"""Use existing isolated PostgreSQL/actor fixture; external transport remains absent."""
import asyncio
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from synthetic_actor_fixture import job_database
from test_news_identity_migration import identity_dsn
from test_synthetic_execution_integration import seed
from services.auth_service import token_digest
from services.external_context_policy import CompanyContextBuilder, ExternalContextPolicy, PolicyDenied

pytestmark = pytest.mark.integration


def test_live_acl_and_default_denial_with_real_postgres(identity_dsn):
    async def scenario():
        async with job_database(identity_dsn) as (_, sessions, c, news):
            await seed(c, news)
            builder = CompanyContextBuilder(sessions)
            token_hash = token_digest(sessions.synthetic_test_token)
            ctx = await builder.build(token_hash, "SYNTH-COMPANY-A", news)
            assert ctx.scope and ctx.rag == ()
            with pytest.raises(PolicyDenied):
                ExternalContextPolicy().prepare(ctx)
            with pytest.raises(HTTPException) as foreign:
                await builder.build(token_hash, "OTHER-COMPANY", news)
            assert foreign.value.status_code == 403
            await c.execute("UPDATE auth_sessions SET revoked_at=clock_timestamp()")
            with pytest.raises(HTTPException) as revoked:
                await builder.build(token_hash, "SYNTH-COMPANY-A", news)
            assert revoked.value.status_code == 401
            assert await c.fetchval("SELECT count(*) FROM news_analysis_attempts") == 0
    asyncio.run(scenario())
