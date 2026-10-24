import argparse
import asyncio
import json
import os
from pathlib import Path

from company_import.validation import ImportProblem, audit_file as audit_companies
from .validation import audit_file


def main(argv=None):
    parser = argparse.ArgumentParser(description='Payments/opaque identifier links; dry-run by default, no AI')
    parser.add_argument('kind', choices=['payments', 'links'])
    parser.add_argument('--file', required=True, type=Path)
    parser.add_argument('--companies-file', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-isolated-import', action='store_true')
    parser.add_argument('--target', choices=['isolated'])
    parser.add_argument('--expected-database')
    args = parser.parse_args(argv)
    try:
        reference = audit_companies(args.companies_file) if args.companies_file else None
        known = {p.source_id for p in reference.accepted} if reference else None
        audit = audit_file(args.file, args.kind, known)
        report = audit.report()
        if reference:
            report['reference_profiles'] = len(known)
            report['reference_rejected_rows'] = len(reference.rejected_lines)
        if args.apply:
            if not args.confirm_isolated_import or args.target != 'isolated' or not args.expected_database:
                raise ImportProblem('EXPLICIT_ISOLATED_CONFIRMATION_REQUIRED')
            from .storage import apply_audit
            result = asyncio.run(apply_audit(audit, os.environ.get('DATASET_IMPORT_DATABASE_URL', ''), args.expected_database))
            print(json.dumps({'mode': 'applied', **report, **result}))
        else:
            print(json.dumps({'mode': 'dry-run', **report}))
        return 2 if audit.rejected_rows else 0
    except ImportProblem as error:
        print(json.dumps({'code': str(error)}))
    except Exception:
        print(json.dumps({'code': 'DATASET_IMPORT_ERROR_VERIFY_BEFORE_RETRY'}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
