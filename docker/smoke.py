"""Docker-only smoke checks. Refuses full mode; never submits paid analysis."""
import json
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


PUBLIC_OPERATIONS = {('/health', 'get'), ('/ready', 'get'), ('/api/auth/login', 'post')}
PROTECTED_OPERATIONS = {
    ('/api/me', 'get'), ('/api/auth/logout', 'post'),
    ('/api/companies/{source_id}', 'get'),
    ('/api/companies/{source_id}/capabilities', 'get'),
    ('/api/companies/{source_id}/insights', 'get'),
    ('/api/companies/{source_id}/insights/{insight_id}', 'get'),
    ('/api/companies/{source_id}/analyses', 'post'),
    ('/api/companies/{source_id}/news/{news_id}/analyses', 'post'),
    ('/api/news', 'post'), ('/api/analyze', 'post'),
    ('/api/analyze-rag', 'post'), ('/api/analyze-company', 'post'),
}


def check_spec(spec):
    # Additional operations are allowed; missing/replaced routes must fail.
    for path, method in PUBLIC_OPERATIONS | PROTECTED_OPERATIONS:
        operation = spec['paths'][path][method]
        if (path, method) in PROTECTED_OPERATIONS:
            assert operation.get('security') == [{'HTTPBearer': []}], (method, path)
            assert {'401', '403', '503'} <= operation['responses'].keys(), (method, path)
    capability = spec['paths']['/api/companies/{source_id}/capabilities']['get']
    assert capability['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/CompanyCapabilities')


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
                 '/api/companies/DEMO-001/insights', '/api/companies/DEMO-001/insights/1',
                 '/api/companies/DEMO-001/capabilities', '/api/me']:
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
    check_spec(spec)
    token = os.environ.get('SMOKE_ACCESS_TOKEN')
    if token:
        source = os.environ.get('SMOKE_COMPANY_SOURCE_ID')
        forbidden = os.environ.get('SMOKE_FORBIDDEN_COMPANY_SOURCE_ID')
        assert source and forbidden and source != forbidden, 'Authenticated smoke requires own and forbidden company IDs'
        auth = {'Authorization': 'Bearer ' + token}
        path = '/api/companies/' + quote(source, safe='') + '/capabilities'
        body, headers = call(path, headers=auth)
        assert headers['Cache-Control'] == 'no-store'
        assert body['company_id'] == source and body['mode'] == 'demo'
        ops = body['operations']
        assert ops['read_profile']['state'] == 'AVAILABLE'
        assert ops['analyze_new']['state'] == ops['reuse_completed']['state'] == 'BLOCKED'
        assert {'AI_DISABLED_IN_DEMO', 'COMPANY_CONTEXT_EXTERNAL_TRANSFER_BLOCKED'} <= {
            reason['code'] for reason in ops['analyze_new']['reasons']}
        assert body['external_provider'] == {'state': 'UNKNOWN', 'reason': {
            'category': 'PROVIDER', 'code': 'PROVIDER_NOT_PROBED'}}
        denied_path = '/api/companies/' + quote(forbidden, safe='') + '/capabilities'
        assert call(denied_path, 403, headers=auth)[0]['detail']['code'] == 'ACCESS_DENIED'
        print('PASS: authenticated capabilities and foreign company denial; no LLM calls')
    else:
        print('SKIP: authenticated capabilities (no individual SMOKE_ACCESS_TOKEN); anonymous ACL verified')
    print('PASS: concrete OpenAPI routes, public readiness/Swagger, CORS, anonymous read/write denied; no LLM calls')


if __name__ == '__main__':
    main()
