"""Never return credentials, password hashes or session hashes."""
from dataclasses import dataclass, field
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    login: str
    token_hash: str = field(repr=False)


class LoginInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    login: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int = 3600


class Membership(BaseModel):
    source_id: str
    name: str | None
    can_analyze: bool


class CurrentUser(BaseModel):
    user_id: UUID
    login: str
    companies: list[Membership]
