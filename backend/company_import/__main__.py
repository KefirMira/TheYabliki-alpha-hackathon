"""Run from backend: python -m company_import --file <private CSV>."""
import argparse
import asyncio
import json
import os
from pathlib import Path

from .validation import ImportProblem, audit_file


def main(argv=None):
    parser = argparse.ArgumentParser(description='Company CSV: dry-run by default; explicit isolated database import')
    parser.add_argument('--file', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-isolated-import', action='store_true')
    parser.add_argument('--target', choices=['isolated'])
    parser.add_argument('--expected-database')
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--update-existing', action='store_true')
    args = parser.parse_args(argv)
    try:
        audit = audit_file(args.file)
        report = audit.report()
        if args.apply:
            if not args.confirm_isolated_import or args.target != 'isolated' or not args.expected_database:
                raise ImportProblem('EXPLICIT_ISOLATED_CONFIRMATION_REQUIRED')
            from .storage import apply_audit
            result = asyncio.run(apply_audit(audit, os.environ.get('COMPANY_IMPORT_DATABASE_URL', ''),
                args.expected_database, update_existing=args.update_existing, allow_partial=args.allow_partial))
            print(json.dumps({'mode': 'applied', **report, **result}, ensure_ascii=True))
            return 2 if report['rejected_rows'] else 0
        print(json.dumps({'mode': 'dry-run', **report}, ensure_ascii=True))
        return 2 if report['rejected_rows'] else 0
    except ImportProblem as error:
        print(json.dumps({'code': str(error)}))
        return 1
    except Exception:
        # Driver exceptions can include input rows, SQL parameters and credentials.
        print(json.dumps({'code': 'IMPORT_DATABASE_ERROR_VERIFY_BEFORE_RETRY'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
