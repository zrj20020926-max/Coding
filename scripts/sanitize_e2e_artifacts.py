from __future__ import annotations

import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "checksum",
    "cookie",
    "input_object_key",
    "output_object_key",
    "password",
    "refresh_token",
    "secret",
    "set-cookie",
    "source_code",
    "source_object_key",
    "token",
}
TEXT_SUFFIXES = {
    ".json",
    ".jsonl",
    ".log",
    ".network",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
BEARER_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~-]+")
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|secret|access[_-]?token|refresh[_-]?token|authorization|cookie|"
    r"source[_-]?(?:code|object[_-]?key)|(?:input|output)[_-]?object[_-]?key|checksum)"
    r"([\"']?\s*[:=]\s*)([^\s,}]+)"
)


def scrub_value(value: Any, key: str | None = None) -> Any:
    normalized_key = (key or "").casefold().replace("-", "_")
    if normalized_key in {item.replace("-", "_") for item in SENSITIVE_KEYS}:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {item_key: scrub_value(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [scrub_value(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                return json.dumps(scrub_value(parsed), ensure_ascii=False, separators=(",", ":"))
        return scrub_text(value)
    return value


def scrub_text(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        ending = "\n" if line.endswith("\n") else ""
        candidate = line[:-1] if ending else line
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            cleaned = BEARER_PATTERN.sub("Bearer [REDACTED]", candidate)
            cleaned = JWT_PATTERN.sub("[REDACTED_TOKEN]", cleaned)
            cleaned = KEY_VALUE_PATTERN.sub(r"\1\2[REDACTED]", cleaned)
        else:
            cleaned = json.dumps(scrub_value(parsed), ensure_ascii=False, separators=(",", ":"))
        lines.append(cleaned + ending)
    return "".join(lines)


def scrub_trace_value(value: Any) -> Any:
    if isinstance(value, dict):
        api_name = str(value.get("apiName", "")).casefold()
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = key.casefold().replace("-", "_")
            if normalized_key in {"postdata", "post_data", "requestbody", "request_body"}:
                cleaned[key] = "[REDACTED]"
            elif key == "params" and api_name.endswith((".fill", ".type", ".inserttext")):
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = scrub_trace_value(item)
        return scrub_value(cleaned)
    if isinstance(value, list):
        return [scrub_trace_value(item) for item in value]
    return scrub_value(value)


def scrub_trace_text(content: str) -> str:
    lines: list[str] = []
    for line in content.splitlines(keepends=True):
        ending = "\n" if line.endswith("\n") else ""
        candidate = line[:-1] if ending else line
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            cleaned = scrub_text(candidate)
        else:
            cleaned = json.dumps(
                scrub_trace_value(parsed), ensure_ascii=False, separators=(",", ":")
            )
        lines.append(cleaned + ending)
    return "".join(lines)


def sanitize_junit(path: Path) -> None:
    try:
        tree = ElementTree.parse(path)
    except ElementTree.ParseError:
        path.write_text(scrub_text(path.read_text(encoding="utf-8")), encoding="utf-8")
        return
    root = tree.getroot()
    for properties in list(root.iter("properties")):
        properties.clear()
    for tag in ("failure", "error", "system-out", "system-err"):
        for element in root.iter(tag):
            element.attrib.pop("message", None)
            element.text = "[REDACTED]"
    tree.write(path, encoding="utf-8", xml_declaration=True)


def sanitize_zip(path: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=path.parent) as handle:
        replacement = Path(handle.name)
    try:
        with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(
            replacement, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if Path(item.filename).suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}:
                    continue
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    target.writestr(item, data)
                else:
                    scrubber = (
                        scrub_trace_text
                        if Path(item.filename).name in {"trace.trace", "trace.network"}
                        else scrub_text
                    )
                    target.writestr(item, scrubber(text).encode("utf-8"))
        replacement.replace(path)
    finally:
        replacement.unlink(missing_ok=True)


def sanitize_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.casefold() == ".md":
            # Playwright error-context Markdown embeds a DOM snapshot and may
            # contain form values or Monaco's visible user source.
            path.unlink()
            continue
        if path.suffix.casefold() == ".zip":
            sanitize_zip(path)
            continue
        if path.suffix.casefold() == ".xml":
            sanitize_junit(path)
            continue
        if path.suffix.casefold() not in TEXT_SUFFIXES and path.name not in {
            "trace.trace",
            "trace.network",
        }:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        path.write_text(scrub_text(content), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: sanitize_e2e_artifacts.py <artifact-directory>")
    sanitize_tree(Path(sys.argv[1]).resolve())
