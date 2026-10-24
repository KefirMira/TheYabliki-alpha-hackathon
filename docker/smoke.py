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
            assert response.status in (expected if isinstance(expected, tuple) else (expected,)), (path, response.status, response.read().decode())
            body = response.read()
            return (json.loads(body) if body and body.startswith(b"{") else {}, response.headers)

    assert call("/health")[0] == {"status": "ok"}
    _, docs_headers = call("/docs")
    assert 'text/html' in docs_headers['Content-Type']
    ready = call("/ready")[0]
    assert ready["status"] == "ready" and ready["checks"]["database"]
    assert not ready["checks"]["llm_config"], "Refusing POST tests when LLM configuration is present"
    for path in ['/api/companies/DEMO-001', '/api/companies/DEMO-002', '/api/companies/DEMO-003',
                 '/api/companies/DEMO-001/insights', '/api/companies/DEMO-001/insights/1', '/api/me']:
        assert call(path, 401)[0]['detail']['code'] == 'AUTHENTICATION_REQUIRED'
    origin = os.environ.get("SMOKE_CORS_ORIGIN", "http://localhost:5173").split(",")[0].strip()
    _, headers = call("/api/companies/DEMO-001", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization"}, method="OPTIONS")
    assert headers["Access-Control-Allow-Origin"] == origin
    _, denied = call("/api/companies/DEMO-001", 400, headers={
        "Origin": "https://untrusted.example.invalid", "Access-Control-Request-Method": "GET"}, method="OPTIONS")
    assert "Access-Control-Allow-Origin" not in denied
    for path in ('/api/analyze','/api/analyze-rag','/api/analyze-company','/api/news',
                 '/api/companies/DEMO-001/news/1/analyses','/api/companies/DEMO-001/analyses'):
        assert call(path,401,data={})[0]['detail']['code']=='AUTHENTICATION_REQUIRED'
    spec=call('/openapi.json')[0]
    assert len(spec['paths'])==14
    assert spec['components']['securitySchemes']
    print('PASS: public readiness/Swagger, CORS, anonymous read/write denied; no LLM calls')


if __name__ == '__main__':
    main()
