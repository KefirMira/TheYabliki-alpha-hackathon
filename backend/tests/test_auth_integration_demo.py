"""Synthetic, real PostgreSQL and real auth dependencies; no SDK."""
import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from integration_demo import seed, MARKER, LOGINS
from main import app
from services.auth_service import HASHER
from test_news_identity_migration import isolated_database, identity_dsn, DATABASE_ROOT

pytestmark = pytest.mark.integration
PASSWORDS = ['Invented-demo-password-a', 'Invented-demo-password-b']


async def setup(c, name, dsn, monkeypatch):
    for file in ['004_news_external_identity.sql', '005_saved_news_analysis_jobs.sql',
                 '006_news_company_matching.sql', '007_auth_access.sql']:
        await c.execute((DATABASE_ROOT / 'migrations' / file).read_text(encoding='utf-8'))
    value = make_url(dsn).set(drivername='postgresql+asyncpg', database=name).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL', value)
    monkeypatch.setenv('AI_MODE', 'demo')
    return value


def test_seed_guards_idempotency_acl_http_and_provenance(identity_dsn, monkeypatch):
    async def scenario():
        async with isolated_database(identity_dsn) as (c, name):
            value = await setup(c, name, identity_dsn, monkeypatch)
            with pytest.raises(ValueError, match='MARKER'):
                await seed(value, name, PASSWORDS, apply=True)
            await c.execute(f"COMMENT ON DATABASE {name} IS '{MARKER}'")
            assert (await seed(value, name))['state'] == 'PLAN_ONLY'
            assert await c.fetchval('SELECT count(*) FROM companies') == 0
            # Separate connections contend on the same transaction advisory lock.
            results = await asyncio.gather(*(seed(value, name, PASSWORDS, apply=True) for _ in range(3)))
            assert sorted(r['state'] for r in results) == ['CREATED', 'UNCHANGED', 'UNCHANGED']
            assert await c.fetchval('SELECT count(*) FROM companies') == 3
            assert await c.fetchval('SELECT count(*) FROM company_news_analyses') == 3
            assert await c.fetchval('SELECT count(*) FROM auth_news_grants') == 3
            assert await c.fetchval('SELECT count(*) FROM news_analysis_attempts') == 0
            for row in await c.fetch('SELECT login,password_hash FROM auth_users ORDER BY login'):
                assert HASHER.verify(row['password_hash'], PASSWORDS[LOGINS.index(row['login'])])
                assert all(p not in row['password_hash'] for p in PASSWORDS)
            with pytest.raises(ValueError, match='CREDENTIALS'):
                await seed(value, name, ['Another-invented-password', PASSWORDS[1]], apply=True)
            with TestClient(app) as client:
                assert client.get('/api/me').status_code == 401
                assert client.get('/api/companies/DEMO-001').status_code == 401
                assert client.post('/api/auth/login', json={'login': LOGINS[0], 'password': 'wrong'}).status_code == 401
                credentials = []
                for login, password in zip(LOGINS, PASSWORDS):
                    response = client.post('/api/auth/login', json={'login': login, 'password': password})
                    assert response.status_code == 200
                    credentials.append({'Authorization': 'Bearer ' + response.json()['access_token']})
                a, b = credentials
                assert {r['source_id'] for r in client.get('/api/me', headers=a).json()['companies']} == {'DEMO-001', 'DEMO-003'}
                assert client.get('/api/companies/DEMO-001', headers=a).status_code == 200
                empty_profile = client.get('/api/companies/DEMO-003', headers=a).json()
                assert empty_profile['revenue'] is None and empty_profile['revenue_year'] is None
                assert client.get('/api/companies/DEMO-003/insights', headers=a).json() == {'items': [], 'next_cursor': None}
                assert client.get('/api/companies/DEMO-002', headers=a).status_code == 403
                assert client.get('/api/companies/ABSENT', headers=a).status_code == 403
                feed = client.get('/api/companies/DEMO-001/insights', headers=a).json()
                assert len(feed['items']) == 2
                path = '/api/companies/DEMO-001/insights/' + str(feed['items'][0]['insight_id'])
                card = client.get(path, headers=a)
                assert card.status_code == 200
                assert card.json()['sources'][0]['synthetic'] is True
                assert card.json()['sources'][0]['provenance']['publisher'] is None
                assert card.json()['sources'][0]['provenance']['declared_format'] == 'TXT'
                assert card.json()['evidence'][0]['evidence_type'] == 'DOCUMENT'
                assert 'Альфа-Банк' not in card.text
                assert client.get(path, headers=b).status_code == 403
                assert client.get('/api/companies/DEMO-001/insights/999999', headers=a).status_code == 403
                logout = client.post('/api/auth/logout', headers=a)
                assert logout.status_code == 204 and logout.content == b''
                assert client.get('/api/me', headers=a).status_code == 401
                assert client.get('/api/me', headers=b).status_code == 200
            # Sessions are outside fixture ownership. Rerun does not revoke/reset.
            assert (await seed(value, name, PASSWORDS, apply=True))['state'] == 'UNCHANGED'
            await c.execute("UPDATE companies SET name='Changed fixture' WHERE source_id='DEMO-001'")
            with pytest.raises(ValueError, match='FIXTURE_CHANGED'):
                await seed(value, name, PASSWORDS, apply=True)
    asyncio.run(scenario())


