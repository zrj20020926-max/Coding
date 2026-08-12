from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalize(output: bytes) -> bytes:
    return b"\n".join(
        line.rstrip() for line in output.replace(b"\r\n", b"\n").splitlines()
    ).rstrip()


def main() -> int:
    started = time.monotonic()
    failures = []
    accepted = wrong_answers = 0
    problem_directories = sorted(
        item for item in (ROOT / "reference-solutions").iterdir() if item.is_dir()
    )
    for problem_directory in problem_directories:
        slug = problem_directory.name
        source = problem_directory / "solution.py"
        inputs = sorted((ROOT / "test-data" / slug).glob("*.in"))
        passed = len(inputs) == 6
        for input_path in inputs:
            expected = input_path.with_suffix(".out").read_bytes()
            result = subprocess.run(
                ["python", str(source)], input=input_path.read_bytes(),
                capture_output=True, check=False, timeout=20,
            )
            if result.returncode or normalize(result.stdout) != normalize(expected):
                failures.append({
                    "problem": slug, "check": "hidden_case", "case": input_path.stem,
                })
                passed = False
                break
        accepted += int(passed)
        wrong_source = ROOT / "wrong-solutions" / f"{slug}.py"
        if wrong_source.is_file():
            for input_path in inputs:
                expected = input_path.with_suffix(".out").read_bytes()
                result = subprocess.run(
                    ["python", str(wrong_source)], input=input_path.read_bytes(),
                    capture_output=True, check=False, timeout=20,
                )
                if result.returncode or normalize(result.stdout) != normalize(expected):
                    wrong_answers += 1
                    break
    report = {
        "status": (
            "success"
            if not failures and accepted == 30 and wrong_answers >= 10
            else "failed"
        ),
        "problem_count": len(problem_directories),
        "python312_accepted": accepted,
        "wrong_answer_verified": wrong_answers,
        "hidden_case_count": len(problem_directories) * 6,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "failures": failures,
    }
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
