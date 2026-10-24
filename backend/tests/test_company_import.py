import csv
from decimal import Decimal
import json

import pytest

from company_import.validation import HEADERS, ImportProblem, audit_file
from company_import.__main__ import main


def synthetic_row(source='SYNTH-IMPORT-001', **changes):
    row = dict.fromkeys(HEADERS, '')
    row.update(SYNTHETIC_U=source, ORG_TYPE='КОММ_ОРГ', OKFS_NAME='СИНТЕТИЧЕСКАЯ ФОРМА',
               COMPANY_AGE_YEARS_GRADATION='8-15', MAINOKVED_CODE='62.01',
               MAINOKVED_NAME='Синтетическая отрасль', AMOUNT_WORKERS_FNS_GRADATION='16-100',
               CL_TYPE='CLOSE_CLIENT', REVENUE_COMPANY='1234567890.12', GROUP_ID='SYNTH-GROUP',
               CITY='Синтетический город', REGION='Синтетический регион')
    for key in HEADERS:
        if key.endswith('_MARK') or key in {'NEGATIVEMARK', 'FTS_FLAG'}:
            row[key] = '0.0'
    row['FACTORING_MARK'] = '0.0'
    row.update(changes)
    return row


def write_csv(path, rows, encoding='utf-8', delimiter=';'):
    with path.open('w', encoding=encoding, newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_valid_decimal_and_private_dry_run(tmp_path, monkeypatch, capsys):
    path = write_csv(tmp_path / 'synthetic.csv', [synthetic_row()])
    audit = audit_file(path)
    assert audit.accepted[0].revenue == Decimal('1234567890.12')
    assert audit.accepted[0].status == 'CLOSED_CLIENT'
    assert audit.accepted[0].lines == [2]
    monkeypatch.setenv('DATABASE_URL', 'DO-NOT-CONNECT')
    assert main(['--file', str(path)]) == 0
    report = capsys.readouterr().out
    assert 'SYNTH-IMPORT' not in report and '1234567890' not in report
    assert json.loads(report)['mode'] == 'dry-run'


def test_conflict_quarantines_every_row_even_if_one_invalid(tmp_path):
    path = write_csv(tmp_path / 'synthetic.csv', [synthetic_row(), synthetic_row(REVENUE_COMPANY='bad'),
                     synthetic_row('SYNTH-IMPORT-002')])
    audit = audit_file(path)
    assert [p.source_id for p in audit.accepted] == ['SYNTH-IMPORT-002']
    assert audit.rejected_lines == {2, 3}
    assert audit.conflicting_ids == 1
    assert [i['line'] for i in audit.issues if i['code'] == 'CONFLICTING_IDENTIFIER'] == [2, 3]


def test_identical_rows_collapse_with_provenance(tmp_path):
    audit = audit_file(write_csv(tmp_path / 'synthetic.csv', [synthetic_row(), synthetic_row()]))
    assert len(audit.accepted) == 1 and audit.accepted[0].lines == [2, 3]
    assert audit.identical_duplicates == 1


@pytest.mark.parametrize('field,value,code', [
    ('SYNTHETIC_U', '', 'REQUIRED'), ('CITY', '', 'REQUIRED'),
    ('REGION', ' padded ', 'WHITESPACE_OR_CONTROL'),
    ('CL_TYPE', 'CLOSED_CLIENT', 'INVALID_ENUM'), ('NEGATIVEMARK', '2.0', 'INVALID_FLAG'),
    ('COMPANY_AGE_YEARS_GRADATION', 'unknown', 'INVALID_ENUM'),
    ('AMOUNT_WORKERS_FNS_GRADATION', '17', 'INVALID_ENUM'),
    ('MAINOKVED_CODE', 'code', 'INVALID_OKVED'),
    ('REVENUE_COMPANY', '-1', 'INVALID_MONEY'), ('REVENUE_COMPANY', 'NaN', 'INVALID_MONEY'),
    ('REVENUE_COMPANY', '1e3', 'INVALID_MONEY'), ('REVENUE_COMPANY', '12,12', 'INVALID_MONEY'),
    ('REVENUE_COMPANY', '0.001', 'INVALID_MONEY'),
    ('REVENUE_COMPANY', '10000000000000000', 'INVALID_MONEY'),
    ('SYNTHETIC_U', 'x'*129, 'TOO_LONG'),
])
def test_invalid_values(tmp_path, field, value, code):
    audit = audit_file(write_csv(tmp_path / 'synthetic.csv', [synthetic_row(**{field: value})]))
    assert not audit.accepted
    assert {'line': 2, 'field': field, 'code': code} in audit.issues


@pytest.mark.parametrize('encoding,delimiter,code', [('cp1251', ';', 'INVALID_UTF8'),
    ('utf-8', ',', 'INVALID_HEADERS_OR_DELIMITER')])
def test_encoding_and_delimiter(tmp_path, encoding, delimiter, code):
    with pytest.raises(ImportProblem, match=code):
        audit_file(write_csv(tmp_path / 'synthetic.csv', [synthetic_row()], encoding, delimiter))


def test_malformed_record_fails_whole_file(tmp_path):
    path = write_csv(tmp_path / 'synthetic.csv', [synthetic_row()])
    with path.open('a', encoding='utf-8') as stream:
        stream.write('wrong;columns\n')
    with pytest.raises(ImportProblem, match='INVALID_COLUMN_COUNT'):
        audit_file(path)
