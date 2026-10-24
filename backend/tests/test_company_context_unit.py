from decimal import Decimal
import json

import pytest

from repositories.company_context_repository import CONTEXT_SQL, CSV_FIELDS
from services.company_context_service import (
    build_context, serialize_context, MAX_CONTEXT_BYTES, external_transfer_guard,
    CompanyContextExternalTransferBlocked, CONTEXT_RULES,
)


def row(**changes):
    value=dict(industry='Синтетическое производство',region='Синтетический регион',revenue=Decimal('1234567890.12'),
        revenue_year=None,client_status='CLIENT',csv_origin=True,
        csv_fields={'MAINOKVED_CODE':'62.01','MAINOKVED_NAME':'Синтетическое производство',
                    'AMOUNT_WORKERS_FNS_GRADATION':'16-100','CL_PRODUCT_LOA_MARK':'1.0','FTS_FLAG':'1.0'},
        incoming_rows=3,incoming_counterparties=2,outgoing_rows=1,outgoing_counterparties=1,snapshot_present=True)
    value.update(changes)
    return value


def test_facts_derivations_and_unknown_units_are_distinct():
    context=build_context(row())
    assert context['facts']['revenue']['value']=='1234567890.12'
    assert context['facts']['revenue']['year'] is context['facts']['revenue']['currency'] is context['facts']['revenue']['unit'] is None
    assert context['facts']['employee_ranges']['fns']['value']=='16-100'
    assert context['facts']['product_and_activity_flags']['loan_product']['value'] is True
    assert context['computed']['payment_structure']['incoming']=={'source_rows':3,'distinct_counterparties':2}
    assert context['model_assumptions']==[] and 'payment_period' in context['missing']
    assert 'F-U_links_and_roles' in context['excluded']


@pytest.mark.parametrize('amount',[None,Decimal('NaN'),Decimal('Infinity'),Decimal('-1')])
def test_unknown_or_invalid_finances_not_invented(amount):
    context=build_context(row(revenue=amount))
    assert 'revenue' not in context['facts'] and 'revenue' in context['missing']


def test_raw_untrusted_data_and_unsupported_categories_are_ignored():
    context=build_context(row(csv_origin=False,csv_fields={'CL_PRODUCT_LOA_MARK':'1.0','secret':'never-copy'}))
    assert 'product_and_activity_flags' not in context['facts']
    assert 'never-copy' not in serialize_context(context)
    context=build_context(row(csv_fields={'MAINOKVED_CODE':'62.01','MAINOKVED_NAME':'Different industry','CL_PRODUCT_LOA_MARK':'maybe'}))
    assert 'okved_code' not in context['facts'] and 'loan_product' in context['missing']


def test_payload_size_and_no_implicit_truncation():
    context=build_context(row(industry='x'*100000,region='y'*100000))
    assert 'industry' in context['missing'] and 'region' in context['missing']
    assert len(serialize_context(context).encode())<=MAX_CONTEXT_BYTES
    with pytest.raises(ValueError,match='COMPANY_CONTEXT_TOO_LARGE'):
        serialize_context({'unexpected':'x'*(MAX_CONTEXT_BYTES+1)})


def test_privacy_gate_and_sql_whitelist():
    with pytest.raises(CompanyContextExternalTransferBlocked):external_transfer_guard(build_context(row()))
    external_transfer_guard(None)
    for excluded in ['p.amount','PAY_AMT','PAY_CNT','company_person_links','c.name','c.inn','c.ogrn']:
        assert excluded not in CONTEXT_SQL
    assert 'count(DISTINCT' in CONTEXT_SQL and 'SELECT *' not in CONTEXT_SQL
    assert len(CSV_FIELDS)==13
    assert 'не доказывает долг' in CONTEXT_RULES
