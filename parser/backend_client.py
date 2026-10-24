"""One POST per attempt. The SQLite collector owns retries; no redirects or AI."""
from dataclasses import asdict, dataclass, field
from email.utils import parsedate_to_datetime
import math
import time

import httpx
from pydantic import BaseModel, Field, ValidationError


class Receipt(BaseModel):
    news_id: int = Field(gt=0, le=9223372036854775807, strict=True)
    created: bool = Field(strict=True)
    duplicate: bool = Field(strict=True)
    diagnostics: list[str]


@dataclass
class Delivery:
    status: str
    http_status: int | None = None
    news_id: int | None = None
    diagnostics: list[str] = field(default_factory=list)
    retry_at: float | None = None

    def to_dict(self):
        return asdict(self)


def retry_after(value, now):
    """Absolute UTC deadline; malformed hints never bypass bounded retries."""
    if not value:
        return None
    try:
        if value.isascii() and value.isdigit():
            result = now + int(value)
        else:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return None
            result = date.timestamp()
        return max(now, result) if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


class BackendClient:
    def __init__(self, config, client=None, clock=time.time):
        self.endpoint = config.backend_url + "/api/news"
        self.timeout = config.timeout
        self.clock = clock
        self.owned = client is None
        self.client = client or httpx.Client(trust_env=False, follow_redirects=False)

    def close(self):
        if self.owned:
            self.client.close()

    def deliver(self, payload):
        try:
            response = self.client.post(self.endpoint, json=payload.model_dump(mode="json"),
                                        timeout=self.timeout, follow_redirects=False)
        except httpx.TimeoutException:
            return Delivery("timeout")
        except httpx.RequestError:
            return Delivery("network_error")
        status = response.status_code
        if status in {200, 201}:
            try:
                receipt = Receipt.model_validate(response.json())
                created = status == 201
                if receipt.created != created or receipt.duplicate == created:
                    raise ValueError("inconsistent receipt flags")
            except (ValueError, ValidationError):
                return Delivery("invalid_response", status)
            return Delivery("created" if created else "duplicate", status, receipt.news_id, receipt.diagnostics)
        diagnostics = {409: ["NEWS_IDENTITY_CONFLICT"], 422: ["REQUEST_VALIDATION_ERROR"],
                       503: ["BACKEND_TEMPORARY_ERROR"], 403: ["BACKEND_ACCESS_DENIED"]}.get(status, [])
        name = {409: "conflict", 422: "invalid_data", 503: "unavailable", 403: "forbidden",
                429: "rate_limited", 500: "temporary_error", 502: "temporary_error", 504: "temporary_error"}.get(status, "http_error")
        return Delivery(name, status, diagnostics=diagnostics,
                        retry_at=retry_after(response.headers.get("Retry-After"), self.clock()))
