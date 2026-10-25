from sqlalchemy import insert

from repositories.analysis_tables import company_news_analyses
from services.source_provenance import source_metadata


class CompanyAnalysisRepository:
    def __init__(self, session):
        self.session = session

    async def create(self, run_id, company_id, news_id, bundle) -> int:
        analysis = bundle.analysis
        validation = analysis.validation.model_dump(mode="json")
        if bundle.financial_review is not None:
            # Existing JSONB field, in the same transaction as insight/evidence/status.
            validation['financial_review'] = bundle.financial_review.model_dump(mode='json')
        if bundle.orchestration is not None:
            validation['orchestration'] = bundle.orchestration.committed().model_dump(mode='json')
        result = await self.session.execute(insert(company_news_analyses).values(
            analysis_run_id=run_id, company_id=company_id, news_id=news_id,
            relevance_level=analysis.relevance, impact_summary=analysis.summary,
            risks=analysis.risks, opportunities=analysis.opportunities,
            recommendations=analysis.recommendations,
            validation=validation,
            source_snapshot=[{**item.model_dump(mode="json", exclude={"text"}),
                              'provenance': source_metadata(item.document)} for item in bundle.evidence],
        ).returning(company_news_analyses.c.id))
        return result.scalar_one()
