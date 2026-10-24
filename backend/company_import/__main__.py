"""Run from backend: python -m company_import --file <private CSV>."""
import argparse
import json
from pathlib import Path

from .validation import ImportProblem, audit_file


def main(argv=None):
    parser = argparse.ArgumentParser(description='Company CSV validation; dry-run without database access')
    parser.add_argument('--file', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit_file(args.file).report()
        print(json.dumps({'mode': 'dry-run', **report}, ensure_ascii=True))
        return 2 if report['rejected_rows'] else 0
    except ImportProblem as error:
        print(json.dumps({'code': str(error)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
