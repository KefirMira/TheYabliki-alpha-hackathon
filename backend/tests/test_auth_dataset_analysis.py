import asyncio
import json
from unittest.mock import patch
import pytest
from sqlalchemy import event
from services.auth_service import token_digest
from services.company_analysis_service import CompanyAnalysisService,AnalysisFailure
from services.dataset_analysis import DatasetAnalyzer,DatasetDraftAdapter,LocalDatasetClient
from services.external_context_policy import PolicyDenied
from repositories.news_analysis_job_repository import AnalysisConflict
from schemas.auth import Principal
from synthetic_actor_fixture import job_database
from test_news_identity_migration import identity_dsn
from dataset_fixture import seed_dataset,manifest

pytestmark=pytest.mark.integration

def test_dataset_atomic_claim_cache_acl_and_no_db_during_fake(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine,sessions,c,news):
            await seed_dataset(c,news)
            user=await c.fetchval("SELECT id FROM auth_users LIMIT 1")
            actor=Principal(user,"synthetic",token_digest(sessions.synthetic_test_token))
            from services.dataset_smoke_plan import prepare_smoke_plan
            plan=await prepare_smoke_plan(sessions,actor,"SYNTH-COMPANY-A",news,manifest())
            assert plan.summary()["requests"]==0 and plan.input_byte_allowance<=8000
            assert await c.fetchval("SELECT count(*) FROM news_analysis_attempts")==0
            adapter=DatasetDraftAdapter(LocalDatasetClient())
            analyzer=DatasetAnalyzer(sessions,actor,manifest(),adapter,news)
            service=CompanyAnalysisService(sessions,analyzer=analyzer,
                context_loader=analyzer.policy.load_context,actor_id=user)
            active=0
            def checkout(*args):
                nonlocal active
                active+=1
            def checkin(*args):
                nonlocal active
                active-=1
            event.listen(engine.sync_engine,"checkout",checkout)
            event.listen(engine.sync_engine,"checkin",checkin)
            original=adapter.complete
            async def complete(dto):
                assert active==0
                return await original(dto)
            adapter.complete=complete
            results=await asyncio.gather(*(service.analyze_saved("SYNTH-COMPANY-A",news) for _ in range(8)),
                return_exceptions=True)
            assert any(not isinstance(r,Exception) for r in results),results
            assert all(not isinstance(r,Exception) or isinstance(r,AnalysisConflict) for r in results),results
            assert adapter.requests==1
            assert await c.fetchval("SELECT count(*) FROM news_analysis_attempts")==1
            assert await c.fetchval("SELECT count(*) FROM company_news_analyses")==1
            assert await c.fetchval("SELECT count(*) FROM insight_evidence")==1
            value=json.loads(await c.fetchval("SELECT validation::text FROM company_news_analyses"))
            assert value["orchestration"]["version"]=="hackathon-dataset-v1"
            assert value["orchestration"]["status"]=="COMPLETED"
            assert value["financial_review"]["financial_correctness"]=="UNKNOWN"
            saved=await service.analyze_saved("SYNTH-COMPANY-A",news)
            assert saved.reused and adapter.requests==1
            await c.execute("DELETE FROM auth_news_grants")
            with pytest.raises(Exception) as error:
                await service.analyze_saved("SYNTH-COMPANY-A",news)
            assert getattr(error.value,"status_code",None)==403
    asyncio.run(scenario())

