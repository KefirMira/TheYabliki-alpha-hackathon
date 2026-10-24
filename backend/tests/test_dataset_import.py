import csv
import json

import pytest

from company_import.validation import ImportProblem
from dataset_import.validation import HEADERS, audit_file, batches
from dataset_import.__main__ import main


def write_rows(path, kind, rows, encoding='utf-8', delimiter=';'):
    with path.open('w', encoding=encoding, newline='') as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerow(HEADERS[kind])
        writer.writerows(rows)
    return path


PAYMENT = ['SYNTH-A', 'SYNTH-OUTSIDE', '123.40', '2']
LINK = ['OPAQUE-F', '', '', 'SYNTH-A']


@pytest.mark.parametrize('kind,row', [('payments', PAYMENT), ('links', LINK)])
def test_exact_repeats_preserved_and_opaque_ids(tmp_path, kind, row):
    path = write_rows(tmp_path/'synthetic.csv', kind, [row, row])
    audit = audit_file(path, kind, {'SYNTH-A'})
    assert audit.rows == 2 and audit.exact_repeats == audit.pair_repeats == 1
    entries = list(batches(audit))[0]
    assert len({r['source_id'] for r in entries}) == 2
    assert entries[0]['source_data']['_external_csv_row_v1']['line'] == 2
    assert entries[1]['source_data']['_external_csv_row_v1']['line'] == 3
    assert audit.outside_reference == ({'BENEFICIARY': 0, 'PAYER': 1} if kind == 'payments' else {'SYNTHETIC_U': 0})


def test_different_payments_same_pair_remain_separate(tmp_path):
    audit = audit_file(write_rows(tmp_path/'synthetic.csv', 'payments', [PAYMENT, PAYMENT[:2]+['456.70','3']]), 'payments')
    assert audit.pair_repeats == 1 and audit.exact_repeats == 0
    assert len(list(batches(audit))[0]) == 2


@pytest.mark.parametrize('kind,row,field,code', [
    ('payments',['','B','1','1'],'BENEFICIARY','REQUIRED'),
    ('payments',['A','B','-1','1'],'PAY_AMT','INVALID_MONEY'),
    ('payments',['A','B','NaN','1'],'PAY_AMT','INVALID_MONEY'),
    ('payments',['A','B','1e3','1'],'PAY_AMT','INVALID_MONEY'),
    ('payments',['A','B','1,1','1'],'PAY_AMT','INVALID_MONEY'),
    ('payments',['A','B','0.001','1'],'PAY_AMT','INVALID_MONEY'),
    ('payments',['A','B','10000000000000000','1'],'PAY_AMT','INVALID_MONEY'),
    ('payments',['A','B','1','-1'],'PAY_CNT','INVALID_COUNT'),
    ('payments',['A','B','1','1.0'],'PAY_CNT','INVALID_COUNT'),
    ('payments',['A','B','1','9223372036854775808'],'PAY_CNT','INVALID_COUNT'),
    ('links',['','','','A'],'SYNTHETIC_F','REQUIRED'),
    ('links',['F','','',''],'SYNTHETIC_U','REQUIRED'),
    ('links',[' F','','','A'],'SYNTHETIC_F','WHITESPACE_OR_CONTROL'),
    ('links',['F','a\nb','','A'],'CITY_NAME','WHITESPACE_OR_CONTROL'),
    ('links',['F'*129,'','','A'],'SYNTHETIC_F','TOO_LONG'),
])
def test_invalid_values(tmp_path, kind, row, field, code):
    audit = audit_file(write_rows(tmp_path/'synthetic.csv',kind,[row]),kind)
    assert audit.rejected_rows == 1
    assert {'line':2,'field':field,'code':code} in audit.issues


@pytest.mark.parametrize('encoding,delimiter,code', [('cp1251',';','INVALID_UTF8'),('utf-8',',','INVALID_HEADERS_OR_DELIMITER')])
def test_encoding_delimiter(tmp_path, encoding, delimiter, code):
    path=write_rows(tmp_path/'synthetic.csv','links',[['F','Синтетический город','','A']],encoding,delimiter)
    with pytest.raises(ImportProblem,match=code):
        audit_file(path,'links')


def test_dry_run_private_and_without_database(tmp_path, monkeypatch, capsys):
    path=write_rows(tmp_path/'synthetic.csv','payments',[PAYMENT])
    monkeypatch.setenv('DATASET_IMPORT_DATABASE_URL','DO-NOT-CONNECT')
    assert main(['payments','--file',str(path)]) == 0
    out=capsys.readouterr().out
    assert 'SYNTH' not in out and '123.40' not in out
    assert json.loads(out)['outside_company_reference'] == {'BENEFICIARY':None,'PAYER':None}
    assert main(['payments','--file',str(path),'--apply']) == 1
    assert json.loads(capsys.readouterr().out)['code']=='EXPLICIT_ISOLATED_CONFIRMATION_REQUIRED'


def test_diagnostics_limit_and_malformed_structure(tmp_path):
    path=write_rows(tmp_path/'synthetic.csv','payments',[['','','','']]*1100)
    audit=audit_file(path,'payments')
    assert audit.rejected_rows==1100 and len(audit.issues)==1000 and audit.report()['issues_truncated']
    path.write_text('BENEFICIARY;PAYER;PAY_AMT;PAY_CNT\nA;B;1\n',encoding='utf-8')
    with pytest.raises(ImportProblem,match='INVALID_COLUMN_COUNT'):
        audit_file(path,'payments')
