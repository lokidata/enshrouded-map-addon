from typing import Any

import pytest
from pydantic import ValidationError

from addon.config import Settings

BASE: dict[str, Any] = {
    "pelican_url": "https://panel.example.test/",
    "pelican_api_key": "pacc_TEST",
    "pelican_server_id": "abcd1234",
    "site_url": "http://site.example.test",
}


def make(**over: Any) -> Settings:
    return Settings(**{**BASE, **over})


def test_trailing_slash_stripped() -> None:
    assert make().pelican_url == "https://panel.example.test"


def test_key_never_in_repr() -> None:
    s = make()
    assert "pacc_TEST" not in repr(s)
    assert "pacc_TEST" not in str(s.pelican_api_key)
    assert s.pelican_api_key.get_secret_value() == "pacc_TEST"


def test_defaults() -> None:
    s = make()
    assert (s.db_path, s.journal_days, s.pelican_timeout) == ("/data/addon.db", 1, 10)


@pytest.mark.parametrize("missing", ["pelican_url", "pelican_api_key"])
def test_required(missing: str) -> None:
    data = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ValidationError):
        Settings(**data)


def test_http_refused_unless_allowed() -> None:
    with pytest.raises(ValidationError):
        make(pelican_url="http://panel.example.test")
    assert make(pelican_url="http://panel.example.test/", allow_http=True).pelican_url == (
        "http://panel.example.test"
    )
