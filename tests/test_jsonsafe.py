import pytest

from addon.jsonsafe import MAX_DEPTH, safe_loads


def nested(n: int) -> str:
    return "[" * n + "]" * n


def test_normal_documents_pass() -> None:
    assert safe_loads('{"a": [1, {"b": "c"}]}') == {"a": [1, {"b": "c"}]}
    assert safe_loads(nested(MAX_DEPTH)) is not None


@pytest.mark.parametrize("n", [MAX_DEPTH + 1, 5_000, 100_000])
def test_too_deep_is_refused_without_parsing(n: int) -> None:
    with pytest.raises(ValueError, match="trop imbriqué"):
        safe_loads(nested(n))
    with pytest.raises(ValueError, match="trop imbriqué"):
        safe_loads(nested(n).encode())


def test_brackets_inside_strings_do_not_count() -> None:
    text = '{"k": "' + "[" * 500 + '", "e": "\\"' + "{" * 500 + '"}'
    assert safe_loads(text)["k"] == "[" * 500


def test_accepts_bytes_and_surrogate_text() -> None:
    assert safe_loads(b'{"a": 1}') == {"a": 1}
    assert safe_loads('{"a": "\\ud800"}') == {"a": "\ud800"}


def test_still_reports_plain_json_errors_as_value_error() -> None:
    with pytest.raises(ValueError):
        safe_loads("{nope")
