"""Settings, read from the environment only."""

import re
from functools import lru_cache
from typing import Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    pelican_url: str
    pelican_api_key: SecretStr
    pelican_server_id: str
    site_url: str
    db_path: str = "/data/addon.db"
    journal_days: int = 1
    pelican_timeout: float = 10
    allow_http: bool = False
    allowed_origin: str | None = None
    # Pelican "ignored files" for backups (gitignore-style, one pattern per line; `\n` accepted).
    backup_ignored: str = ""
    # chestsort categories file, relative to the server root; unset = feature off
    chestsort_file: str | None = None
    # folder of the built UI; empty = frontend/dist/browser next to src/
    static_dir: str = ""

    @model_validator(mode="after")
    def _normalise_url(self) -> Self:
        self.pelican_url = self.pelican_url.rstrip("/")
        if self.allowed_origin:
            self.allowed_origin = self.allowed_origin.rstrip("/")
            if not re.fullmatch(r"https?://[^/\s]+", self.allowed_origin):
                raise ValueError(
                    "ALLOWED_ORIGIN must look like https://host[:port] (scheme, no path)"
                )
        f = self.chestsort_file
        if f is not None and (
            not f.startswith("/")
            or f.endswith("/")
            or ".." in f
            or "\\" in f
            or len(f) > 200
            or any(ord(c) < 32 or ord(c) == 127 for c in f)
        ):
            raise ValueError(
                "CHESTSORT_FILE must be a file path from the server root (/name.json), no '..'"
            )
        self.backup_ignored = self.backup_ignored.replace("\\n", "\n")
        if not self.allow_http and not self.pelican_url.startswith("https://"):
            raise ValueError("PELICAN_URL must use https (set ALLOW_HTTP=true to override)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
