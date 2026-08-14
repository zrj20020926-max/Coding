from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.bootstrap.content import ContentBootstrapError, MaterializedProblem, load_content_bundle
from app.schemas.problem import AdminProblem, ProblemDetail, ProblemPage
from app.services.object_storage import SourceObjectStore, get_source_object_store

FORBIDDEN_PUBLIC_FIELDS = {
    "reference_solutions",
    "test_set",
    "test_cases",
    "input_object_key",
    "output_object_key",
    "checksum",
    "compile_command",
    "docker_image",
}


class ValidationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem: str
    check: str
    message: str


class CatalogValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failed"]
    problem_count: int
    hidden_case_count: int
    javascript_v8_accepted: int
    nodejs_accepted: int
    wrong_reading_detected: int
    minio_objects_verified: int
    duration_ms: int
    failures: list[ValidationFailure]


@dataclass(frozen=True)
class ProgramResult:
    returncode: int
    stdout: bytes
    stderr: bytes


def _run(command: list[str], stdin: bytes, timeout_seconds: float) -> ProgramResult:
    completed = subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )
    return ProgramResult(
        completed.returncode,
        completed.stdout.replace(b"\r\n", b"\n"),
        completed.stderr,
    )


def _normalize(output: bytes) -> bytes:
    lines = output.replace(b"\r\n", b"\n").splitlines()
    return b"\n".join(line.rstrip() for line in lines).rstrip()


def _check_public_contracts() -> None:
    schemas = (ProblemPage, ProblemDetail, AdminProblem)
    for schema in schemas:
        serialized = json.dumps(schema.model_json_schema(), sort_keys=True)
        leaked = sorted(field for field in FORBIDDEN_PUBLIC_FIELDS if f'"{field}"' in serialized)
        if leaked:
            raise RuntimeError(f"public DTO contains forbidden fields: {', '.join(leaked)}")


def _validate_solution(
    problem: MaterializedProblem,
    root: Path,
    node: str,
    v8_runner: Path,
    check_v8: bool,
    check_nodejs: bool,
) -> tuple[bool, bool]:
    document = problem.document
    if (
        document.reference_solutions.javascript_v8 is None
        or document.reference_solutions.nodejs is None
    ):
        raise RuntimeError("JavaScript course references are incomplete")
    v8_source = root / document.reference_solutions.javascript_v8
    node_source = root / document.reference_solutions.nodejs
    public_cases = (
        [(sample.input.encode(), sample.output.encode()) for sample in document.samples]
        if document.samples
        else [(document.sample_input.encode(), document.sample_output.encode())]
    )
    cases = public_cases + [
        (case.input_data, case.output_data) for case in problem.cases
    ]
    v8_ok = nodejs_ok = True
    for stdin, expected in cases:
        timeout = max(5, document.time_limit_ms / 1000 * 4)
        normalized_expected = _normalize(expected)
        v8_result = None
        node_result = None
        if check_v8:
            v8_result = _run([node, str(v8_runner), str(v8_source)], stdin, timeout)
            if v8_result.returncode or _normalize(v8_result.stdout) != normalized_expected:
                v8_ok = False
        if check_nodejs:
            node_result = _run([node, str(node_source)], stdin, timeout)
            if node_result.returncode or _normalize(node_result.stdout) != normalized_expected:
                nodejs_ok = False
        if v8_result is not None and node_result is not None:
            if _normalize(v8_result.stdout) != _normalize(node_result.stdout):
                v8_ok = nodejs_ok = False
    return v8_ok, nodejs_ok


def _validate_wrong_reading(
    problem: MaterializedProblem,
    root: Path,
    node: str,
) -> bool:
    relative = problem.document.reference_solutions.nodejs
    if relative is None:
        return False
    source = (root / relative).read_text(encoding="utf-8")
    mutations = (
        source.replace(
            "const lines = input === '' ? [] : input.split('\\n');",
            "const lines = input.trim().split('\\n');",
        ),
        source.replace(
            "line.trim().split(/\\s+/)",
            "line.split(' ')",
        ),
    )
    for case in problem.cases:
        for mutation in mutations:
            result = _run(
                [node, "-e", mutation],
                case.input_data,
                max(5, problem.document.time_limit_ms / 1000 * 4),
            )
            if result.returncode or _normalize(result.stdout) != _normalize(case.output_data):
                return True
    return False


