import asyncio
import json

import pytest
from sqlalchemy import text

from company_import.storage import MARKER, NAMESPACE, apply_audit
from company_import.validation import ImportProblem, audit_file
from repositories.company_repository import CompanyRepository
from services.company_profile_service import CompanyProfileService
from test_company_import import synthetic_row, write_csv
from test_job_claim_integration import job_database, identity_dsn
from test_news_identity_migration import DATABASE_ROOT

pytestmark = pytest.mark.integration


async def marked_target(c, engine):
    name = await c.fetchval('SELECT current_database()')
    # Only the UUID database created by job_database, never the supplied control DB.
    assert name.startswith('test_news_identity_') and len(name) == len('test_news_identity_') + 32
    await c.execute(f'COMMENT ON DATABASE "{name}" IS \'{MARKER}\'')
    return engine.url.render_as_string(hide_password=False), name


def test_import_repeat_update_protected_fields_profile_and_history(tmp_path, identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine, sessions, c, news):
            await c.execute((DATABASE_ROOT / 'migrations/006_news_company_matching.sql').read_text(encoding='utf-8'))
            url, name = await marked_target(c, engine)
            path = write_csv(tmp_path / 'synthetic.csv', [synthetic_row()])
            audit = audit_file(path)
            assert (await apply_audit(audit, url, name))['created'] == 1
            company = await c.fetchval("SELECT id FROM companies WHERE source_id='SYNTH-IMPORT-001'")
            before = await c.fetchval('SELECT row_to_json(t)::text FROM companies t WHERE id=$1', company)
            assert (await apply_audit(audit, url, name))['unchanged'] == 1
            assert await c.fetchval('SELECT row_to_json(t)::text FROM companies t WHERE id=$1', company) == before
            async with sessions() as session:
                response = await CompanyProfileService(CompanyRepository(session)).get_frontend_profile('SYNTH-IMPORT-001')
                assert response.name is None and response.name_is_placeholder
                assert response.credit_exposure is None and response.revenue_year is None
                assert response.model_dump(mode='json')['revenue'] == '1234567890.12'
                assert response.client_status == 'CLOSED_CLIENT'
            await c.execute("UPDATE companies SET name='Синтетическое проверенное имя',inn='1234567890',ogrn='1234567890123',employee_count=42,website='https://synthetic.invalid' WHERE id=$1", company)
            await c.execute("INSERT INTO company_verified_names(company_id,name,verified_by,provenance) VALUES($1,'Синтетическое альтернативное имя','Synthetic reviewer','Synthetic registry')", company)
            run = await c.fetchval("INSERT INTO analysis_runs(company_id,analysis_type,status) VALUES($1,'NEWS','COMPLETED') RETURNING id", company)
            analysis = await c.fetchval('INSERT INTO company_news_analyses(analysis_run_id,company_id,news_id) VALUES($1,$2,$3) RETURNING id', run, company, news)
            await c.execute("INSERT INTO insight_evidence(company_news_analysis_id,evidence_type,evidence_text) VALUES($1,'DOCUMENT','Synthetic historical evidence')", analysis)
            async def history():
                return [await c.fetch(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY id')
                        for table in ['analysis_runs','company_news_analyses','insight_evidence','company_verified_names']]
            old_history = await history()
            changed = audit_file(write_csv(path, [synthetic_row(REVENUE_COMPANY='456.78', REGION='Другой синтетический регион')]))
            with pytest.raises(ImportProblem, match='EXISTING_PROFILE_REQUIRES_UPDATE'):
                await apply_audit(changed, url, name)
            assert (await apply_audit(changed, url, name, update_existing=True))['updated'] == 1
            row = await c.fetchrow('SELECT * FROM companies WHERE id=$1', company)
            assert row['name'] == 'Синтетическое проверенное имя' and row['inn'] == '1234567890'
            assert row['ogrn'] == '1234567890123' and row['employee_count'] == 42
            assert str(row['revenue']) == '456.78' and row['revenue_year'] is None
            provenance = json.loads(row['source_data'])[NAMESPACE]
            assert len(provenance['history']) == 1 and provenance['current']['lines'] == [2]
            assert provenance['current']['file_sha256'] == changed.file_hash
            assert await history() == old_history
            from repositories.news_match_repository import NewsMatchRepository
            async with sessions() as session:
                catalogue = await NewsMatchRepository(session).catalogue()
                assert any(item['id'] == company and item['inn'] == '1234567890' for item in catalogue)
    asyncio.run(scenario())


def test_partial_concurrent_import_dated_revenue_and_existing_metadata(tmp_path, identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine, _, c, _):
            url, name = await marked_target(c, engine)
            rows = [synthetic_row('SYNTH-OK'), synthetic_row('SYNTH-BAD'), synthetic_row('SYNTH-BAD', CITY='Другой город')]
            audit = audit_file(write_csv(tmp_path / 'synthetic.csv', rows))
            with pytest.raises(ImportProblem, match='PARTIAL_IMPORT_CONFIRMATION_REQUIRED'):
                await apply_audit(audit, url, name)
            assert await c.fetchval("SELECT count(*) FROM companies WHERE source_id LIKE 'SYNTH-%'") == 2
            results = await asyncio.gather(*(apply_audit(audit, url, name, allow_partial=True) for _ in range(4)))
            assert sum(r['created'] for r in results) == 1
            assert sum(r['unchanged'] for r in results) == 3
            assert not await c.fetchval("SELECT count(*) FROM companies WHERE source_id='SYNTH-BAD'")
            await c.execute("UPDATE companies SET revenue_year=2024, source_data=source_data || '{\"keep\":\"synthetic\"}'::jsonb WHERE source_id='SYNTH-OK'")
            changed = audit_file(write_csv(tmp_path / 'synthetic.csv', [synthetic_row('SYNTH-OK', REVENUE_COMPANY='1.23')]))
            result = await apply_audit(changed, url, name, update_existing=True)
            assert result['dated_revenue_preserved'] == 1
            row = await c.fetchrow("SELECT * FROM companies WHERE source_id='SYNTH-OK'")
            assert str(row['revenue']) == '1234567890.12' and row['revenue_year'] == 2024
            assert json.loads(row['source_data'])['keep'] == 'synthetic'
    asyncio.run(scenario())


def test_failure_rolls_back_insert_and_update(tmp_path, identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine, _, c, _):
            url, name = await marked_target(c, engine)
            initial = audit_file(write_csv(tmp_path / 'synthetic.csv', [synthetic_row('SYNTH-AAA')]))
            await apply_audit(initial, url, name)
            before = await c.fetch('SELECT row_to_json(t)::text FROM companies t ORDER BY id')
            await c.execute("""CREATE FUNCTION synthetic_import_failure() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.source_id='SYNTH-ZZZ' THEN RAISE EXCEPTION 'Synthetic failure'; END IF;
                RETURN NEW; END $$;
                CREATE TRIGGER synthetic_import_failure BEFORE INSERT ON companies FOR EACH ROW EXECUTE FUNCTION synthetic_import_failure()""")
            audit = audit_file(write_csv(tmp_path / 'synthetic.csv', [synthetic_row('SYNTH-AAA', REGION='Обновление'), synthetic_row('SYNTH-BBB'), synthetic_row('SYNTH-ZZZ')]))
            from sqlalchemy.exc import DBAPIError
            with pytest.raises(DBAPIError):
                await apply_audit(audit, url, name, update_existing=True)
            assert await c.fetch('SELECT row_to_json(t)::text FROM companies t ORDER BY id') == before
    asyncio.run(scenario())


def test_database_marker_and_unmanaged_record_guards(tmp_path, identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (engine, _, c, _):
            name = await c.fetchval('SELECT current_database()')
            url = engine.url.render_as_string(hide_password=False)
            audit = audit_file(write_csv(tmp_path / 'synthetic.csv', [synthetic_row('SYNTH-COMPANY-A')]))
            with pytest.raises(ImportProblem, match='ISOLATED_DATABASE_MARKER_REQUIRED'):
                await apply_audit(audit, url, name)
            await marked_target(c, engine)
            with pytest.raises(ImportProblem, match='EXISTING_PROFILE_REQUIRES_UPDATE'):
                await apply_audit(audit, url, name)
            await apply_audit(audit, url, name, update_existing=True)
            assert await c.fetchval("SELECT name FROM companies WHERE source_id='SYNTH-COMPANY-A'") == 'Synthetic'
    asyncio.run(scenario())
