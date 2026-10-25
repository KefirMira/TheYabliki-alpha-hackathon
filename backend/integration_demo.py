"""Explicit synthetic seed for EMPTY, marked, loopback test databases only.

No registration endpoint, default password, credential reset or implicit grants.
"""
import argparse
import asyncio
import getpass
import hashlib
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from company_import.storage import target_url
from services.auth_service import HASHER, verify_password

MARKER = 'pulse:isolated-integration-demo:v1'
VERSION = 'integration-demo-v1'
LOGINS = ('synthetic-demo-a', 'synthetic-demo-b')
TABLES = ('companies', 'company_verified_names', 'news_articles', 'analysis_runs',
          'company_news_analyses', 'insight_evidence', 'auth_users',
          'auth_user_companies', 'auth_news_grants')


async def fingerprint(connection):
    digest = hashlib.sha256()
    for table in TABLES:
        # Fixed allowlist, never interpolates operator input. Exclude only the
        # checksum itself; passwords are hashed, never returned or logged.
        expression = "to_jsonb(t) - 'source_data' || jsonb_build_object('source_data',source_data - '_integration_demo')" if table == 'companies' else 'to_jsonb(t)'
        rows = await connection.scalar(text(
            f"SELECT coalesce(jsonb_agg(v ORDER BY v::text),'[]')::text FROM (SELECT {expression} v FROM public.{table} t) q"))
        digest.update(table.encode())
        digest.update(rows.encode())
    return digest.hexdigest()


async def seed(value, expected_database, passwords=None, *, apply=False):
    url = target_url(value, expected_database)
    if apply and (passwords is None or len(passwords) != 2 or
                  any(not isinstance(p, str) or not 12 <= len(p) <= 256 for p in passwords)):
        raise ValueError('SYNTHETIC_PASSWORDS_REQUIRED')
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True,
                                connect_args={'timeout': 5, 'command_timeout': 30})
    try:
        async with engine.begin() as c:
            await c.execute(text("SELECT pg_advisory_xact_lock(1241001)"))
            marker = await c.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"))
            if marker != MARKER:
                raise ValueError('ISOLATED_DEMO_MARKER_REQUIRED')
            manifest = await c.scalar(text("SELECT source_data->'_integration_demo' FROM companies WHERE source_id='DEMO-001'"))
            if manifest is not None:
                if manifest != {'version': VERSION, 'sha256': await fingerprint(c)}:
                    raise ValueError('DEMO_FIXTURE_CHANGED')
                if apply:
                    for login, password in zip(LOGINS, passwords):
                        encoded = await c.scalar(text('SELECT password_hash FROM auth_users WHERE login=:login'), {'login': login})
                        if not await asyncio.to_thread(verify_password, encoded, password):
                            raise ValueError('EXISTING_CREDENTIALS_DIFFER')
                return {'synthetic': True, 'state': 'UNCHANGED', 'companies': 3, 'users': 2, 'insights': 3}
            # Refuse all populated public tables, including import snapshots/jobs.
            tables = (await c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars()
            for table in tables:
                quoted = c.dialect.identifier_preparer.quote(table)
                if await c.scalar(text(f'SELECT EXISTS(SELECT 1 FROM public.{quoted})')):
                    raise ValueError('EMPTY_DATABASE_REQUIRED')
            if not apply:
                return {'synthetic': True, 'state': 'PLAN_ONLY', 'companies': 3, 'users': 2, 'insights': 3}
            sql = Path(__file__).with_name('fixtures').joinpath('integration_demo.sql').read_text(encoding='utf-8')
            # asyncpg supports the fixed multi-statement fixture as one execution.
            # Strip transaction boundaries: ownership belongs to engine.begin().
            sql = sql.replace('BEGIN;', '', 1).rsplit('COMMIT;', 1)[0]
            raw = await c.get_raw_connection()
            await raw.driver_connection.execute(sql)
            for index, (login, password) in enumerate(zip(LOGINS, passwords)):
                user = uuid5(NAMESPACE_URL, VERSION + ':' + login)
                encoded = await asyncio.to_thread(HASHER.hash, password)
                await c.execute(text('INSERT INTO auth_users(id,login,password_hash) VALUES (:id,:login,:hash)'),
                                {'id': user, 'login': login, 'hash': encoded})
                sources = ['DEMO-001', 'DEMO-003'] if index == 0 else ['DEMO-002']
                for source in sources:
                    await c.execute(text('INSERT INTO auth_user_companies(user_id,company_id,can_analyze) SELECT :user,id,false FROM companies WHERE source_id=:source'),
                                    {'user': user, 'source': source})
                await c.execute(text('''INSERT INTO auth_news_grants(user_id,news_id)
                    SELECT DISTINCT CAST(:user AS uuid),a.news_id FROM company_news_analyses a
                    JOIN auth_user_companies m ON m.company_id=a.company_id WHERE m.user_id=CAST(:user AS uuid)'''), {'user': user})
            manifest = json.dumps({'version': VERSION, 'sha256': await fingerprint(c)})
            await c.execute(text("UPDATE companies SET source_data=jsonb_build_object('_integration_demo',CAST(:manifest AS jsonb)) WHERE source_id='DEMO-001'"), {'manifest': manifest})
            return {'synthetic': True, 'state': 'CREATED', 'companies': 3, 'users': 2, 'insights': 3}
    finally:
        await engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-isolated', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.apply and not args.confirm_isolated:
            raise ValueError('CONFIRM_ISOLATED_REQUIRED')
        passwords = None
        if args.apply:
            passwords = []
            for login in LOGINS:
                password = getpass.getpass(f'{login} password (12–256 characters): ')
                if password != getpass.getpass('Repeat password: '):
                    raise ValueError('PASSWORD_CONFIRMATION_MISMATCH')
                passwords.append(password)
        result = asyncio.run(seed(os.environ.get('INTEGRATION_DEMO_DATABASE_URL', ''), args.expected_database, passwords, apply=args.apply))
        print(json.dumps(result))
        return 0
    except Exception:
        # Never serialize exceptions/DSNs, submitted passwords or SQL parameters.
        print(json.dumps({'code': 'DEMO_SEED_FAILED_VERIFY_TARGET_AND_FIXTURE'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
