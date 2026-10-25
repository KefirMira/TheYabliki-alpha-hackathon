"""Documentation metadata must describe all operations without filtering legacy output."""
from fastapi.testclient import TestClient
from main import app


def test_all_operations_are_documented():
    spec = app.openapi()
    operations = [(path, method, value) for path, methods in spec["paths"].items()
                  for method, value in methods.items() if method in {"get", "post"}]
    assert {(path,method) for path,method,_ in operations} == {
        ("/health","get"),("/ready","get"),("/api/news","post"),
        ("/api/auth/login","post"),("/api/auth/logout","post"),("/api/me","get"),
        ("/api/companies/{source_id}","get"),
        ("/api/companies/{source_id}/insights","get"),
        ("/api/companies/{source_id}/insights/{insight_id}","get"),
        ("/api/companies/{source_id}/capabilities","get"),
        ("/api/companies/{source_id}/analyses","post"),
        ("/api/companies/{source_id}/news/{news_id}/analyses","post"),
        ("/api/companies/{source_id}/news/{news_id}/dataset-analyses","post"),
        ("/api/companies/{source_id}/dataset-news","get"),
        ("/api/analyze","post"),("/api/analyze-company","post"),("/api/analyze-rag","post"),
    }
    assert spec["info"]["version"] == "1.27.0"
    for path, method, operation in operations:
        assert operation["description"], (method, path)
        for status, response in operation["responses"].items():
            if status == "204":
                continue
            assert response["content"]["application/json"]["schema"], (path, status)
    assert set(spec["paths"]["/ready"]["get"]["responses"]) == {"200", "503"}
    news = spec["paths"]["/api/news"]["post"]
    assert set(news["responses"]) == {"200", "201", "401", "403", "409", "422", "503"}
    assert spec["components"]["schemas"]["ExternalNewsInput"]["required"] == ["title", "content"]
    saved = spec["paths"]["/api/companies/{source_id}/news/{news_id}/analyses"]["post"]
    assert "requestBody" not in saved
    assert {"200", "201", "401", "403", "404", "409", "422", "502", "503"} == set(saved["responses"])
    assert "Demo блокирует и cache" in saved["responses"]["200"]["description"]
    assert "ACCESS_DENIED" in news["responses"]["403"]["description"]
    assert "DATABASE_UNAVAILABLE" in spec["paths"]["/api/auth/login"]["post"]["responses"]["503"]["description"]


def test_rag_documentation_does_not_filter_runtime_response(monkeypatch):
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = {"analysis": "synthetic", "sources": [], "additional_metadata": "preserved"}
    async def analyzer(**kwargs): return result
    monkeypatch.setattr("main.analyze_with_rag", analyzer)
    with TestClient(app) as client:
        assert client.post("/api/analyze-rag", json={"news": "synthetic"}).json() == result
