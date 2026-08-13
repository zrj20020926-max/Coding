from decimal import Decimal, InvalidOperation


def normalize_output(value: bytes) -> str:
    text = value.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).rstrip()


def outputs_equal(actual: bytes, expected: bytes) -> bool:
    return normalize_output(actual) == normalize_output(expected)


def token_outputs_equal(actual: bytes, expected: bytes) -> bool:
    return normalize_output(actual).split() == normalize_output(expected).split()


def float_outputs_equal(
    actual: bytes,
    expected: bytes,
    absolute_tolerance: Decimal,
    relative_tolerance: Decimal,
) -> bool:
    actual_tokens = normalize_output(actual).split()
    expected_tokens = normalize_output(expected).split()
    if len(actual_tokens) != len(expected_tokens):
        return False
    for actual_token, expected_token in zip(actual_tokens, expected_tokens, strict=True):
        try:
            actual_number = Decimal(actual_token)
            expected_number = Decimal(expected_token)
        except InvalidOperation:
            if actual_token != expected_token:
                return False
            continue
        # NaN and infinities must never compare equal: accepting matching non-finite
        # values would let user output bypass tolerance checks.
        if not actual_number.is_finite() or not expected_number.is_finite():
            return False
        difference = abs(actual_number - expected_number)
        allowed = max(absolute_tolerance, relative_tolerance * abs(expected_number))
        if difference > allowed:
            return False
    return True
