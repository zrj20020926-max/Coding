from __future__ import annotations

import json
import subprocess
import tempfile
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
    accepted = 0
    problem_directories = sorted(
        item for item in (ROOT / "reference-solutions").iterdir() if item.is_dir()
    )
    with tempfile.TemporaryDirectory(prefix="codearena-cpp20-") as temporary:
        binary_root = Path(temporary)
        for problem_directory in problem_directories:
            slug = problem_directory.name
            binary = binary_root / slug
            compiled = subprocess.run(
                [
                    "g++", "-std=c++20", "-O2", "-pipe",
                    str(problem_directory / "solution.cpp"), "-o", str(binary),
                ],
                capture_output=True,
                check=False,
                timeout=30,
            )
            if compiled.returncode:
                failures.append({"problem": slug, "check": "compile"})
                continue
            passed = True
            inputs = sorted((ROOT / "test-data" / slug).glob("*.in"))
            if len(inputs) != 6:
                failures.append({"problem": slug, "check": "case_count"})
                continue
            for input_path in inputs:
                expected_path = input_path.with_suffix(".out")
                result = subprocess.run(
                    [str(binary)], input=input_path.read_bytes(), capture_output=True,
                    check=False, timeout=20,
                )
                if result.returncode or normalize(result.stdout) != normalize(expected_path.read_bytes()):
                    failures.append({
                        "problem": slug, "check": "hidden_case", "case": input_path.stem,
                    })
                    passed = False
                    break
            accepted += int(passed)
    report = {
        "status": "success" if not failures and accepted == 30 else "failed",
        "problem_count": len(problem_directories),
        "cpp20_accepted": accepted,
        "hidden_case_count": len(problem_directories) * 6,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "failures": failures,
    }
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
