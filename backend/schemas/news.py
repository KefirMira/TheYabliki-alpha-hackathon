from datetime import datetime
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from services.news_url import canonical_url

ASCII_WHITESPACE = " \t\n\r\f\v"


class ExternalNewsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500, strict=True)
    content: str = Field(min_length=1, max_length=100_000, strict=True)
    url: str | None = Field(default=None, min_length=1, max_length=2048, strict=True, description="HTTP(S), без credentials; canonical scheme/host, без fragment/tracking; path и HTTP/HTTPS различаются")
    source_name: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9._-]+$", strict=True)
    source_id: str | None = Field(default=None, min_length=1, max_length=500, strict=True, description="Регистр сохраняется; запрещены крайние ASCII whitespace и NUL; Unicode-пробелы отдельно не нормализуются")
    published_at: AwareDatetime | None = Field(default=None, description="ISO 8601 с явным timezone; отсутствие не заменяется временем приёма")
    language: str | None = Field(default=None, min_length=1, max_length=10, strict=True)

    @field_validator("title", "content", "language")
    @classmethod
    def nonblank(cls, value):
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("Value must contain text and no NUL")
        return value

    @field_validator("source_id")
    @classmethod
    def external_id(cls, value):
        if value is not None and (value != value.strip(ASCII_WHITESPACE) or "\x00" in value):
            raise ValueError("source_id must not have surrounding ASCII whitespace or NUL")
        return value

    @field_validator("published_at", mode="before")
    @classmethod
    def explicit_timestamp(cls, value):
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("published_at must be ISO 8601 with an explicit timezone")
        return value

    @field_validator("url")
    @classmethod
    def http_url(cls, value):
        if value is None:
            return None
        if any(ord(c) <= 32 or ord(c) == 127 for c in value) or re.search(r"%(?![0-9a-fA-F]{2})", value):
            raise ValueError("URL contains whitespace, control characters or invalid escapes")
        TypeAdapter(AnyHttpUrl).validate_python(value)
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError("URL must have an explicit HTTP/HTTPS scheme and hostname")
        if parts.username is not None or parts.password is not None or "\\" in value:
            raise ValueError("URL credentials and backslashes are not allowed")
        return canonical_url(value)


class NewsMetadata(BaseModel):
    title: str
    url: str | None
    source_name: str | None
    source_id: str | None
    published_at: datetime | None
    language: str | None
    input_kind: str


class IngestedNews(BaseModel):
    news_id: int
    created: bool
    duplicate: bool
    diagnostics: list[Literal["URL_MISMATCH", "SOURCE_IDENTITY_MISMATCH", "CONTENT_MISMATCH", "TITLE_MISMATCH", "METADATA_MISMATCH"]]
    news: NewsMetadata
