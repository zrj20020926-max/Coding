def normalize_output(value: bytes) -> str:
    text = value.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).rstrip()


def outputs_equal(actual: bytes, expected: bytes) -> bool:
    return normalize_output(actual) == normalize_output(expected)
