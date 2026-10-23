"""Verbatim production prompts. No production service or prompt is changed.
Source drift blocks evaluation; BOM/newlines normalized across Windows/Linux.
"""
from pathlib import Path
import hashlib

SOURCE_HASHES = {'rag_service.py': '7317a9fffc5697ab91afa8245398c73df6dabd962d8e972af66884c5f39c096d', 'personalization_service.py': '1f26aeb10b1b5dc874520707a06f0d6d576acf03d0585e6c641d930656499bf8'}
DOCUMENT_DATES = {'ALFA_Russian_Steels_1К21PreviewUpdate_15Apr2021.pdf': '2021-04-15', 'FI_Strategy_3Q26_22072026.pdf': '2026-07-22', 'Gold_digest_August26.pdf': '2026-08', 'Inflation_tracker_02.pdf': '2026-09-02', 'policy_rate.pdf': '2026-09-11', 'Бонд_Бриф_14092026.pdf': '2026-09-14'}

def assert_sources_unchanged():
    base = Path(__file__).resolve().parents[1] / "services"
    for name, expected in SOURCE_HASHES.items():
        actual = hashlib.sha256((base / name).read_text(encoding="utf-8-sig").encode()).hexdigest()
        if actual != expected:
            raise ValueError("PRODUCTION_PROMPT_DRIFT")

def company_question(company, news):
    company_data = company.model_dump_json(indent=2, exclude_none=True)
    return f'\nПроанализируй влияние новости на компанию.\n\nПРОФИЛЬ КОМПАНИИ:\n{company_data}\n\nНОВОСТЬ:\n{news}\n\nВерни только корректный JSON-объект.\nНе добавляй Markdown, пояснения или текст вне JSON.\n\nСтруктура JSON:\n{{\n    "relevance": "high",\n    "summary": "Краткое описание влияния новости",\n    "risks": [\n        "Риск 1",\n        "Риск 2"\n    ],\n    "opportunities": [\n        "Возможность 1"\n    ],\n    "recommendations": [\n        "Рекомендация 1"\n    ]\n}}\n\nПравила:\n- relevance: только high, medium, low или unknown.\n- summary: 1-3 предложения.\n- risks: список возможных рисков.\n- opportunities: список возможных возможностей.\n- recommendations: конкретные действия для компании.\n- Если нет обоснованных пунктов, используй пустой список.\n- Не выдумывай отсутствующие данные.\n- Разделяй подтверждённые факты и предположения.\n- Не делай вывод об экспорте по региону регистрации.\n- Нулевая кредитная экспозиция не означает\n  отсутствие всех долгов компании.\n- Не считай отношение долга к выручке\n  доказательством высокой долговой нагрузки.\n- Для неподтверждённых выводов используй\n  формулировки "возможно", "если", "при условии".\n- Если используешь факты из аналитики,\n  указывай номер источника в тексте.\n'

def rag_messages(question, context):
    return [{'role': 'system', 'content': 'Ты финансовый аналитик, который помогает оценивать влияние новостей на бизнес компаний. Используй предоставленные аналитические материалы как источники контекста. Строго соблюдай правила: 1. Не выдумывай факты, цифры или сведения о компании. 2. Различай факты из источников и собственные аналитические выводы. 3. Учитывай дату каждого документа. Не выдавай исторические данные за актуальные. 4. Если источник относится к 2021 году, используй его только как исторический контекст, если вопрос не касается именно этого периода. 5. Не делай выводов о конкретной компании только на основании общей отраслевой аналитики. 6. Ссылайся на источники в формате [Источник 1]. 7. Если данных недостаточно, прямо сообщай об этом. 8. Отвечай на русском языке, кратко и по существу. '}, {'role': 'user', 'content': f'Запрос:\n{question}\n\nАналитические материалы:\n{context}'}]
