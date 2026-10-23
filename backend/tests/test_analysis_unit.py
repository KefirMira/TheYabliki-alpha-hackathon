import asyncio
from contextlib import asynccontextmanager
from datetime import date
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from repositories.company_repository import CompanyRecord
from repositories.evidence_repository import complete_date
from schemas.company import CompanyProfile
from schemas.persisted_analysis import PersistableAnalysis
from services import company_analysis_service as service_module
from services.company_analysis_service import AnalysisFailure, CompanyAnalysisService, RunStatusUncertain


@pytest.mark.parametrize("raw,expected", [(None, None), ("2026", None), ("2026-08", None),
    ("2026-02-30", None), ("2026-08-12", date(2026, 8, 12))])
def test_document_date_never_invents_precision(raw, expected):
    assert complete_date(raw) == expected


def test_bundle_requires_matching_retrieved_evidence(bundle_factory):
    raw = bundle_factory().model_dump()
    raw["evidence"][0]["document"] = "wrong.pdf"
    with pytest.raises(ValidationError):
        PersistableAnalysis.model_validate(raw)
    raw = bundle_factory().model_dump()
    raw["evidence"] = []
    with pytest.raises(ValidationError):
        PersistableAnalysis.model_validate(raw)


@pytest.mark.parametrize("failure", [None, "ai", "evidence", "status"])
def test_transaction_boundaries_and_failure_status(monkeypatch, bundle_factory, failure):
    events = []
    active = 0

    class Sessions:
        @asynccontextmanager
        async def __call__(self):
            nonlocal active
            active += 1
            events.append("open")
            try:
                yield self
            finally:
                active -= 1
                events.append("close")

        @asynccontextmanager
        async def begin(self):
            try:
                yield
            except Exception:
                events.append("rollback")
                raise
            else:
                events.append("commit")

    record = CompanyRecord(1, "SYNTH-COMPANY-A", "Synthetic", None, None, None, None, None)

    class Repositories:
        def __init__(self, session):
            pass

        async def get_by_source_id(self, source_id):
            return record

        async def create_manual(self, *args):
            return 2

        async def start(self, *args):
            return 3

        async def create(self, *args):
            return 4

        async def finish(self, run_id, status, **values):
            events.append(status)
            if failure == "status" and status == "FAILED":
                raise OSError("Unavailable")

    class Evidence(Repositories):
        async def create(self, *args):
            if failure == "evidence":
                raise RuntimeError("Evidence failed")
            events.append("evidence")

    for name in ["CompanyRepository", "NewsRepository", "AnalysisRunRepository", "CompanyAnalysisRepository"]:
        monkeypatch.setattr(service_module, name, Repositories)

    async def analyzer(**kwargs):
        assert active == 0
        assert events[-2:] == ["commit", "close"]
        if failure in ("ai", "status"):
            raise RuntimeError("AI failed")
        return bundle_factory()

    service = CompanyAnalysisService(Sessions(), analyzer, Evidence)
    if failure is None:
        assert asyncio.run(service.analyze(record.source_id, "Synthetic persistence news")).run_id == 3
        assert "COMPLETED" in events and "FAILED" not in events
    else:
        with pytest.raises(RunStatusUncertain if failure == "status" else AnalysisFailure):
            asyncio.run(service.analyze(record.source_id, "Synthetic persistence news"))
        assert "FAILED" in events and "COMPLETED" not in events
    assert active == 0


def load_service(name, filename):
    path = Path(__file__).resolve().parents[1] / "services" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rag_captures_exact_selected_text_without_changing_legacy_response(monkeypatch):
    import sys

    completion = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Synthetic answer"), finish_reason="stop")],
        model="synthetic-model", usage=None,
    ))
    fake_openai = ModuleType("openai")
    sdk_options = []
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
    fake_client.with_options = lambda **kwargs: (sdk_options.append(kwargs) or fake_client)
    fake_openai.AsyncOpenAI = lambda **kwargs: fake_client
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.setenv(key, "synthetic-test-only")
    selected = {"source": "synthetic.pdf", "page": 2, "chunk_id": 3, "score": 0.42, "text": "Exact text.\nLine two."}
    for name, attr, value in [
        ("knowledge_base_service", "load_knowledge_base", lambda: [selected]),
        ("search_service", "search_chunks", lambda **kwargs: [selected]),
    ]:
        module = ModuleType("services." + name)
        setattr(module, attr, value)
        monkeypatch.setitem(sys.modules, "services." + name, module)
    rag = load_service("tested_rag_capture", "rag_service.py")
    rag.DOCUMENT_DATES = {"synthetic.pdf": "2026-08"}
    legacy = asyncio.run(rag.analyze_with_rag("Synthetic question"))
    enriched = asyncio.run(rag.analyze_with_rag("Synthetic question", include_evidence=True))
    assert set(legacy) == {"analysis", "sources"}
    assert enriched["sources"] == legacy["sources"]
    assert enriched["evidence"][0]["text"] == selected["text"]
    assert enriched["evidence"][0]["date"] == "2026-08"
    assert enriched["model_name"] == "synthetic-model"
    from services.protected_ai import invoke, protected_call
    protected = asyncio.run(invoke(rag.analyze_with_rag, question='Synthetic', include_evidence=True))
    assert protected['evidence'] == enriched['evidence']
    assert sdk_options == [{'max_retries': 0, 'timeout': 120}]
    assert protected_call.get() is False


def test_personalization_legacy_contract_and_internal_bundle(monkeypatch, bundle_factory):
    import json
    import sys

    bundle = bundle_factory()
    rag_result = {
        "analysis": json.dumps(bundle.analysis.model_dump(include={"relevance", "summary", "risks", "opportunities", "recommendations"})),
        "sources": [item.model_dump(exclude={"text"}) for item in bundle.evidence],
        "evidence": [item.model_dump() for item in bundle.evidence], "model_name": "synthetic-model",
    }
    rag = ModuleType("services.rag_service")
    rag.analyze_with_rag = AsyncMock(return_value=rag_result)
    monkeypatch.setitem(sys.modules, "services.rag_service", rag)
    module = load_service("tested_personalization_capture", "personalization_service.py")
    company = CompanyProfile(company_id="SYNTH-COMPANY-A")
    legacy = asyncio.run(module.analyze_for_company(bundle.analysis.news, company))
    assert set(legacy) == set(type(bundle.analysis).model_fields)
    assert set(legacy["sources"][0]) == {"id", "document", "page", "score"}
    captured = asyncio.run(module.analyze_for_company_with_evidence(bundle.analysis.news, company))
    assert captured.evidence == bundle.evidence
    assert rag.analyze_with_rag.await_args.kwargs["include_evidence"] is True
