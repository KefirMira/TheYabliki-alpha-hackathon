"""Bounded deterministic review. Lexical/metadata checks are not semantic proof."""
import json
import re

from schemas.financial_review import FinancialFinding, FinancialReview
from schemas.persisted_analysis import RetrievedEvidence
from services.financial_assertion_rules import financial_assertion_flags

QUALIFIED = re.compile(r'\b(?:если|возможно|может|могут|могло|предположим)\b|при\s+условии|'
    r'нельзя\s+(?:утверждать|считать|гарантировать)|не\s+(?:означает|гарантирует|доказывает)|'
    r'нет\s+оснований|не\s+подтверждено|условия[^.!?;]{0,40}неизвестн')
LOAN = re.compile(r'кредит|за[её]мн|долг|лизинг|процентн\w*\s+(?:расход|платеж)|'
                  r'договор[^.!?;]{0,80}(?:комисси|ставк|срок|погашени)')
COMPANY = re.compile(r'компани|договор|портфел|по\s+кредит|у\s+не[её]')
PAYMENT_INVARIANCE = re.compile(r'не\s+повыша\w*\s+(?:процентн\w*\s+)?плат[её]ж|'
    r'плат[её]ж[^.!?;]{0,60}(?:не\s+(?:раст|измен|меня)|оста\w*\s+прежн)')
NUMBER = re.compile(r'(?<![\w.,])\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?')
FINANCIAL_NUMBER = re.compile(r'(?<!\w)\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?\s*'
    r'(?:%|₽|руб\w*|млн\b|млрд\b|usd\b|месяц\w*|лет\b|год\w*)', re.I)
CITATION = re.compile(r'\[Источник\s+(\d+)\]', re.I)


def numeric_forms(text):
    # Literal forms only: do not infer units/currency/year or calculate new financial facts.
    return {m.group().replace(' ', '').replace('\u00a0', '').replace(',', '.') for m in NUMBER.finditer(text)}