async def _verify_minio(
    problems: dict[str, MaterializedProblem], store: SourceObjectStore
) -> int:
    verified = 0
    for problem in problems.values():
        for case in problem.cases:
            stored_input = await store.get_test_data(case.input_object_key)
            stored_output = await store.get_test_data(case.output_object_key)
            if hashlib.sha256(stored_input).hexdigest() != case.input_hash:
                raise RuntimeError(f"problem {problem.document.slug} has a corrupt stored input")
            if hashlib.sha256(stored_output).hexdigest() != case.output_hash:
                raise RuntimeError(f"problem {problem.document.slug} has a corrupt stored output")
            verified += 2
    return verified


async def validate_catalog(
    manifest: Path,
    *,
    node: str = "node",
    v8_runner: Path | None = None,
    check_minio: bool = False,
    store: SourceObjectStore | None = None,
    check_v8: bool = True,
    check_nodejs: bool = True,
) -> CatalogValidationReport:
    started = time.monotonic()
    failures: list[ValidationFailure] = []
    bundle = load_content_bundle(manifest)
    root = await asyncio.to_thread(lambda: manifest.resolve().parent)
    runner = v8_runner or root / "tools" / "run_v8_reference.cjs"
    _check_public_contracts()
    v8_accepted = nodejs_accepted = wrong_reading_detected = 0
    chapters_with_counterexample: set[str] = set()
    for slug, problem in bundle.problems.items():
        try:
            v8_ok, nodejs_ok = _validate_solution(
                problem,
                root,
                node,
                runner,
                check_v8,
                check_nodejs,
            )
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            failures.append(ValidationFailure(
                problem=slug, check="reference_execution", message=str(exc)[:300]
            ))
            continue
        if check_v8 and v8_ok:
            v8_accepted += 1
        elif check_v8:
            failures.append(ValidationFailure(
                problem=slug, check="javascript_v8_reference", message="reference output mismatch"
            ))
        if check_nodejs and nodejs_ok:
            nodejs_accepted += 1
        elif check_nodejs:
            failures.append(ValidationFailure(
                problem=slug, check="nodejs_reference", message="reference output mismatch"
            ))
        try:
            if check_nodejs and _validate_wrong_reading(problem, root, node):
                wrong_reading_detected += 1
                if problem.document.chapter is not None:
                    chapters_with_counterexample.add(problem.document.chapter)
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(ValidationFailure(
                problem=slug, check="wrong_reading", message=str(exc)[:300]
            ))
    course_chapters = {
        item.document.chapter
        for item in bundle.problems.values()
        if item.document.chapter is not None
    }
    if check_nodejs and chapters_with_counterexample != course_chapters:
        failures.append(ValidationFailure(
            problem="catalog",
            check="wrong_reading_counterexamples",
            message="not every course chapter detects an unsafe reading mutation",
        ))
    minio_verified = 0
    if check_minio:
        try:
            minio_verified = await _verify_minio(
                bundle.problems, store or get_source_object_store()
            )
        except Exception:
            failures.append(
                ValidationFailure(
                    problem="catalog",
                    check="minio_checksum",
                    message="stored object checksum verification failed",
                )
            )
    return CatalogValidationReport(
        status="failed" if failures else "success",
        problem_count=len(bundle.problems),
        hidden_case_count=sum(len(item.cases) for item in bundle.problems.values()),
        javascript_v8_accepted=v8_accepted,
        nodejs_accepted=nodejs_accepted,
        wrong_reading_detected=wrong_reading_detected,
        minio_objects_verified=minio_verified,
        duration_ms=round((time.monotonic() - started) * 1000),
        failures=failures,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the complete CodeArena problem catalog")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--node", default="node")
    parser.add_argument("--v8-runner", type=Path)
    parser.add_argument("--check-minio", action="store_true")
    parser.add_argument("--skip-v8", action="store_true")
    parser.add_argument("--skip-nodejs", action="store_true")
    args = parser.parse_args()
    try:
        report = asyncio.run(validate_catalog(
            args.manifest,
            node=args.node,
            v8_runner=args.v8_runner,
            check_minio=args.check_minio,
            check_v8=not args.skip_v8,
            check_nodejs=not args.skip_nodejs,
        ))
    except ContentBootstrapError as exc:
        report = CatalogValidationReport(
            status="failed", problem_count=0, hidden_case_count=0,
            javascript_v8_accepted=0, nodejs_accepted=0, wrong_reading_detected=0,
            minio_objects_verified=0, duration_ms=0,
            failures=[
                ValidationFailure(
                    problem="catalog", check=exc.code, message=exc.safe_message
                )
            ],
        )
    print(report.model_dump_json())
    raise SystemExit(0 if report.status == "success" else 1)


if __name__ == "__main__":
    main()
