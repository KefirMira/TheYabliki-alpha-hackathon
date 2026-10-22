from datetime import date
import re

from sqlalchemy import insert

from repositories.analysis_tables import insight_evidence


def complete_date(raw: str | None) -> date | None:
    if raw is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


class EvidenceRepository:
    def __init__(self, session):
        self.session = session

    async def create(self, insight_id: int, fragment) -> int:
        result = await self.session.execute(insert(insight_evidence).values(
            company_news_analysis_id=insight_id, evidence_type="PDF",
            evidence_text=fragment.text, document_name=fragment.document,
            document_page=fragment.page, chunk_id=fragment.chunk_id,
            document_date=complete_date(fragment.date),
        ).returning(insight_evidence.c.id))
        return result.scalar_one()
