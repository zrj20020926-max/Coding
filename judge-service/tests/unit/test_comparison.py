import pytest

from app.domain.comparison import normalize_output, outputs_equal


@pytest.mark.unit
def test_output_comparison_normalizes_line_endings_and_trailing_whitespace() -> None:
    assert outputs_equal(b"1 2  \r\n3\t\r\n\r\n", b"1 2\n3\n")
    assert normalize_output(b" left padded\n") == " left padded"
    assert not outputs_equal(b"1 2", b"1 3")
