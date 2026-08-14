from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("CATALOG_API_URL", "http://backend-api-content-test:8000/api/v1")
TERMINAL = {
    "Accepted", "Wrong Answer", "Compile Error", "Runtime Error",
    "Time Limit Exceeded", "Memory Limit Exceeded", "Output Limit Exceeded", "System Error",
}


class ApiRequestError(RuntimeError):
    def __init__(self, method: str, path: str, status: int) -> None:
        self.status = status
        super().__init__(f"API request failed: {method} {path}: HTTP {status}")


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
        raise ApiRequestError(method, path, exc.code) from None


class ApiClient:
    def __init__(self, credentials: dict[str, object]) -> None:
        self.credentials = credentials
        self._access_token = ""
        self._auth_lock = Lock()

    def authenticate(self, *, register: bool = False) -> None:
        with self._auth_lock:
            if register:
                try:
                    session = request("POST", "/auth/register", payload=self.credentials)
                except ApiRequestError as exc:
                    if exc.status != 409:
                        raise
                else:
                    self._access_token = str(session["access_token"])
                    return
            session = request(
                "POST",
                "/auth/login",
                payload={
                    "account": self.credentials["username"],
                    "password": self.credentials["password"],
                },
            )
            self._access_token = str(session["access_token"])

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        token = self._access_token
        try:
            return request(
                method,
                path,
                payload=payload,
                token=token,
                idempotency_key=idempotency_key,
            )
        except ApiRequestError as exc:
            if exc.status != 401:
                raise
        # Long catalog runs can outlive the short access-token lifetime. Only
        # one polling thread renews the session; peers reuse the new token.
        with self._auth_lock:
            if self._access_token == token:
                session = request(
                    "POST",
                    "/auth/login",
                    payload={
                        "account": self.credentials["username"],
                        "password": self.credentials["password"],
                    },
                )
                self._access_token = str(session["access_token"])
            renewed_token = self._access_token
        return request(
            method,
            path,
            payload=payload,
            token=renewed_token,
            idempotency_key=idempotency_key,
        )