@pytest.mark.parametrize("failure",["sdk","evidence"])
def test_dataset_failures_never_partial_and_no_auto_retry(identity_dsn,failure):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed_dataset(c,news)
            user=await c.fetchval("SELECT id FROM auth_users LIMIT 1")
            actor=Principal(user,"synthetic",token_digest(sessions.synthetic_test_token))
            client=LocalDatasetClient()
            if failure=="sdk":
                async def fail(**kwargs):
                    raise TimeoutError()
                client.create=fail
            adapter=DatasetDraftAdapter(client)
            analyzer=DatasetAnalyzer(sessions,actor,manifest(),adapter,news)
            from repositories.evidence_repository import EvidenceRepository
            class BadEvidence(EvidenceRepository):
                async def create(self,*args):
                    raise ValueError("synthetic-storage-failure")
            kwargs={"evidence_repository":BadEvidence} if failure=="evidence" else {}
            service=CompanyAnalysisService(sessions,analyzer=analyzer,
                context_loader=analyzer.policy.load_context,actor_id=user,**kwargs)
            with pytest.raises(AnalysisFailure):
                await service.analyze_saved("SYNTH-COMPANY-A",news)
            assert adapter.requests==1
            assert await c.fetchval("SELECT count(*) FROM company_news_analyses")==0
            assert await c.fetchval("SELECT count(*) FROM insight_evidence")==0
            with pytest.raises(AnalysisConflict):
                await service.analyze_saved("SYNTH-COMPANY-A",news)
            assert adapter.requests==1
    asyncio.run(scenario())


