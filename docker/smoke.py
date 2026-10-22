"""Docker-only smoke checks. Refuses full mode; never submits paid analysis."""
import json
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def main():
    if os.environ.get("SMOKE_MODE") != "demo":
        raise SystemExit("Smoke POST checks are allowed only with the demo Compose configuration")
    base = os.environ.get("SMOKE_BASE_URL", "http://backend:8000")

    def call(path, expected=200, data=None, headers=None, method=None):
        request = Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                          headers={"Content-Type": "application/json", **(headers or {})}, method=method)
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            assert response.status == expected, (path, response.status, response.read().decode())
            body = response.read()
            return (json.loads(body) if body and body.startswith(b"{") else {}, response.headers)

    assert call("/health")[0] == {"status": "ok"}
    ready = call("/ready")[0]
    assert ready["status"] == "ready" and ready["checks"]["database"]
    assert not ready["checks"]["llm_config"], "Refusing POST tests when LLM configuration is present"
    assert call("/api/companies/DEMO-001")[0]["revenue"] == "12345678.90"
    assert call("/api/companies/DEMO-002")[0]["name"]
    assert call("/api/companies/DEMO-003/insights")[0]["items"] == []
    feed = call("/api/companies/DEMO-001/insights?limit=1")[0]
    assert len(feed["items"]) == 1 and feed["next_cursor"]
    first = feed["items"][0]["insight_id"]
    page = call("/api/companies/DEMO-001/insights?limit=1&cursor=" + quote(feed["next_cursor"]))[0]
    assert page["items"][0]["insight_id"] < first
    card = call(f"/api/companies/DEMO-001/insights/{first}")[0]
    assert card["status"] == "COMPLETED" and card["evidence"] and card["sources"]
    assert card["validation"]["passed"] is False
    call(f"/api/companies/DEMO-002/insights/{first}", 404)
    call("/api/companies/missing", 404)
    call("/api/companies/DEMO-001/insights?limit=0", 422)
    origin = os.environ.get("SMOKE_CORS_ORIGIN", "http://localhost:5173").split(",")[0].strip()
    _, headers = call("/api/companies/DEMO-001", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization"}, method="OPTIONS")
    assert headers["Access-Control-Allow-Origin"] == origin
    _, denied = call("/api/companies/DEMO-001", 400, headers={
        "Origin": "https://untrusted.example.invalid", "Access-Control-Request-Method": "GET"}, method="OPTIONS")
    assert "Access-Control-Allow-Origin" not in denied
    for path in ("/api/analyze", "/api/analyze-rag", "/api/analyze-company",
                 "/api/companies/DEMO-001/analyses"):
        assert call(path, 503, data={})[0]["detail"]["code"] == "AI_DISABLED_IN_DEMO"
    assert len(call("/openapi.json")[0]["paths"]) == 9
    print("PASS: demo readiness, Decimal profile, feed/card, pagination, isolation, errors, CORS, all AI routes blocked")


if __name__ == "__main__":
    main()