def review_financial_analysis(analysis, company_context, evidence, news):
    if not isinstance(company_context, dict) or company_context.get('version') != 'company-context-v1':
        raise ValueError('INVALID_FINANCIAL_REVIEW_CONTEXT')
    fragments = [RetrievedEvidence.model_validate(item) for item in evidence]
    sources = {item.id: item for item in fragments}
    if len(sources) != len(fragments):
        raise ValueError('DUPLICATE_FINANCIAL_REVIEW_SOURCE')
    fields = [('summary', analysis.summary)]
    fields += [(f'{name}[{i}]', value) for name in ('risks', 'opportunities', 'recommendations')
               for i, value in enumerate(getattr(analysis, name))]
    if sum(len(value) for _, value in fields) > 100_000:
        raise ValueError('FINANCIAL_REVIEW_INPUT_TOO_LARGE')
    supplied_text = news + '\n' + json.dumps(company_context, ensure_ascii=False, allow_nan=False) + '\n' + '\n'.join(item.text for item in fragments)
    if len(supplied_text.encode('utf-8')) > 200_000:
        raise ValueError('FINANCIAL_REVIEW_INPUT_TOO_LARGE')
    supplied_numbers = numeric_forms(supplied_text)
    findings = []
    limited = False

    def add(code, field, claim, explanation, *, disposition='NEEDS_REVIEW', severity='WARNING', ids=()):
        nonlocal limited
        if len(findings) >= 199 and disposition != 'CONFIRMED_ERROR':
            limited = True
            return
        # Structural errors must still block even after the review-hint limit.
        if len(findings) >= 200:
            limited = True
            if disposition == 'CONFIRMED_ERROR' and not any(f.disposition == 'CONFIRMED_ERROR' for f in findings):
                findings.pop()
            else:
                return
        findings.append(FinancialFinding(code=code, field=field, claim=claim[:1200],
            claim_truncated=len(claim)>1200, explanation=explanation,
            disposition=disposition, severity=severity, source_ids=list(ids)))

    for field, value in fields:
        # Keep decimal points and source labels; this is segmentation, not semantic parsing.
        for claim in re.split(r'(?<=[.!?;])\s+|\n+', value):
            if not claim.strip():
                continue
            lower = claim.casefold()
            flags = financial_assertion_flags(claim)
            qualified = bool(QUALIFIED.search(lower))
            loan = bool(LOAN.search(lower))
            company = bool(COMPANY.search(lower))
            if 'UNSUPPORTED_UNCHANGED_BORROWING_COST' in flags:
                add('UNSUPPORTED_UNCHANGED_BORROWING_COST', field, claim,
                    'Категоричная неизменность стоимости не подтверждена доступным контекстом. Неизменная ключевая ставка сама по себе не устанавливает все условия кредита; это сигнал проверки, не доказательство ложности.')
            if PAYMENT_INVARIANCE.search(lower):
                add('PAYMENT_INVARIANCE_REQUIRES_REVIEW', field, claim,
                    'Даже условная привязка к ключевой ставке не устанавливает все компоненты платежа. Проверить договор, комиссии и график; формулировка не объявляется ложной.')
            if loan:
                # Current company-context-v1 intentionally carries no verified credit terms.
                add('CREDIT_TERMS_UNKNOWN', field, claim,
                    'Текущая разрешённая проекция не содержит подтверждённых условий кредитного договора. Обоснованность индивидуального финансового вывода не установлена.',
                    disposition='UNKNOWN', severity='INFO')
                if company and not qualified:
                    add('MISSING_CREDIT_TERMS_QUALIFICATION', field, claim,
                        'Утверждение о компании/договоре не обозначено как условное при неизвестных кредитных условиях. Эвристика не определяет истинность утверждения.')
            numbers = [m.group() for m in FINANCIAL_NUMBER.finditer(claim)]
            for number in numbers:
                forms = numeric_forms(number)
                absent = not forms.issubset(supplied_numbers)
                add('FINANCIAL_NUMBER_NOT_IN_INPUT' if absent else 'FINANCIAL_NUMBER_ATTRIBUTION_UNKNOWN', field, claim,
                    ('Числовая форма не найдена во входах. Возможны вычисление, округление или запись прописью: проверить происхождение, единицы, период и расчёт, не объявлять число выдуманным автоматически.'
                     if absent else 'Число встречается во входах, но это не доказывает совпадение величины, субъекта, единиц или периода. Требуется проверка атрибуции.'),
                    disposition='NEEDS_REVIEW' if absent else 'UNKNOWN', severity='WARNING' if absent else 'INFO')
            if numbers and loan and company:
                add('COMPANY_CONTRACT_NUMBER_UNVERIFIED', field, claim,
                    'Сумма, процент или срок конкретного договора не установлены разрешённым профилем. Число в новости или чужом источнике не подтверждает условия компании.')
            if company and not qualified and re.search(r'экспортиру|импортиру|имеет\s+(?:долг|кредит)|есть\s+(?:долг|кредит)', lower):
                add('COMPANY_FACT_NOT_ESTABLISHED', field, claim,
                    'Отрасль, регион и продуктовые/ВЭД-признаки не доказывают конкретную деятельность или обязательство. Требуется проверка утверждения по данным компании.')
            if company and not qualified and re.search(r'гарантирован|обязательно|точно|получит|составит|достигнет', lower):
                add('COMPANY_PROJECTION_AS_FACT', field, claim,
                    'Прогноз о компании сформулирован категорично. Проверить, не выдано ли отраслевое предположение за факт; эвристика не устанавливает ложность.')
            if re.search(r'по\s+(?:количеств\w*|числ\w*)\s+плат[её]ж|из\s+числа\s+контрагент', lower) and re.search(r'оборот|прибыл|долг|выручк', lower):
                add('STRUCTURAL_COUNT_AS_FINANCIAL_INFERENCE', field, claim,
                    'Структурные счётчики платёжных строк/контрагентов не задают денежный оборот, прибыль или долг. Проверить смешение вычислений и фактов.')
            if re.search(r'факт|по\s+данным\s+(?:компании|профиля)', lower) and re.search(r'предполож|гипотез|возможно', lower):
                add('FACT_ASSUMPTION_BOUNDARY_REQUIRES_REVIEW', field, claim,
                    'В одном фрагменте объединены признаки факта и предположения. Проверка не различает корректное противопоставление и ошибочное смешение: нужен эксперт.')
            for citation in CITATION.finditer(claim):
                source_id = int(citation.group(1))
                if source_id not in sources:
                    add('CITATION_SOURCE_NOT_FOUND', field, claim,
                        'Указанного номера нет в точном наборе evidence. Подтверждена ошибка ссылки, а не ложность финансового утверждения.',
                        disposition='CONFIRMED_ERROR', severity='ERROR', ids=[source_id])
                else:
                    add('CITATION_ENTAILMENT_UNKNOWN', field, claim,
                        'Источник существует, но поддержка конкретного тезиса семантически не установлена. Совпадение слов, чисел или даже наличие цитаты не доказывает достоверность.',
                        disposition='UNKNOWN', severity='INFO', ids=[source_id])
                    mentioned = set().union(*(numeric_forms(number) for number in numbers)) if numbers else set()
                    if mentioned - numeric_forms(sources[source_id].text):
                        add('CITED_SOURCE_NUMBER_NOT_FOUND', field, claim,
                            'Числовая форма отсутствует в указанном фрагменте. Возможен иной источник или расчёт, но эта ссылка пока не обосновывает число.', ids=[source_id])
    if not findings:
        add('FINANCIAL_CORRECTNESS_NOT_ESTABLISHED', 'analysis', '',
            'Детерминированных сигналов не обнаружено. Полнота правил ограничена; финансовая корректность не установлена.',
            disposition='UNKNOWN', severity='INFO')
    blocking = any(item.disposition == 'CONFIRMED_ERROR' for item in findings)
    status = 'ERROR' if blocking else 'NEEDS_REVIEW' if limited or any(item.disposition == 'NEEDS_REVIEW' for item in findings) else 'UNKNOWN'
    return FinancialReview(status=status, findings=findings, blocking=blocking, coverage_complete=not limited)
