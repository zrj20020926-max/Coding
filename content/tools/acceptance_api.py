from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("CATALOG_API_URL", "http://backend-api-content-test:8000/api/v1")
TERMINAL = {
    "Accepted", "Wrong Answer", "Compile Error", "Runtime Error",
    "Time Limit Exceeded", "Memory Limit Exceeded", "System Error",
}


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
    token: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    body = json.dumps(payload).encode() if payload is not None else None
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"{BASE_URL}{path}", data=body, headers=headers, method=method
            ),
            timeout=30,
        ) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"API request failed: {method} {path}: HTTP {exc.code}") from None


def submit_and_wait(
    token: str, problem_id: int, language: str, source: str, key: str
) -> str:
    created = request(
        "POST",
        "/submissions",
        payload={
            "problem_id": problem_id,
            "language": language,
            "source_code": source,
            "mode": "judge",
        },
        token=token,
        idempotency_key=key,
    )
    submission_id = created["id"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        detail = request(
            "GET", f"/submissions/{submission_id}/status", token=token
        )
        status = str(detail["status"])
        if status in TERMINAL:
            return status
        time.sleep(0.25)
    raise RuntimeError(f"submission timed out: {key}")


def require_status(
    token: str,
    problem_id: int,
    language: str,
    source: str,
    key: str,
    expected: str,
) -> str:
    status = submit_and_wait(token, problem_id, language, source, key)
    if status == expected:
        return status
    # A previous acceptance run may have snapshotted an older resource limit.
    # One fresh key is sufficient to verify the current content version while
    # preserving the original immutable submission for audit.
    return submit_and_wait(
        token, problem_id, language, source, f"{key}-current-content"
    )


def main() -> int:
    started = time.monotonic()
    credentials = {
        "username": "catalog_acceptance",
        "email": "catalog-acceptance@example.com",
        "password": "Catalog-Acceptance-2026!",
        "nickname": "题库验收员",
    }
    try:
        session = request("POST", "/auth/register", payload=credentials)
    except RuntimeError as exc:
        if "HTTP 409" not in str(exc):
            raise
        session = request(
            "POST",
            "/auth/login",
            payload={
                "account": credentials["username"],
                "password": credentials["password"],
            },
        )
    token = str(session["access_token"])
    page = request("GET", "/problems?page=1&page_size=100&sort=oldest", token=token)
    items = page["items"]
    if not isinstance(items, list) or len(items) < 30:
        raise RuntimeError("public problem API returned fewer than 30 problems")
    problems = {str(item["slug"]): int(item["id"]) for item in items}
    if len(problems) != 30:
        raise RuntimeError("public problem slugs are not unique")
    forbidden = {
        "reference_solutions", "test_set", "test_cases", "input_object_key",
        "output_object_key", "checksum", "docker_image", "compile_command",
    }
    for slug, problem_id in problems.items():
        detail = request("GET", f"/problems/{problem_id}", token=token)
        serialized = json.dumps(detail, sort_keys=True)
        if any(f'"{field}"' in serialized for field in forbidden):
            raise RuntimeError(f"public problem DTO leaked internal fields: {slug}")
    collections = request("GET", "/collections?page=1&page_size=100", token=token)
    collection_items = collections["items"]
    if not isinstance(collection_items, list) or len(collection_items) != 3:
        raise RuntimeError("expected three public collections")
    for collection in collection_items:
        detail = request(
            "GET", f"/collections/{collection['slug']}?page=1&page_size=100", token=token
        )
        if len(detail["problems"]) < 8:
            raise RuntimeError("public collection contains fewer than eight problems")
    request("GET", "/daily-challenge", token=token)

    python_accepted = cpp_accepted = wrong_answers = 0
    for slug, problem_id in problems.items():
        solution_root = ROOT / "reference-solutions" / slug
        python_status = require_status(
            token,
            problem_id,
            "python",
            (solution_root / "solution.py").read_text(encoding="utf-8"),
            f"catalog-python-{slug}",
            "Accepted",
        )
        python_accepted += int(python_status == "Accepted")
        if python_status != "Accepted":
            raise RuntimeError(f"Python reference was not Accepted: {slug}: {python_status}")
        cpp_status = require_status(
            token,
            problem_id,
            "cpp",
            (solution_root / "solution.cpp").read_text(encoding="utf-8"),
            f"catalog-cpp-{slug}",
            "Accepted",
        )
        cpp_accepted += int(cpp_status == "Accepted")
        if cpp_status != "Accepted":
            raise RuntimeError(f"C++ reference was not Accepted: {slug}: {cpp_status}")

    for wrong_source in sorted((ROOT / "wrong-solutions").glob("*.py")):
        slug = wrong_source.stem
        status = require_status(
            token,
            problems[slug],
            "python",
            wrong_source.read_text(encoding="utf-8"),
            f"catalog-wrong-{slug}",
            "Wrong Answer",
        )
        wrong_answers += int(status == "Wrong Answer")
        if status != "Wrong Answer":
            raise RuntimeError(f"wrong solution did not get Wrong Answer: {slug}: {status}")

    report = {
        "status": "success",
        "public_problems": len(problems),
        "details_opened": len(problems),
        "python_accepted": python_accepted,
        "cpp_accepted": cpp_accepted,
        "wrong_answers": wrong_answers,
        "collections": len(collection_items),
        "daily_challenge": 1,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
