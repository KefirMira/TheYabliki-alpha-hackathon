"""Strict CSV snapshot validation. Diagnostics never include input values."""
import csv
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path
import re

from . import VERSION

HEADERS = tuple('''SYNTHETIC_U ORG_TYPE OKFS_NAME COMPANY_AGE_YEARS_GRADATION
ECO_MARK_LABEL MAINOKVED_CODE MAINOKVED_NAME NEGATIVEMARK
AMOUNT_WORKERS_FNS_GRADATION AMOUNT_WORKERS_SPARK_GRADATION CL_TYPE
CL_PRODUCT_RKO_MARK CL_PRODUCT_GAR_MARK CL_PRODUCT_LOA_MARK CL_PRODUCT_LEA_MARK
CL_PRODUCT_DEP_MARK CL_PRODUCT_ZPP_MARK FTS_FLAG FTS_COUNTRY_NAME FACTORING_MARK
REVENUE_COMPANY GROUP_ID CITY REGION'''.split())
OPTIONAL = {'ECO_MARK_LABEL', 'AMOUNT_WORKERS_SPARK_GRADATION', 'FTS_COUNTRY_NAME'}
FLAGS = {'NEGATIVEMARK', 'FTS_FLAG', 'FACTORING_MARK'} | {k for k in HEADERS if k.startswith('CL_PRODUCT_')}
WORKERS = {'Менее 15', '16-100', '101-250', 'Более 251'}
ENUMS = {
    'ORG_TYPE': {'КОММ_ОРГ'},
    'COMPANY_AGE_YEARS_GRADATION': {'0-3', '4-7', '8-15', '16-25'},
    'ECO_MARK_LABEL': {'', 'Рождение', 'Оптимизация', 'Бизнес в новой реальности', 'Стремительный рост'},
    'AMOUNT_WORKERS_FNS_GRADATION': WORKERS,
    'AMOUNT_WORKERS_SPARK_GRADATION': WORKERS | {''},
    'CL_TYPE': {'CLIENT', 'PROSPECT', 'CLOSE_CLIENT'},
}
SOURCE = 'df_Uid_data_hack'


class ImportProblem(Exception):
    """Only a fixed diagnostic code may cross the CLI boundary."""


@dataclass
class Profile:
    attributes: dict[str, str]
    revenue: Decimal
    lines: list[int]
    row_hash: str

    @property
    def source_id(self):
        return self.attributes['SYNTHETIC_U']

    @property
    def status(self):
        value = self.attributes['CL_TYPE']
        return 'CLOSED_CLIENT' if value == 'CLOSE_CLIENT' else value


@dataclass
class Audit:
    file_hash: str
    total_rows: int = 0
    accepted: list[Profile] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    rejected_lines: set[int] = field(default_factory=set)
    conflicting_ids: int = 0
    identical_duplicates: int = 0

    def report(self):
        return {'importer_version': VERSION, 'source': SOURCE,
                'rows': self.total_rows, 'eligible_profiles': len(self.accepted),
                'rejected_rows': len(self.rejected_lines),
                'conflicting_identifiers': self.conflicting_ids,
                'identical_duplicate_rows': self.identical_duplicates,
                'issues': self.issues}


def row_problems(row):
    errors = []
    for key, value in row.items():
        code = None
        if not value and key not in OPTIONAL:
            code = 'REQUIRED'
        elif value != value.strip() or any(ord(c) < 32 for c in value):
            code = 'WHITESPACE_OR_CONTROL'
        elif len(value) > (128 if key == 'SYNTHETIC_U' else 1024):
            code = 'TOO_LONG'
        elif key in ENUMS and value not in ENUMS[key]:
            code = 'INVALID_ENUM'
        elif key in FLAGS and value not in {'0', '1', '0.0', '1.0'}:
            code = 'INVALID_FLAG'
        elif key == 'MAINOKVED_CODE' and not re.fullmatch(r'[0-9]{2}(?:\.[0-9]{1,2}){0,2}', value):
            code = 'INVALID_OKVED'
        if code:
            errors.append((key, code))
    value = row['REVENUE_COMPANY']
    revenue = None
    try:
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
            raise InvalidOperation
        revenue = Decimal(value)
        if not revenue.is_finite() or revenue >= Decimal('10000000000000000'):
            raise InvalidOperation
        if revenue != revenue.quantize(Decimal('0.01')):
            raise InvalidOperation
    except InvalidOperation:
        errors.append(('REVENUE_COMPANY', 'INVALID_MONEY'))
    return errors, revenue


def audit_file(path: Path) -> Audit:
    try:
        data = path.read_bytes()
        decoded = data.decode('utf-8-sig', errors='strict')
    except UnicodeError:
        raise ImportProblem('INVALID_UTF8') from None
    except OSError:
        raise ImportProblem('FILE_UNAVAILABLE') from None
    audit = Audit(sha256(data).hexdigest())
    reader = csv.reader(io.StringIO(decoded, newline=''), delimiter=';', strict=True)
    groups = {}
    try:
        if tuple(next(reader, ())) != HEADERS:
            raise ImportProblem('INVALID_HEADERS_OR_DELIMITER')
        while True:
            line = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            audit.total_rows += 1
            if len(values) != len(HEADERS):
                # Identity cannot be trusted in a malformed record: fail the whole file.
                raise ImportProblem('INVALID_COLUMN_COUNT')
            row = dict(zip(HEADERS, values))
            errors, revenue = row_problems(row)
            for key, code in errors:
                audit.issues.append({'line': line, 'field': key, 'code': code})
            group = groups.setdefault(row['SYNTHETIC_U'], [])
            group.append((row, revenue, line, bool(errors)))
        for group in groups.values():
            first = group[0][0]
            conflict = any(item[0] != first for item in group[1:])
            invalid = any(item[3] for item in group)
            if conflict or invalid:
                audit.conflicting_ids += int(conflict)
                for _, _, line, _ in group:
                    audit.rejected_lines.add(line)
                    if conflict:
                        audit.issues.append({'line': line, 'field': 'SYNTHETIC_U', 'code': 'CONFLICTING_IDENTIFIER'})
                continue
            lines = [item[2] for item in group]
            row_hash = sha256(json.dumps(first, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
            audit.accepted.append(Profile(first, group[0][1], lines, row_hash))
            audit.identical_duplicates += len(group) - 1
    except (csv.Error, OverflowError):
        raise ImportProblem('MALFORMED_CSV') from None
    audit.issues.sort(key=lambda i: (i['line'], i['field'], i['code']))
    return audit
