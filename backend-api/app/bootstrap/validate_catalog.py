from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
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
    python_accepted: int
    cpp_accepted: int
    wrong_answer_verified: int
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


def _compile_cpp(compiler: str, source: Path, binary: Path) -> None:
    result = subprocess.run(
        [compiler, "-std=c++20", "-O2", "-pipe", str(source), "-o", str(binary)],
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError("C++20 reference implementation failed to compile")


def _validate_solution(
    problem: MaterializedProblem,
    root: Path,
    python: str,
    compiler: str,
    binary_root: Path,
    check_python: bool,
    check_cpp: bool,
) -> tuple[bool, bool]:
    document = problem.document
    python_source = root / document.reference_solutions.python
    cpp_source = root / document.reference_solutions.cpp
    binary = binary_root / document.slug
    if sys.platform == "win32":
        binary = binary.with_suffix(".exe")
    if check_cpp:
        _compile_cpp(compiler, cpp_source, binary)
    cases = [(document.sample_input.encode(), document.sample_output.encode())] + [
        (case.input_data, case.output_data) for case in problem.cases
    ]
    python_ok = cpp_ok = True
    for stdin, expected in cases:
        timeout = max(5, document.time_limit_ms / 1000 * 4)
        normalized_expected = _normalize(expected)
        python_result = None
        cpp_result = None
        if check_python:
            python_result = _run([python, str(python_source)], stdin, timeout)
            if python_result.returncode or _normalize(python_result.stdout) != normalized_expected:
                python_ok = False
        if check_cpp:
            cpp_result = _run([str(binary)], stdin, timeout)
            if cpp_result.returncode or _normalize(cpp_result.stdout) != normalized_expected:
                cpp_ok = False
        if python_result is not None and cpp_result is not None:
            if _normalize(python_result.stdout) != _normalize(cpp_result.stdout):
                python_ok = cpp_ok = False
    return python_ok, cpp_ok


def _validate_wrong_solution(
    problem: MaterializedProblem,
    root: Path,
    python: str,
) -> bool:
    wrong_source = root / "wrong-solutions" / f"{problem.document.slug}.py"
    if not wrong_source.is_file():
        return False
    for case in problem.cases:
        result = _run(
            [python, str(wrong_source)],
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
    python: str,
    compiler: str,
    check_minio: bool = False,
    store: SourceObjectStore | None = None,
    check_python: bool = True,
    check_cpp: bool = True,
) -> CatalogValidationReport:
    started = time.monotonic()
    failures: list[ValidationFailure] = []
    bundle = load_content_bundle(manifest)
    root = await asyncio.to_thread(lambda: manifest.resolve().parent)
    _check_public_contracts()
    python_accepted = cpp_accepted = wrong_answer_verified = 0
    with tempfile.TemporaryDirectory(prefix="codearena-catalog-") as temporary:
        binary_root = Path(temporary)
        for slug, problem in bundle.problems.items():
            try:
                python_ok, cpp_ok = _validate_solution(
                    problem,
                    root,
                    python,
                    compiler,
                    binary_root,
                    check_python,
                    check_cpp,
                )
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                failures.append(ValidationFailure(
                    problem=slug, check="reference_execution", message=str(exc)[:300]
                ))
                continue
            if check_python and python_ok:
                python_accepted += 1
            elif check_python:
                failures.append(ValidationFailure(
                    problem=slug, check="python_reference", message="reference output mismatch"
                ))
            if check_cpp and cpp_ok:
                cpp_accepted += 1
            elif check_cpp:
                failures.append(ValidationFailure(
                    problem=slug, check="cpp_reference", message="reference output mismatch"
                ))
            try:
                if check_python and _validate_wrong_solution(problem, root, python):
                    wrong_answer_verified += 1
            except (OSError, subprocess.TimeoutExpired) as exc:
                failures.append(ValidationFailure(
                    problem=slug, check="wrong_solution", message=str(exc)[:300]
                ))
    if check_python and wrong_answer_verified < 10:
        failures.append(ValidationFailure(
            problem="catalog",
            check="wrong_solutions",
            message="fewer than ten wrong solutions were verified as Wrong Answer",
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
        python_accepted=python_accepted,
        cpp_accepted=cpp_accepted,
        wrong_answer_verified=wrong_answer_verified,
        minio_objects_verified=minio_verified,
        duration_ms=round((time.monotonic() - started) * 1000),
        failures=failures,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the complete CodeArena problem catalog")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--compiler", default=shutil.which("g++") or "g++")
    parser.add_argument("--check-minio", action="store_true")
    parser.add_argument("--skip-python", action="store_true")
    parser.add_argument("--skip-cpp", action="store_true")
    args = parser.parse_args()
    try:
        report = asyncio.run(validate_catalog(
            args.manifest,
            python=args.python,
            compiler=args.compiler,
            check_minio=args.check_minio,
            check_python=not args.skip_python,
            check_cpp=not args.skip_cpp,
        ))
    except ContentBootstrapError as exc:
        report = CatalogValidationReport(
            status="failed", problem_count=0, hidden_case_count=0,
            python_accepted=0, cpp_accepted=0, wrong_answer_verified=0,
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
