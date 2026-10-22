import base64
import json
import re
from datetime import timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class InvalidInsightCursor(ValueError):
    pass


class InsightCursor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    v: Literal[1] = 1
    company_id: str = Field(min_length=1, max_length=200)
    created_at: AwareDatetime
    id: int = Field(gt=0, le=9223372036854775807)


def encode_cursor(company_id: str, created_at, insight_id: int) -> str:
    position = InsightCursor(company_id=company_id, created_at=created_at, id=insight_id)
    payload = position.model_dump(mode="json")
    payload["created_at"] = position.created_at.astimezone(timezone.utc).isoformat(timespec="microseconds")
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")


def decode_cursor(token: str | None, company_id: str) -> InsightCursor | None:
    if token is None:
        return None
    try:
        if len(token) > 2048 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            raise ValueError("Invalid encoding")
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        # JSON validation permits an ISO timestamp while keeping id strictly int.
        position = InsightCursor.model_validate_json(raw)
        if position.company_id != company_id:
            raise ValueError("Cursor belongs to another company")
        return position
    except (ValueError, TypeError) as error:
        raise InvalidInsightCursor("Invalid insight cursor") from error
