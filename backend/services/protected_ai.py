"""Per-task policy; does not alter SDK defaults of legacy endpoints."""
import asyncio
from contextvars import ContextVar

protected_call = ContextVar('protected_saved_news_analysis', default=False)
PROTECTED_TIMEOUT_SECONDS = 150
SDK_TIMEOUT_SECONDS = 120


async def invoke(analyzer, **kwargs):
    token = protected_call.set(True)
    try:
        async with asyncio.timeout(PROTECTED_TIMEOUT_SECONDS):
            return await analyzer(**kwargs)
    finally:
        protected_call.reset(token)
