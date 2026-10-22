"""Async database lifecycle. Schema is owned by SQL migrations, never ORM DDL."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "DATABASE_UNAVAILABLE", "message": "База данных недоступна"},
    )


@asynccontextmanager
async def database_lifespan(app: FastAPI):
    url = os.environ.get("DATABASE_URL")
    engine = None
    app.state.company_sessions = None
    if url:
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        engine = create_async_engine(
            url,
            pool_pre_ping=True,
            connect_args={"timeout": 5, "command_timeout": 5},
            hide_parameters=True,
        )
        app.state.company_sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield
    finally:
        if engine is not None:
            await engine.dispose()
        app.state.company_sessions = None


async def get_company_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessions = getattr(request.app.state, "company_sessions", None)
    if sessions is None:
        raise unavailable()
    try:
        async with sessions() as session:
            yield session
    except (SQLAlchemyError, OSError, TimeoutError) as error:
        # Never expose DSNs, credentials or SQL parameters in the API response.
        raise unavailable() from error


def get_session_factory(request: Request):
    """A factory, not a request-long transaction: AI must run outside a session."""
    sessions = getattr(request.app.state, "company_sessions", None)
    if sessions is None:
        raise unavailable()
    return sessions
