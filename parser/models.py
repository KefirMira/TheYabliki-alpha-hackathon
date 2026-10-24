"""Independent wire model matching ExternalNewsInput; no backend dependency."""
import re
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, field_validator

ASCII_WHITESPACE = " \t\n\r\f\v"


class NewsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500, strict=True)
    content: str = Field(min_length=1, max_length=100_000, strict=True)
    url: str | None = Field(default=None, min_length=1, max_length=2048, strict=True)
    source_name: str = Field(min_length=1, max_length=100, strict=True)
    source_id: str | None = Field(default=None, min_length=1, max_length=500, strict=True)
    published_at: AwareDatetime | None = None
    language: str | None = Field(default=None, min_length=1, max_length=10, strict=True)

    @field_validator("title", "content", "language")
    @classmethod
    def nonblank(cls, value):
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("empty text or NUL")
        return value

    @field_validator("source_name")
    @classmethod
    def technical_source(cls, value):
        if re.fullmatch(r"[a-z0-9._-]+", value) is None:
            raise ValueError("source_name must be lowercase ASCII")
        return value

    @field_validator("source_id")
    @classmethod
    def external_id(cls, value):
        if value is not None and (value != value.strip(ASCII_WHITESPACE) or "\x00" in value):
            raise ValueError("source_id has surrounding ASCII whitespace or NUL")
        return value

    @field_validator("url")
    @classmethod
    def synthetic_url(cls, value):
        if value is None:
            return None
        if any(ord(c) <= 32 or ord(c) == 127 for c in value) or re.search(r"%(?![0-9a-fA-F]{2})", value):
            raise ValueError("invalid URL characters")
        TypeAdapter(AnyHttpUrl).validate_python(value)
        parts = urlsplit(value)
        if (parts.scheme not in {"http", "https"} or not parts.hostname
                or parts.username is not None or parts.password is not None or "\\" in value):
            raise ValueError("invalid HTTP URL")
        if parts.hostname != "example.invalid" and not parts.hostname.endswith(".example.invalid"):
            raise ValueError("v1.13.0 permits only synthetic example.invalid links")
        return value  # Backend owns canonicalization; don't duplicate its algorithm.