def test_seed_rolls_back_and_refuses_populated_database(identity_dsn, monkeypatch):
    async def scenario():
        async with isolated_database(identity_dsn) as (c, name):
            value = await setup(c, name, identity_dsn, monkeypatch)
            await c.execute(f"COMMENT ON DATABASE {name} IS '{MARKER}'")
            with patch('integration_demo.HASHER') as broken:
                broken.hash.side_effect = RuntimeError('Synthetic write failure')
                with pytest.raises(RuntimeError):
                    await seed(value, name, PASSWORDS, apply=True)
            for table in ['companies', 'news_articles', 'analysis_runs', 'insight_evidence', 'auth_users']:
                assert await c.fetchval(f'SELECT count(*) FROM {table}') == 0
            await c.execute("INSERT INTO companies(source_id,name) VALUES ('EXISTING','Synthetic existing')")
            with pytest.raises(ValueError, match='EMPTY_DATABASE'):
                await seed(value, name, PASSWORDS, apply=True)
            assert await c.fetchval('SELECT count(*) FROM companies') == 1
    asyncio.run(scenario())


@pytest.mark.parametrize('case', ['txt', 'verified_pdf', 'verified_pdf_unknown_publisher'])
def test_provenance_persisted_and_legacy_history_not_rewritten(identity_dsn, monkeypatch, bundle_factory, case):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from repositories.company_analysis_repository import CompanyAnalysisRepository
    from repositories.evidence_repository import EvidenceRepository
    from schemas.persisted_analysis import PersistableAnalysis

    async def scenario():
        async with isolated_database(identity_dsn) as (c, name):
            value = await setup(c, name, identity_dsn, monkeypatch)
            await c.execute(f"COMMENT ON DATABASE {name} IS '{MARKER}'")
            await seed(value, name, PASSWORDS, apply=True)
            raw = bundle_factory().model_dump()
            for fragment, source in zip(raw['evidence'], raw['analysis']['sources']):
                fragment['document'] = source['document'] = 'invented-fragment.txt' if case == 'txt' else 'verified-synthetic.pdf'
            bundle = PersistableAnalysis.model_validate(raw)
            company = await c.fetchval("SELECT id FROM companies WHERE source_id='DEMO-001'")
            news = await c.fetchval('SELECT min(id) FROM news_articles')
            run = await c.fetchval("INSERT INTO analysis_runs(company_id,analysis_type,status) VALUES ($1,'NEWS','COMPLETED') RETURNING id", company)
            engine = create_async_engine(value, poolclass=NullPool)
            try:
                async with async_sessionmaker(engine)() as s, s.begin():
                    insight = await CompanyAnalysisRepository(s).create(run, company, news, bundle)
                    for fragment in bundle.evidence:
                        await EvidenceRepository(s).create(insight, fragment)
            finally:
                await engine.dispose()
            import json
            stored = json.loads(await c.fetchval('SELECT source_snapshot::text FROM company_news_analyses WHERE id=$1', insight))
            assert stored[0]['provenance']['publisher'] is None
            assert stored[0]['provenance']['declared_format'] == ('TXT' if case == 'txt' else 'PDF')
            assert await c.fetchval('SELECT bool_and(evidence_type=\'DOCUMENT\') FROM insight_evidence WHERE company_news_analysis_id=$1', insight)
            if case != 'txt':
                # Synthetic fixture represents a trusted historical curation record;
                # no real documents are loaded or declared verified by the service.
                for source in stored:
                    source['provenance'].update(format_verified=True,
                        publisher='Synthetic independent publisher' if case == 'verified_pdf' else None)
                await c.execute('UPDATE company_news_analyses SET source_snapshot=$1::jsonb WHERE id=$2', json.dumps(stored), insight)
            await c.execute("UPDATE insight_evidence SET evidence_type='PDF' WHERE company_news_analysis_id=$1", insight)
            with TestClient(app) as client:
                token = client.post('/api/auth/login', json={'login': LOGINS[0], 'password': PASSWORDS[0]}).json()['access_token']
                card = client.get(f'/api/companies/DEMO-001/insights/{insight}', headers={'Authorization': 'Bearer ' + token})
                assert card.status_code == 200
                assert card.json()['evidence'][0]['evidence_type'] == ('DOCUMENT' if case == 'txt' else 'PDF')
                assert card.json()['evidence'][0]['text'] == bundle.evidence[0].text
                assert card.json()['sources'] == stored
                assert 'Альфа-Банк' not in card.text
            assert await c.fetchval("SELECT bool_and(evidence_type='PDF') FROM insight_evidence WHERE company_news_analysis_id=$1", insight)
    asyncio.run(scenario())
