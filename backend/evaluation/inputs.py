"""Same retrieval and context layout as production, with no SDK import."""
from evaluation.prompts import DOCUMENT_DATES, assert_sources_unchanged, company_question, rag_messages
from schemas.company import CompanyProfile
from services.search_service import search_chunks


def prepare(case, chunks, *, profile_model=CompanyProfile):
    assert_sources_unchanged()
    company = profile_model.model_validate(case['company'])
    selected = search_chunks(query=case['news'], chunks=chunks, top_k=3)
    evidence, parts = [], []
    for index, chunk in enumerate(selected, 1):
        name = chunk['source']
        date = DOCUMENT_DATES.get(name, 'Дата не указана')
        parts.append(f"[Источник {index}]\nДокумент: {name}\nДата документа: {date}\n"
                     f"Страница: {chunk['page']}\nФрагмент: {chunk.get('chunk_id', 1)}\nТекст:\n{chunk['text']}")
        evidence.append({'id': index, 'document': name, 'date': DOCUMENT_DATES.get(name),
                         'page': chunk['page'], 'chunk_id': chunk.get('chunk_id', 1),
                         'score': round(chunk['score'], 4), 'text': chunk['text']})
    return {'messages': rag_messages(company_question(company, case['news']), '\n\n'.join(parts)),
            'evidence': evidence}


def synthetic_chunks():
    return [{'source': 'synthetic-evaluation.txt', 'page': 1, 'chunk_id': 1,
             'text': 'Синтетическая макроэкономическая аналитика. Инфляция и ключевая ставка влияют '
                     'на кредит и потребление. Цена золота и стали может изменяться. Это вымышленная '
                     'тестовая запись, не подтверждение реальных событий или финансовых прогнозов.'}]