def submit_and_wait(
    client: ApiClient, problem_id: int, language: str, source: str, key: str
) -> str:
    created = client.request(
        "POST",
        "/submissions",
        payload={
            "problem_id": problem_id,
            "language": language,
            "source_code": source,
            "mode": "judge",
        },
        idempotency_key=key,
    )
    submission_id = created["id"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        detail = client.request("GET", f"/submissions/{submission_id}/status")
        status = str(detail["status"])
        if status in TERMINAL:
            return status
        time.sleep(0.25)
    raise RuntimeError(f"submission timed out: {key}")


def require_status(
    client: ApiClient,
    problem_id: int,
    language: str,
    source: str,
    key: str,
    expected: str,
) -> str:
    status = submit_and_wait(client, problem_id, language, source, key)
    if status == expected:
        return status
    # A previous acceptance run may have snapshotted an older resource limit.
    # One fresh key is sufficient to verify the current content version while
    # preserving the original immutable submission for audit.
    status = submit_and_wait(
        client, problem_id, language, source, f"{key}-current-content"
    )
    if status != expected:
        raise RuntimeError(f"unexpected status for {key}: expected {expected}, got {status}")
    return status


def enqueue(
    client: ApiClient, problem_id: int, language: str, source: str, key: str
) -> str:
    created = client.request(
        "POST",
        "/submissions",
        payload={
            "problem_id": problem_id,
            "language": language,
            "source_code": source,
            "mode": "judge",
        },
        idempotency_key=key,
    )
    return str(created["id"])


def wait_for_all(
    client: ApiClient,
    submissions: list[tuple[str, str, str]],
    timeout_seconds: int = 1800,
) -> None:
    pending = {submission_id: (slug, language) for submission_id, slug, language in submissions}
    deadline = time.monotonic() + timeout_seconds
    with ThreadPoolExecutor(max_workers=24) as executor:
        while pending and time.monotonic() < deadline:
            ids = list(pending)
            statuses = executor.map(
                lambda submission_id: client.request(
                    "GET", f"/submissions/{submission_id}/status"
                ),
                ids,
            )
            for submission_id, detail in zip(ids, statuses):
                status = str(detail["status"])
                if status not in TERMINAL:
                    continue
                slug, language = pending.pop(submission_id)
                if status != "Accepted":
                    raise RuntimeError(
                        f"reference was not Accepted: {slug}/{language}: {status}"
                    )
            if pending:
                time.sleep(0.5)
    if pending:
        raise RuntimeError(f"reference acceptance timed out with {len(pending)} pending")


def main() -> int:
    started = time.monotonic()
    credentials = {
        "username": "catalog_acceptance",
        "email": "catalog-acceptance@example.com",
        "password": "Catalog-Acceptance-2026!",
        "nickname": "题库验收员",
    }
    client = ApiClient(credentials)
    client.authenticate(register=True)
    first_page = client.request("GET", "/problems?page=1&page_size=100&sort=oldest")
    items = list(first_page["items"])
    for page_number in range(2, int(first_page["pages"]) + 1):
        page = client.request(
            "GET", f"/problems?page={page_number}&page_size=100&sort=oldest"
        )
        items.extend(page["items"])
    if len(items) != 168:
        raise RuntimeError("public training API did not return exactly 168 exercises")
    problems = {str(item["slug"]): int(item["id"]) for item in items}
    if len(problems) != 168:
        raise RuntimeError("public problem slugs are not unique")
    output_problem_count = sum(slug.startswith("js-acm-output-") for slug in problems)
    if output_problem_count != 63:
        raise RuntimeError("public training API did not return all 63 output exercises")
    forbidden = {
        "reference_solutions", "test_set", "test_cases", "input_object_key",
        "output_object_key", "checksum", "docker_image", "compile_command",
    }
    for slug in problems:
        detail = client.request("GET", f"/problems/{slug}")
        serialized = json.dumps(detail, sort_keys=True)
        if any(f'"{field}"' in serialized for field in forbidden):
            raise RuntimeError(f"public problem DTO leaked internal fields: {slug}")
    collections = client.request("GET", "/collections?page=1&page_size=100")
    collection_items = collections["items"]
    if not isinstance(collection_items, list) or len(collection_items) != 18:
        raise RuntimeError("expected eighteen public course chapters")
    for collection in collection_items:
        detail = client.request(
            "GET", f"/collections/{collection['slug']}?page=1&page_size=100"
        )
        if not detail["problems"]:
            raise RuntimeError("public course chapter is empty")
    client.request("GET", "/daily-challenge")

    submissions: list[tuple[str, str, str]] = []
    for slug, problem_id in problems.items():
        course_directory = "js-acm-output" if slug.startswith("js-acm-output-") else "js-acm"
        solution_root = ROOT / "reference-solutions" / course_directory / slug
        v8_id = enqueue(
            client,
            problem_id,
            "javascript-v8",
            (solution_root / "solution-v8.js").read_text(encoding="utf-8"),
            f"course-v8-{slug}",
        )
        submissions.append((v8_id, slug, "javascript-v8"))
        nodejs_id = enqueue(
            client,
            problem_id,
            "nodejs",
            (solution_root / "solution-nodejs.js").read_text(encoding="utf-8"),
            f"course-nodejs-{slug}",
        )
        submissions.append((nodejs_id, slug, "nodejs"))
    wait_for_all(client, submissions)

    wrong_output_sources: dict[str, str] = {}
    for slug in (
        "js-acm-output-values-single-space",
        "js-acm-output-no-debug-output",
        "js-acm-output-bigint-without-suffix",
        "js-acm-output-fixed-two-decimals",
        "js-acm-output-blank-between-groups",
    ):
        source_path = (
            ROOT / "reference-solutions" / "js-acm-output" / slug / "solution-nodejs.js"
        )
        source = source_path.read_text(encoding="utf-8")
        if slug == "js-acm-output-values-single-space":
            mutated = source.replace("tokens.join(' ')", "tokens.join('  ')", 1)
        elif slug == "js-acm-output-bigint-without-suffix":
            mutated = source.replace(
                "BigInt(tokens[0] ?? '0').toString()",
                "`${BigInt(tokens[0] ?? '0')}n`",
                1,
            )
        elif slug == "js-acm-output-fixed-two-decimals":
            mutated = source.replace(
                "fixedDecimal(tokens[0] ?? '0', 2)",
                "Number(tokens[0] ?? 0).toFixed(1)",
                1,
            )
        elif slug == "js-acm-output-blank-between-groups":
            mutated = source.replace("join('\\n\\n')", "join('\\n')", 1)
        else:
            mutated = "process.stdout.write('debug: extra\\n');\n" + source
        if mutated == source:
            raise RuntimeError(f"wrong-output mutation did not change source: {slug}")
        wrong_output_sources[slug] = mutated

    for slug, source in wrong_output_sources.items():
        require_status(
            client,
            problems[slug],
            "nodejs",
            source,
            f"course-wrong-output-{slug}",
            "Wrong Answer",
        )

    report = {
        "status": "success",
        "public_problems": len(problems),
        "details_opened": len(problems),
        "javascript_v8_accepted": len(problems),
        "nodejs_accepted": len(problems),
        "output_exercises": output_problem_count,
        "wrong_output_verified": len(wrong_output_sources),
        "collections": len(collection_items),
        "daily_challenge": 1,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
