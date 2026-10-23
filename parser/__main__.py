import argparse
import json
import sys
from xml.etree.ElementTree import ParseError

from .collector import collect_once, save_report
from .config import Config


def main(argv=None):
    cli = argparse.ArgumentParser(description="One-shot local synthetic RSS collector; no AI or PostgreSQL")
    cli.add_argument("--once", action="store_true", required=True, help="Read local RSS and deliver each valid item once")
    cli.parse_args(argv)
    try:
        config = Config.from_env()
        report = collect_once(config)
        save_report(config.report_path, report)
    except (ValueError, OSError, ParseError) as error:
        # No response bodies/credentials/news text in stderr. Detailed item codes are in the report.
        print(json.dumps({"status": "run_error", "error_type": type(error).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
