import copy

import pytest

from schemas.analysis import AnalysisContent, ValidationResult
from services.company_context_service import build_context
from services.financial_review_service import review_financial_analysis


def context():
    return build_context(dict(industry='Synthetic industry', incoming_rows=3, incoming_counterparties=2,
                              outgoing_rows=0, outgoing_counterparties=0))


def evidence(text='Учебная ключевая ставка 14%; это не условия конкретной компании.'):
    return [dict(id=1, document='synthetic.pdf', page=1, chunk_id=1, date=None, score=0.4, text=text)]


def analyze(text, *, fragments=None, news='Учебная ключевая ставка сохранена на 14%.'):
    content = AnalysisContent(relevance='unknown', summary=text, risks=[], opportunities=[], recommendations=[])
    return review_financial_analysis(content, context(), evidence() if fragments is None else fragments, news)


def codes(report):
    return {item.code for item in report.findings}


@pytest.mark.parametrize('text', [
    'Если у компании есть кредит, возможно влияние ставки; условия договора неизвестны.',
    'Нельзя утверждать, что стоимость кредитования не меняется.',
    'При условии фиксированной ставки стоимость кредита компании может оставаться прежней.',
])
def test_qualified_wording_is_not_treated_as_false_or_passed(text):
    report = analyze(text)
    assert 'UNSUPPORTED_UNCHANGED_BORROWING_COST' not in codes(report)
    assert 'MISSING_CREDIT_TERMS_QUALIFICATION' not in codes(report)
    assert report.status == 'UNKNOWN' and not report.blocking
    assert report.financial_correctness == 'UNKNOWN'
    assert all(f.disposition == 'UNKNOWN' for f in report.findings)


@pytest.mark.parametrize('text', [
    'Стоимость кредитования не меняется.',
    'Прямого изменения стоимости заёмного финансирования не произошло.',
    'Стоимость кредита компании не изменилась.',
])
def test_categorical_cost_claims_are_review_signals_not_confirmed_falsehoods(text):
    report = analyze(text)
    assert 'UNSUPPORTED_UNCHANGED_BORROWING_COST' in codes(report)
    assert report.status == 'NEEDS_REVIEW' and not report.blocking
    assert not any(f.disposition == 'CONFIRMED_ERROR' for f in report.findings)
    assert all(f.claim == text and f.field == 'summary' and f.explanation for f in report.findings)


def test_conditional_payment_invariance_still_requires_review():
    report = analyze('Если кредиты привязаны к ключевой ставке, её сохранение не повышает платежи по ним.')
    assert 'PAYMENT_INVARIANCE_REQUIRES_REVIEW' in codes(report)
    assert report.status == 'NEEDS_REVIEW'


@pytest.mark.parametrize('text', [
    'У компании кредит 987654 рублей под 19,25% на 36 месяцев.',
    'Договор компании предусматривает комиссию 987654 рублей.',
])
def test_invented_contract_numbers_and_missing_qualifications(text):
    report = analyze(text)
    assert {'FINANCIAL_NUMBER_NOT_IN_INPUT', 'COMPANY_CONTRACT_NUMBER_UNVERIFIED',
            'MISSING_CREDIT_TERMS_QUALIFICATION'} <= codes(report)
    assert all(f.disposition != 'CONFIRMED_ERROR' for f in report.findings)


def test_same_number_in_macro_source_does_not_prove_company_rate():
    report = analyze('Кредит компании выдан под 14% [Источник 1].')
    assert {'FINANCIAL_NUMBER_ATTRIBUTION_UNKNOWN', 'COMPANY_CONTRACT_NUMBER_UNVERIFIED',
            'CITATION_ENTAILMENT_UNKNOWN'} <= codes(report)
    assert report.status == 'NEEDS_REVIEW'


@pytest.mark.parametrize('text', [
    'Компания имеет кредит.', 'Компания экспортирует нефть.',
    'Компания обязательно получит прибыль.',
    'По числу платёжных строк оборот компании равен 987 млн рублей.',
    'По данным профиля это факт: возможно увеличение долга компании.',
])
def test_company_facts_computations_and_assumptions_are_not_conflated(text):
    report = analyze(text)
    assert codes(report) & {'COMPANY_FACT_NOT_ESTABLISHED', 'COMPANY_PROJECTION_AS_FACT',
                            'STRUCTURAL_COUNT_AS_FINANCIAL_INFERENCE', 'FACT_ASSUMPTION_BOUNDARY_REQUIRES_REVIEW'}
    assert report.status == 'NEEDS_REVIEW' and not report.blocking


@pytest.mark.parametrize('source_text', [
    'Синтетический обзор добычи золота; кредитные договоры не рассматриваются.',
    'Стоимость кредитования не меняется.',
])
def test_existing_citation_or_literal_text_match_never_proves_entailment(source_text):
    report = analyze('Стоимость кредитования не меняется [Источник 1].', fragments=evidence(source_text))
    finding = next(f for f in report.findings if f.code == 'CITATION_ENTAILMENT_UNKNOWN')
    assert finding.disposition == 'UNKNOWN' and finding.source_ids == [1]
    assert not report.blocking and report.financial_correctness == 'UNKNOWN'


def test_number_missing_from_cited_fragment_is_not_automatically_false():
    report = analyze('Ставка 19,25% [Источник 1].')
    assert 'CITED_SOURCE_NUMBER_NOT_FOUND' in codes(report)
    assert not report.blocking


def test_missing_citation_is_confirmed_reference_error_only():
    report = analyze('Условный вывод [Источник 99].')
    finding = next(f for f in report.findings if f.code == 'CITATION_SOURCE_NOT_FOUND')
    assert finding.disposition == 'CONFIRMED_ERROR' and finding.severity == 'ERROR'
    assert report.status == 'ERROR' and report.blocking
    assert report.financial_correctness == 'UNKNOWN'


def test_no_signal_means_unknown_and_legacy_contract_unchanged():
    report = analyze('Данных для вывода недостаточно.')
    assert report.status == 'UNKNOWN'
    assert codes(report) == {'FINANCIAL_CORRECTNESS_NOT_ESTABLISHED'}
    assert set(ValidationResult.model_fields) == {'passed', 'warnings'}


def test_inputs_unchanged_and_findings_reproducible():
    data = context()
    fragments = evidence()
    before = copy.deepcopy((data, fragments))
    content = AnalysisContent(relevance='unknown', summary='Условный вывод [Источник 1].',
                              risks=[], opportunities=[], recommendations=[])
    a = review_financial_analysis(content, data, fragments, 'Synthetic')
    b = review_financial_analysis(content, data, fragments, 'Synthetic')
    assert a == b and (data, fragments) == before


def test_review_limits_are_explicit_and_cannot_hide_reference_error():
    report = analyze(('Кредит компании 987654 рублей. '*80)+'Вывод [Источник 999].')
    assert not report.coverage_complete and len(report.findings) <= 200
    assert report.blocking and 'CITATION_SOURCE_NOT_FOUND' in codes(report)


def test_duplicate_evidence_rejected():
    with pytest.raises(ValueError, match='DUPLICATE_FINANCIAL_REVIEW_SOURCE'):
        analyze('Synthetic', fragments=evidence()+evidence())


def test_review_input_byte_limit():
    with pytest.raises(ValueError, match='FINANCIAL_REVIEW_INPUT_TOO_LARGE'):
        analyze('Synthetic', news='x'*200001)
