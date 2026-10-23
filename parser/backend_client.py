"""Only POST /api/news, once per item. No retries, redirects, DB or AI calls."""
from dataclasses import asdict, dataclass, field

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

    def to_dict(self):
        return asdict(self)


class BackendClient:
    def __init__(self, config, client=None):
        self.endpoint = config.backend_url + "/api/news"
        self.timeout = config.timeout
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
        return Delivery({409: "conflict", 422: "invalid_data", 503: "unavailable", 403: "forbidden"}.get(status, "http_error"),
                        status, diagnostics=diagnostics)
