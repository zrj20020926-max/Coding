from decimal import Decimal

import pytest

from app.domain.comparison import (
    float_outputs_equal,
    normalize_output,
    outputs_equal,
    token_outputs_equal,
)


@pytest.mark.unit
def test_output_comparison_normalizes_line_endings_and_trailing_whitespace() -> None:
    assert outputs_equal(b"1 2  \r\n3\t\r\n\r\n", b"1 2\n3\n")
    assert normalize_output(b" left padded\n") == " left padded"
    assert not outputs_equal(b"1 2", b"1 3")


@pytest.mark.unit
def test_exact_preserves_middle_whitespace_semantics() -> None:
    assert outputs_equal(b"a b  \r\n", b"a b\n")
    assert not outputs_equal(b"a  b\n", b"a b\n")
    assert not outputs_equal(b" a\n", b"a\n")


@pytest.mark.unit
def test_token_checker_requires_same_tokens_in_same_order() -> None:
    assert token_outputs_equal(b"1\t2\r\nhello", b"1  2\nhello\n")
    assert not token_outputs_equal(b"1 2", b"2 1")
    assert not token_outputs_equal(b"1 2 3", b"1 2")


@pytest.mark.unit
def test_float_checker_supports_absolute_relative_and_text_tokens() -> None:
    assert float_outputs_equal(
        b"value 100.09 0.0009",
        b"value 100 0",
        Decimal("0.001"),
        Decimal("0.001"),
    )
    assert not float_outputs_equal(
        b"Value 1", b"value 1", Decimal("0.01"), Decimal("0.01")
    )
    assert not float_outputs_equal(
        b"1 2", b"1 2 3", Decimal("0.01"), Decimal("0.01")
    )


@pytest.mark.unit
@pytest.mark.parametrize("value", [b"NaN", b"nan", b"Infinity", b"-Infinity"])
def test_float_checker_rejects_non_finite_numbers(value: bytes) -> None:
    assert not float_outputs_equal(value, value, Decimal("1"), Decimal("1"))
