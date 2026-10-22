from datetime import datetime, timezone

from sqlalchemy import insert, update

from repositories.analysis_tables import analysis_runs


class AnalysisRunRepository:
    def __init__(self, session):
        self.session = session

    async def start(self, company_id: int) -> int:
        result = await self.session.execute(insert(analysis_runs).values(
            company_id=company_id, analysis_type="NEWS", status="RUNNING",
            started_at=datetime.now(timezone.utc),
        ).returning(analysis_runs.c.id))
        return result.scalar_one()

    async def finish(self, run_id: int, status: str, **values):
        result = await self.session.execute(update(analysis_runs).where(
            analysis_runs.c.id == run_id, analysis_runs.c.status == "RUNNING",
        ).values(status=status, finished_at=datetime.now(timezone.utc), **values))
        if result.rowcount != 1:
            raise RuntimeError("Run is missing or already finished")
