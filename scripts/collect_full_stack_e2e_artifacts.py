from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sanitize_e2e_artifacts import sanitize_tree

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "full-stack-e2e"
PROJECT = os.getenv("FULL_STACK_COMPOSE_PROJECT", "codearena-full-stack-e2e")


def compose_output(*arguments: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            PROJECT,
            "-f",
            str(ROOT / "docker-compose.content-test.yml"),
            *arguments,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout + result.stderr


def main() -> int:
    if not PROJECT.startswith("codearena-full-stack-e2e"):
        raise RuntimeError("refusing to collect from a non-E2E Compose project")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "compose-status.jsonl").write_text(
        compose_output("ps", "--format", "json"), encoding="utf-8"
    )
    (ARTIFACTS / "compose-services.log").write_text(
        compose_output("logs", "--no-color", "--timestamps"), encoding="utf-8"
    )
    sanitize_tree(ARTIFACTS)
    print(str(ARTIFACTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
