"""Individual synthetic session in a UUID-owned test database, no auth overrides."""
from contextlib import asynccontextmanager
from uuid import uuid4
import secrets
from services.auth_service import HASHER, token_digest
from test_job_claim_integration import job_database as original_database
from test_news_identity_migration import DATABASE_ROOT


async def add_actor(connection, news, companies=('SYNTH-COMPANY-A',), grant=True):
    user = uuid4()
    token = secrets.token_urlsafe(32)
    await connection.execute('INSERT INTO auth_users(id,login,password_hash) VALUES ($1,$2,$3)',
        user,'synthetic-'+user.hex,HASHER.hash(secrets.token_urlsafe(24)))
    await connection.execute("INSERT INTO auth_sessions(user_id,token_hash,expires_at) VALUES ($1,$2,now()+interval '1 hour')",user,token_digest(token))
    for source in companies:
        await connection.execute('INSERT INTO auth_user_companies(user_id,company_id,can_analyze) SELECT $1,id,true FROM companies WHERE source_id=$2',user,source)
    if grant:
        await connection.execute('INSERT INTO auth_news_grants(user_id,news_id) VALUES ($1,$2)',user,news)
    return user,token


@asynccontextmanager
async def job_database(dsn):
    async with original_database(dsn) as (engine,sessions,connection,news):
        await connection.execute((DATABASE_ROOT/'migrations/007_auth_access.sql').read_text(encoding='utf-8'))
        _,token = await add_actor(connection,news,('SYNTH-COMPANY-A','SYNTH-COMPANY-B'))
        sessions.synthetic_test_token = token
        yield engine,sessions,connection,news