def test_dataset_http_consent_acl_off_and_cache(identity_dsn,monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    from main import app
    import hashlib
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed_dataset(c,news)
            previous=getattr(app.state,"company_sessions",None)
            app.state.company_sessions=sessions
            approved=manifest()
            path=tmp_path/"manifest.json"
            path.write_text(approved.model_dump_json(),encoding="utf-8")
            monkeypatch.setenv("DATASET_AI_MANIFEST",str(path))
            monkeypatch.setenv("DATASET_AI_MANIFEST_SHA256",hashlib.sha256(path.read_bytes()).hexdigest())
            monkeypatch.setenv("DATASET_AI_TRANSPORT","fake")
            auth={"Authorization":"Bearer "+sessions.synthetic_test_token}
            route=f"/api/companies/SYNTH-COMPANY-A/news/{news}/dataset-analyses"
            try:
                with TestClient(app,raise_server_exceptions=False) as client:
                    # Lifespan installs its own factory; use this isolated fixture only.
                    app.state.company_sessions=sessions
                    assert client.post(route,json={"news_external_transfer_confirmed":True}).status_code==401
                    assert client.post(route,headers=auth,json={}).status_code==422
                    caps=client.get("/api/companies/SYNTH-COMPANY-A/capabilities",headers=auth)
                    assert caps.status_code==200
                    assert caps.json()["dataset_transport"]=="fake"
                    assert caps.json()["operations"]["analyze_new"]["state"]=="BLOCKED"
                    first=client.post(route,headers=auth,json={"news_external_transfer_confirmed":True})
                    assert first.status_code==201,first.text
                    second=client.post(route,headers=auth,json={"news_external_transfer_confirmed":True})
                    assert second.status_code==200 and first.json()==second.json()
                    feed=client.get("/api/companies/SYNTH-COMPANY-A/insights",headers=auth)
                    assert feed.status_code==200
                    candidates=client.get("/api/companies/SYNTH-COMPANY-A/dataset-news",headers=auth)
                    assert candidates.status_code==200
                    assert candidates.json()["matching"]=="TOPICAL_CANDIDATES_NOT_CONFIRMED"
                    foreign=client.get("/api/companies/UNKNOWN/dataset-news",headers=auth)
                    assert foreign.status_code==403
                    card=client.get("/api/companies/SYNTH-COMPANY-A/insights/"+str(first.json()["insight_id"]),headers=auth)
                    assert card.status_code==200
                    assert card.json()["validation"]["financial_review"]["financial_correctness"]=="UNKNOWN"
                    monkeypatch.setenv("DATASET_AI_TRANSPORT","organizer")
                    # No explicit operator real confirmation: never construct/send SDK.
                    assert client.post(route,headers=auth,json={"news_external_transfer_confirmed":True}).status_code==503
                    monkeypatch.setenv("DATASET_AI_REAL_CONFIRMED","one-bounded-draft-approved")
                    monkeypatch.setenv("DATASET_AI_REAL_PAIR_SHA256","f"*64)
                    with patch("services.dataset_analysis.DatasetDraftAdapter.organizer",side_effect=AssertionError("SDK_MUST_NOT_BE_CREATED")):
                        wrong=client.post(route,headers=auth,json={"news_external_transfer_confirmed":True})
                        assert wrong.status_code==503
                        assert wrong.json()["detail"]["code"]=="DATASET_REAL_PAIR_NOT_APPROVED"
                    monkeypatch.setenv("DATASET_AI_TRANSPORT","off")
                    assert client.post(route,headers=auth,json={"news_external_transfer_confirmed":True}).status_code==503
            finally:
                app.state.company_sessions=previous
    asyncio.run(scenario())



def test_structural_counts_are_conditional_and_never_amounts_or_F_roles(identity_dsn):
    from repositories.company_repository import CompanyRepository
    from services.dataset_analysis import HackathonDatasetPolicy
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed_dataset(c,news)
            pmeta=json.dumps({"_external_csv_row_v1":{"source":"df_Uid_payment_hack","file_sha256":"b"*64}})
            lmeta=json.dumps({"_external_csv_row_v1":{"source":"df_Fid_Uid_link_hack","file_sha256":"c"*64}})
            for index in range(2):
                await c.execute("""INSERT INTO company_payments(source_id,source_company_id,payer_source_company_id,
                    amount,source_name,source_data) VALUES($1,'SYNTH-COMPANY-A','UNPROFILED',999.99,'df_Uid_payment_hack',$2::jsonb)""",
                    "synthetic-payment-"+str(index),pmeta)
            await c.execute("""INSERT INTO company_person_links(source_id,source_company_id,source_person_id,
                source_name,source_data) VALUES('synthetic-link','SYNTH-COMPANY-A','SYNTH-F-UNKNOWN',
                'df_Fid_Uid_link_hack',$1::jsonb)""",lmeta)
            approved=manifest().model_copy(update={"payment_aggregates_approved":True,
                "payment_file_sha256":"b"*64,"link_file_sha256":"c"*64})
            p=HackathonDatasetPolicy(approved)
            async with sessions() as session:
                company=await CompanyRepository(session).get_by_source_id("SYNTH-COMPANY-A")
                context=await p.load_context(session,company)
            dto,_=p.prepare(context,"Учебная ключевая ставка, платежи поставщикам и структура связей")
            payload=json.loads(dto.messages[1].content)["company_source_assertions"]
            assert payload["computed"]["payment_structure"]["incoming_rows"]==2
            assert payload["computed"]["payment_structure"]["incoming_counterparties"]==1
            assert payload["computed"]["external_link_structure"]["source_rows"]==1
            assert "999.99" not in dto.messages[1].content
            assert "SYNTH-F-UNKNOWN" not in dto.messages[1].content
            assert "UNPROFILED" not in dto.messages[1].content
            unrelated,_=p.prepare(context,"Учебная ключевая ставка")
            assert json.loads(unrelated.messages[1].content)["company_source_assertions"]["computed"]=={}
    asyncio.run(scenario())



def test_policy_rejection_rolls_back_claim_before_any_sdk(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_,sessions,c,news):
            await seed_dataset(c,news)
            await c.execute("UPDATE companies SET source_data='{}'::jsonb")
            user=await c.fetchval("SELECT id FROM auth_users LIMIT 1")
            actor=Principal(user,"synthetic",token_digest(sessions.synthetic_test_token))
            adapter=DatasetDraftAdapter(LocalDatasetClient())
            analyzer=DatasetAnalyzer(sessions,actor,manifest(),adapter,news)
            service=CompanyAnalysisService(sessions,analyzer=analyzer,
                context_loader=analyzer.policy.load_context,actor_id=user)
            with pytest.raises(PolicyDenied):
                await service.analyze_saved("SYNTH-COMPANY-A",news)
            assert adapter.requests==0
            assert await c.fetchval("SELECT count(*) FROM news_analysis_jobs")==0
            assert await c.fetchval("SELECT count(*) FROM analysis_runs")==0
    asyncio.run(scenario())
