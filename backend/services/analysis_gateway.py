"""Delay legacy AI imports until an analysis is explicitly requested."""


async def analyze_for_company(*, news, company):
    from services.personalization_service import analyze_for_company as analyze

    return await analyze(news=news, company=company)


async def analyze_with_rag(*, question, search_query, **options):
    from services.rag_service import analyze_with_rag as analyze

    return await analyze(question=question, search_query=search_query, **options)
