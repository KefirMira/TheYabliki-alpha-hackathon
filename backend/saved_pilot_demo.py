"""Offline import of ONE pinned synthetic historical result. Never dispatches SDK."""
import argparse
import asyncio
import copy
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from company_import.storage import target_url
from db.diagnostics import database_error_code
from repositories.analysis_run_repository import AnalysisRunRepository
from repositories.company_analysis_repository import CompanyAnalysisRepository
from repositories.evidence_repository import EvidenceRepository
from schemas.analysis import AnalysisContent
from schemas.persisted_analysis import PersistableAnalysis
from services.auth_service import HASHER, verify_password
from services.synthetic_gateway_input import canonical, fixture, make_input, verify_input

VERSION = 'saved-llm-pilot-v1'
MARKER = 'pulse:isolated-saved-pilot-demo:v1'
LOGIN = 'synthetic-pilot-viewer'
ARTIFACT = Path(__file__).with_name('fixtures') / 'saved_llm_pilot_v1.json'
ARTIFACT_SHA256 = '5c75a2d975712f20303c065adaf64d69337d1812cc6738aa49cc23a2c14a243f'
MANIFEST = '_saved_pilot_demo'


def approved():
    raw = ARTIFACT.read_bytes()
    if len(raw) > 100_000:
        raise ValueError('PILOT_ARTIFACT_TOO_LARGE')
    data = json.loads(raw)
    if hashlib.sha256(canonical(data).encode()).hexdigest() != ARTIFACT_SHA256:
        raise ValueError('PILOT_ARTIFACT_CHANGED')
    f = fixture()
    if verify_input(make_input((1, 2))) != data['metadata']['dto_sha256']:
        raise ValueError('PILOT_DTO_CHANGED')
    content = AnalysisContent.model_validate_json(data['content'])
    evidence = []
    for n, source in enumerate(data['sources'], 1):
        c = f['corpus'][n - 1]
        if (source['id'], source['document'], source['page']) != (n, c['source'], c['page']):
            raise ValueError('PILOT_SOURCE_MISMATCH')
        evidence.append(dict(id=n, document=c['source'], page=c['page'], chunk_id=c['chunk_id'],
                             date=None, score=source['score'], text=c['text']))
    if len(evidence) != 2:
        raise ValueError('PILOT_EVIDENCE_REQUIRED')
    bundle = PersistableAnalysis.model_validate({
        'analysis': dict(company_id=f['source_id'], news=f['news'], **content.model_dump(),
                         sources=data['sources'], validation=data['validation']),
        'evidence': evidence, 'model_name': data['metadata']['model'],
        'prompt_version': 'synthetic-gateway-v1',
        'financial_review': data['financial_review'], 'orchestration': data['orchestration'],
    })
    counts = {key: sum(f.disposition == key for f in bundle.financial_review.findings)
              for key in ['UNKNOWN', 'NEEDS_REVIEW', 'CONFIRMED_ERROR']}
    if counts != {'UNKNOWN': 16, 'NEEDS_REVIEW': 4, 'CONFIRMED_ERROR': 0}:
        raise ValueError('PILOT_REVIEW_MISMATCH')
    return data, bundle


async def fingerprint(c):
    digest = hashlib.sha256()
    tables = (await c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))).scalars()
    for table in tables:
        if table == 'auth_sessions':
            continue  # Ordinary login/logout must not invalidate the imported snapshot.
        name = c.dialect.identifier_preparer.quote(table)
        projection = "to_jsonb(t) - 'source_data' || jsonb_build_object('source_data',source_data - '_saved_pilot_demo')" if table == 'companies' else 'to_jsonb(t)'
        value = await c.scalar(text(f"SELECT coalesce(jsonb_agg(v ORDER BY v::text),'[]')::text FROM (SELECT {projection} v FROM public.{name} t) q"))
        digest.update(table.encode())
        digest.update(value.encode())
    return digest.hexdigest()


