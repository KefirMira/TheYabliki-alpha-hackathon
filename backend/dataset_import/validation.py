"""Streaming validation and private-free aggregate reports for two CSV formats."""
import csv
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

from company_import.validation import ImportProblem
from . import VERSION

HEADERS = {
    'payments': ('BENEFICIARY', 'PAYER', 'PAY_AMT', 'PAY_CNT'),
    'links': ('SYNTHETIC_F', 'CITY_NAME', 'RC_NAME', 'SYNTHETIC_U'),
}
SOURCES = {'payments': 'df_Uid_payment_hack', 'links': 'df_Fid_Uid_link_hack'}
IDS = {'payments': ('BENEFICIARY', 'PAYER'), 'links': ('SYNTHETIC_F', 'SYNTHETIC_U')}
REFERENCE_IDS = {'payments': ('BENEFICIARY', 'PAYER'), 'links': ('SYNTHETIC_U',)}
NAMESPACE = '_external_csv_row_v1'


def fingerprint(path):
    try:
        digest = sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        raise ImportProblem('FILE_UNAVAILABLE') from None


def encoded_hash(values):
    return sha256(json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def records(path, kind):
    try:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream, delimiter=';', strict=True)
            if tuple(next(reader, ())) != HEADERS[kind]:
                raise ImportProblem('INVALID_HEADERS_OR_DELIMITER')
            ordinal = 0
            while True:
                line = reader.line_num + 1
                values = next(reader, None)
                if values is None:
                    break
                ordinal += 1
                if len(values) != 4:
                    raise ImportProblem('INVALID_COLUMN_COUNT')
                yield ordinal, line, reader.line_num, dict(zip(HEADERS[kind], values))
    except UnicodeError:
        raise ImportProblem('INVALID_UTF8') from None
    except csv.Error:
        raise ImportProblem('MALFORMED_CSV') from None
    except OSError:
        raise ImportProblem('FILE_UNAVAILABLE') from None


def problems(row, kind):
    errors = []
    for key, value in row.items():
        code = None
        if not value and (kind == 'payments' or key in IDS[kind]):
            code = 'REQUIRED'
        elif value != value.strip() or any(ord(c) < 32 for c in value):
            code = 'WHITESPACE_OR_CONTROL'
        elif len(value) > (128 if key in IDS[kind] else 1024):
            code = 'TOO_LONG'
        if code:
            errors.append((key, code))
    if kind == 'payments':
        try:
            value = row['PAY_AMT']
            if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
                raise InvalidOperation
            amount = Decimal(value)
            if not amount.is_finite() or amount >= Decimal('10000000000000000') or amount != amount.quantize(Decimal('.01')):
                raise InvalidOperation
        except InvalidOperation:
            errors.append(('PAY_AMT', 'INVALID_MONEY'))
        value = row['PAY_CNT']
        if not re.fullmatch(r'[0-9]{1,19}', value) or int(value) > 9223372036854775807:
            errors.append(('PAY_CNT', 'INVALID_COUNT'))
    return errors


@dataclass
class Audit:
    path: Path
    kind: str
    file_hash: str
    rows: int = 0
    rejected_rows: int = 0
    exact_repeats: int = 0
    pair_repeats: int = 0
    issue_count: int = 0
    issues: list = field(default_factory=list)
    identifier_counts: dict = field(default_factory=dict)
    outside_reference: dict = field(default_factory=dict)

    def report(self):
        return {'importer_version': VERSION, 'kind': self.kind, 'rows': self.rows,
                'valid_rows': self.rows-self.rejected_rows, 'rejected_rows': self.rejected_rows,
                'exact_repeat_rows': self.exact_repeats, 'repeated_pair_rows': self.pair_repeats,
                'distinct_identifiers': self.identifier_counts, 'outside_company_reference': self.outside_reference,
                'issue_count': self.issue_count, 'issues': self.issues,
                'issues_truncated': self.issue_count > len(self.issues)}


def audit_file(path, kind, known_company_ids=None):
    path = Path(path)
    if kind not in HEADERS:
        raise ImportProblem('INVALID_DATASET_KIND')
    digest = fingerprint(path)
    audit = Audit(path, kind, digest)
    unique_rows, unique_pairs = set(), set()
    identifiers = {k: set() for k in IDS[kind]}
    for _, line, _, row in records(path, kind):
        audit.rows += 1
        errors = problems(row, kind)
        audit.rejected_rows += bool(errors)
        for key, code in errors:
            audit.issue_count += 1
            if len(audit.issues) < 1000:
                audit.issues.append({'line': line, 'field': key, 'code': code})
        row_hash = encoded_hash(row)
        pair = encoded_hash([row[k] for k in IDS[kind]])
        audit.exact_repeats += row_hash in unique_rows
        audit.pair_repeats += pair in unique_pairs
        unique_rows.add(row_hash)
        unique_pairs.add(pair)
        for key in identifiers:
            if row[key]:
                identifiers[key].add(row[key])
    if fingerprint(path) != digest:
        raise ImportProblem('FILE_CHANGED_DURING_VALIDATION')
    audit.identifier_counts = {k: len(v) for k, v in identifiers.items()}
    audit.outside_reference = {k: None if known_company_ids is None else len(identifiers[k]-known_company_ids)
                               for k in REFERENCE_IDS[kind]}
    return audit


def batches(audit, size=1000):
    batch = []
    for ordinal, line, end, row in records(audit.path, audit.kind):
        if problems(row, audit.kind):
            raise ImportProblem('FILE_CHANGED_OR_INVALID')
        metadata = {'source': SOURCES[audit.kind], 'filename': audit.path.name,
                    'file_sha256': audit.file_hash, 'record_number': ordinal,
                    'line': line, 'line_end': end, 'row_sha256': encoded_hash(row),
                    'importer_version': VERSION, 'attributes': row}
        entry = {'source_id': f'pulse-csv-row-v1:{audit.kind}:{audit.file_hash}:{ordinal}',
                 'source_data': {NAMESPACE: metadata}}
        if audit.kind == 'payments':
            entry.update(source_company_id=row['BENEFICIARY'], payer_source_company_id=row['PAYER'],
                         amount=str(Decimal(row['PAY_AMT'])), payment_count=int(row['PAY_CNT']))
        else:
            entry.update(source_company_id=row['SYNTHETIC_U'], source_person_id=row['SYNTHETIC_F'],
                         city_name=row['CITY_NAME'], rc_name=row['RC_NAME'])
        batch.append(entry)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
