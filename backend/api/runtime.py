"""Demo is read-only with respect to AI, even if real credentials are present."""
from fastapi import HTTPException
from settings import ai_disabled_reason


def require_ai_enabled():
    reason = ai_disabled_reason()
    if reason:
        raise HTTPException(503, detail={
            "code": reason,
            "message": "AI-анализ недоступен в demo-режиме. Используйте готовые синтетические инсайты.",
        })