async def import_pilot(value, expected_database, password=None, *, apply=False):
    url = target_url(value, expected_database)
    data, bundle = approved()
    if apply and (not isinstance(password, str) or not 12 <= len(password) <= 256):
        raise ValueError('PILOT_PASSWORD_REQUIRED')
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True,
                                 connect_args={'timeout': 5, 'command_timeout': 30})
    try:
        async with engine.begin() as c:
            await c.execute(text('SELECT pg_advisory_xact_lock(1251001)'))
            marker = await c.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"))
            if marker != MARKER:
                raise ValueError('ISOLATED_PILOT_MARKER_REQUIRED')
            manifest = await c.scalar(text("SELECT source_data->'_saved_pilot_demo' FROM companies WHERE source_id=:source"),
                                      {'source': bundle.analysis.company_id})
            if manifest is not None:
                if manifest != {'version': VERSION, 'artifact_sha256': ARTIFACT_SHA256, 'sha256': await fingerprint(c)}:
                    raise ValueError('PILOT_SNAPSHOT_CHANGED')
                if apply:
                    encoded = await c.scalar(text('SELECT password_hash FROM auth_users WHERE login=:login'), {'login': LOGIN})
                    if not await asyncio.to_thread(verify_password, encoded, password):
                        raise ValueError('PILOT_CREDENTIALS_DIFFER')
                return {'state': 'UNCHANGED', 'synthetic': True, 'insights': 1, 'evidence': 2, 'new_llm_requests': 0}
            tables = (await c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars()
            for table in tables:
                quoted = c.dialect.identifier_preparer.quote(table)
                if await c.scalar(text(f'SELECT EXISTS(SELECT 1 FROM public.{quoted})')):
                    raise ValueError('EMPTY_PILOT_DATABASE_REQUIRED')
            if not apply:
                return {'state': 'PLAN_ONLY', 'synthetic': True, 'insights': 1, 'evidence': 2, 'new_llm_requests': 0}
            f = fixture()
            company = await c.scalar(text("""INSERT INTO companies(source_id,name,industry,source_data)
                VALUES (:source,:source,:industry,CAST(:data AS jsonb)) RETURNING id"""),
                {'source': f['source_id'], 'industry': f['context']['facts']['industry']['value'],
                 'data': canonical({'approved_synthetic_context': f['context']})})
            news = await c.scalar(text("""INSERT INTO news_articles(title,content,input_kind,source_name)
                VALUES ('Синтетический пример: сохранение ключевой ставки',:news,'MANUAL','synthetic-saved-llm-pilot') RETURNING id"""),
                {'news': f['news']})
            user = uuid5(NAMESPACE_URL, VERSION + ':' + LOGIN)
            encoded = await asyncio.to_thread(HASHER.hash, password)
            await c.execute(text('INSERT INTO auth_users(id,login,password_hash) VALUES (:id,:login,:hash)'),
                            {'id': user, 'login': LOGIN, 'hash': encoded})
            await c.execute(text('INSERT INTO auth_user_companies(user_id,company_id,can_analyze) VALUES (:user,:company,false)'),
                            {'user': user, 'company': company})
            await c.execute(text('INSERT INTO auth_news_grants(user_id,news_id) VALUES (:user,:news)'), {'user': user, 'news': news})
            # Existing repositories share the import transaction. No job/attempt or paid path.
            async with async_sessionmaker(bind=c, expire_on_commit=False, join_transaction_mode='create_savepoint')() as session, session.begin():
                run = await AnalysisRunRepository(session).start(company)
                insight = await CompanyAnalysisRepository(session).create(run, company, news, bundle.model_copy(update={'orchestration': None}))
                for fragment in bundle.evidence:
                    await EvidenceRepository(session).create(insight, fragment)
                await AnalysisRunRepository(session).finish(run, 'COMPLETED',
                    model_name=bundle.model_name, prompt_version=bundle.prompt_version)
                await session.flush()
            # Preserve historical trace exactly; do not rewrite paid_calls=1 as an import SDK call.
            sources = [{**s.model_dump(exclude={'text'}), 'synthetic': True,
                        'provenance': {'declared_format': 'TXT', 'format_verified': False,
                                       'publisher': None, 'attribution_status': 'UNKNOWN'}}
                       for s in bundle.evidence]
            validation = bundle.analysis.validation.model_dump()
            validation.update(financial_review=copy.deepcopy(data['financial_review']),
                              orchestration=copy.deepcopy(data['orchestration']),
                              saved_pilot_import={**data['metadata'], 'version': VERSION, 'synthetic': True,
                                'artifact_sha256': ARTIFACT_SHA256, 'new_llm_requests': 0,
                                'imported_at': datetime.now(timezone.utc).isoformat()})
            await c.execute(text("""UPDATE company_news_analyses SET validation=CAST(:validation AS jsonb),
                    source_snapshot=CAST(:sources AS jsonb) WHERE id=:id"""),
                    {'id': insight, 'validation': canonical(validation), 'sources': canonical(sources)})
            # Run timestamps describe the import, not a new generation. UI labels imported records separately.
            manifest = canonical({'version': VERSION, 'artifact_sha256': ARTIFACT_SHA256, 'sha256': await fingerprint(c)})
            await c.execute(text("UPDATE companies SET source_data=source_data || jsonb_build_object('_saved_pilot_demo',CAST(:manifest AS jsonb)) WHERE id=:id"),
                            {'id': company, 'manifest': manifest})
            return {'state': 'CREATED', 'synthetic': True, 'insights': 1, 'evidence': 2, 'new_llm_requests': 0}
    finally:
        await engine.dispose()


class BackendDatabaseCheckFailed(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


async def verify_backend_connection(value, expected_database):
    """Read-only TCP probe of Docker service, using the SAME credentials as seed/backend.

    Writes still use the existing guarded loopback importer. Docker's loopback
    trust must not hide a wrong password on an already initialized volume.
    """
    url = target_url(value, expected_database)
    if not re.fullmatch(r'[a-fA-F0-9]{32,128}', url.password or ''):
        raise BackendDatabaseCheckFailed('DATABASE_PASSWORD_FORMAT_INVALID')
    engine = create_async_engine(url.set(host='postgres'), poolclass=NullPool,
        hide_parameters=True, connect_args={'timeout': 5, 'command_timeout': 5})
    try:
        async with engine.begin() as connection:
            await connection.execute(text('SET TRANSACTION READ ONLY'))
            result = (await connection.execute(text("""SELECT current_database() AS name,
                shobj_description(oid, 'pg_database') AS marker
                FROM pg_database WHERE datname=current_database()"""))).mappings().one()
            if result['name'] != expected_database or result['marker'] != MARKER:
                raise BackendDatabaseCheckFailed('DATABASE_ISOLATION_MARKER_MISMATCH')
    except BackendDatabaseCheckFailed:
        raise
    except Exception as error:
        raise BackendDatabaseCheckFailed(database_error_code(error)) from None
    finally:
        await engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-isolated', action='store_true')
    parser.add_argument('--password-env', action='store_true',
                        help='Read SAVED_PILOT_DEMO_PASSWORD for isolated non-interactive seed')
    parser.add_argument('--verify-backend-connection', action='store_true',
                        help='Verify Docker TCP authentication before importing')
    args = parser.parse_args(argv)
    try:
        if args.apply and not args.confirm_isolated:
            raise ValueError('CONFIRM_ISOLATED_REQUIRED')
        password = None
        if args.apply:
            if args.password_env:
                password = os.environ.get('SAVED_PILOT_DEMO_PASSWORD', '')
                if not 12 <= len(password) <= 256 or password.startswith('REPLACE_'):
                    raise ValueError('PILOT_PASSWORD_REQUIRED')
            else:
                password = getpass.getpass(f'{LOGIN} password (12–256 characters): ')
                if password != getpass.getpass('Repeat password: '):
                    raise ValueError('PASSWORD_CONFIRMATION_MISMATCH')
        if args.verify_backend_connection:
            asyncio.run(verify_backend_connection(os.environ.get('SAVED_PILOT_DATABASE_URL', ''),
                                                  args.expected_database))
        result = asyncio.run(import_pilot(os.environ.get('SAVED_PILOT_DATABASE_URL', ''),
                            args.expected_database, password, apply=args.apply))
        print(json.dumps(result))
        return 0
    except BackendDatabaseCheckFailed as error:
        print(json.dumps({'code': 'SAVED_PILOT_BACKEND_DATABASE_CHECK_FAILED',
                          'reason': error.code}))
        return 1
    except Exception:
        # No exception/DSN/SQL/body/password serialization.
        print(json.dumps({'code': 'SAVED_PILOT_IMPORT_FAILED_VERIFY_TARGET_AND_ARTIFACT'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
