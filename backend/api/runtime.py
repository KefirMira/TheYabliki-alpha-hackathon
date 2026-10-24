"""Demo is read-only with respect to AI, even if real credentials are present."""
from fastapi import HTTPException
from settings import execution_mode


def require_ai_enabled():
    if execution_mode() == "demo":
        raise HTTPException(503, detail={
            "code": "AI_DISABLED_IN_DEMO",
            "message": "AI-анализ недоступен в demo-режиме. Используйте готовые синтетические инсайты.",
        })
