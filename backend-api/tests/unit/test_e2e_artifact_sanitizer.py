from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from sanitize_e2e_artifacts import sanitize_tree  # noqa: E402


def test_sanitizer_removes_credentials_source_and_dom_context(tmp_path: Path) -> None:
    secret_source = "const privateSource = readline();"
    secret_password = "NeverUpload-Aa1!"
    secret_token = "eyJaaaaaaaaaaaaaaaa.bbbbbbbbbbbbbbbb.cccccccccccccccc"
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "service.log").write_text(
        json.dumps(
            {
                "password": secret_password,
                "access_token": secret_token,
                "source_code": secret_source,
            }
        ),
        encoding="utf-8",
    )
    (artifact_root / "error-context.md").write_text(secret_source, encoding="utf-8")
    (artifact_root / "report.xml").write_text(
        f'<testsuites tests="1" failures="1"><testsuite><testcase name="safe">'
        f'<failure message="{secret_source}">{secret_password}</failure>'
        "</testcase></testsuite></testsuites>",
        encoding="utf-8",
    )
    trace_path = artifact_root / "trace.zip"
    with zipfile.ZipFile(trace_path, "w") as trace:
        trace.writestr(
            "trace.trace",
            json.dumps(
                {
                    "type": "before",
                    "apiName": "keyboard.insertText",
                    "params": {"text": secret_source},
                }
            ),
        )
        trace.writestr(
            "trace.network",
            json.dumps(
                {
                    "request": {
                        "headers": {"authorization": f"Bearer {secret_token}"},
                        "postData": json.dumps(
                            {"password": secret_password, "source_code": secret_source}
                        ),
                    }
                }
            ),
        )
        trace.writestr("screenshot.png", b"unsafe-image")

    sanitize_tree(artifact_root)

    assert not (artifact_root / "error-context.md").exists()
    junit = (artifact_root / "report.xml").read_text(encoding="utf-8")
    service_log = (artifact_root / "service.log").read_text(encoding="utf-8")
    with zipfile.ZipFile(trace_path) as trace:
        names = trace.namelist()
        trace_content = b"\n".join(trace.read(name) for name in names).decode("utf-8")
    for sensitive in (secret_source, secret_password, secret_token):
        assert sensitive not in junit
        assert sensitive not in service_log
        assert sensitive not in trace_content
    assert "screenshot.png" not in names
    assert "failure" in junit
    assert "[REDACTED]" in trace_content
