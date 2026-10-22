from sqlalchemy import insert

from repositories.analysis_tables import company_news_analyses


class CompanyAnalysisRepository:
    def __init__(self, session):
        self.session = session

    async def create(self, run_id, company_id, news_id, bundle) -> int:
        analysis = bundle.analysis
        result = await self.session.execute(insert(company_news_analyses).values(
            analysis_run_id=run_id, company_id=company_id, news_id=news_id,
            relevance_level=analysis.relevance, impact_summary=analysis.summary,
            risks=analysis.risks, opportunities=analysis.opportunities,
            recommendations=analysis.recommendations,
            validation=analysis.validation.model_dump(mode="json"),
            source_snapshot=[item.model_dump(mode="json", exclude={"text"}) for item in bundle.evidence],
        ).returning(company_news_analyses.c.id))
        return result.scalar_one()
