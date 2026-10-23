"""OpenAPI-only models: do not transform existing error or legacy responses."""
from typing import Literal
from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    code: str
    message: str
    run_id: int | None = None


class APIError(BaseModel):
    detail: ErrorDetail


class ValidationItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    loc: list[str | int]
    msg: str
    type: str


class ValidationResponse(BaseModel):
    detail: list[ValidationItem] | ErrorDetail | str


class LegacyError(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessChecks(BaseModel):
    rag: bool
    llm_config: bool
    database: bool


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


class RAGSource(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    document: str
    date: str | None
    page: int
    chunk_id: str | int | None
    score: float


class RAGResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    analysis: str
    sources: list[RAGSource]


def errors(**descriptions):
    return {int(status): {"model": ValidationResponse if status == "422" else APIError,
                          "description": description}
            for status, description in descriptions.items()}


ANALYSIS_ERRORS = errors(**{
    "404": "COMPANY_NOT_FOUND; для анализа сохранённой новости также NEWS_NOT_FOUND; запуск не создаётся",
    "422": "Ошибка валидации; для сохранённой новости также NEWS_CONTENT_UNAVAILABLE",
    "502": "AI_ANALYSIS_FAILED; run_id и статус FAILED, если запись статуса подтверждена",
    "503": "AI_DISABLED_IN_DEMO / DATABASE_UNAVAILABLE / ошибка сохранения / неопределённый статус запуска",
})
