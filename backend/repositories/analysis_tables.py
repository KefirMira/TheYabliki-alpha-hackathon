"""Core projections of PR #2 tables. No metadata.create_all or migrations."""

from sqlalchemy import BigInteger, Date, DateTime, String, column, table
from sqlalchemy.dialects.postgresql import JSONB


def projection(name, *columns):
    return table(name, column("id", BigInteger), *columns, schema="public")


news_articles = projection(
    "news_articles", column("title", String), column("content", String),
    column("input_kind", String), column("content_hash", String),
    column("url", String), column("source_name", String), column("source_id", String),
    column("published_at", DateTime(timezone=True)), column("language", String),
)
analysis_runs = projection(
    "analysis_runs", column("company_id", BigInteger), column("analysis_type", String),
    column("status", String), column("started_at", DateTime(timezone=True)),
    column("finished_at", DateTime(timezone=True)), column("model_name", String),
    column("prompt_version", String), column("result_summary", String), column("error_message", String),
)
company_news_analyses = projection(
    "company_news_analyses", column("analysis_run_id", BigInteger), column("company_id", BigInteger),
    column("news_id", BigInteger), column("relevance_level", String), column("impact_summary", String),
    column("risks", JSONB), column("opportunities", JSONB), column("recommendations", JSONB),
    column("validation", JSONB), column("source_snapshot", JSONB),
)
insight_evidence = projection(
    "insight_evidence", column("company_news_analysis_id", BigInteger),
    column("evidence_type", String), column("evidence_text", String), column("document_name", String),
    column("document_page", BigInteger), column("chunk_id", BigInteger), column("document_date", Date),
)
