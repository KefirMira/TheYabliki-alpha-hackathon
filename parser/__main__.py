import argparse
import json
import sys
import signal
import sqlite3
from threading import Event
from xml.etree.ElementTree import ParseError

from .collector import collect_once, poll, save_report
from .config import Config


def main(argv=None):
    cli = argparse.ArgumentParser(description="Durable RSS collector; HTTP requires explicit opt-in; no AI or PostgreSQL")
    modes = cli.add_mutually_exclusive_group(required=True)
    modes.add_argument("--once", action="store_true", help="Scan and deliver due queued items once")
    modes.add_argument("--poll", action="store_true", help="Repeat until Ctrl+C / SIGTERM")
    cli.add_argument('--reset-source-errors',action='store_true',help='Explicitly clear HTTP source error exhaustion; preserve validators, queue and rate deadline')
    args = cli.parse_args(argv)
    stop, previous = Event(), {}
    def shutdown(signum, frame):
        stop.set()
    def output(report):
        save_report(config.report_path, report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    try:
        config = Config.from_env()
        if args.reset_source_errors and (args.poll or config.source_mode!='http'):
            raise ValueError('Reset requires HTTP --once; automatic reset during polling is forbidden')
        for number in (signal.SIGINT, signal.SIGTERM):
            previous[number] = signal.signal(number, shutdown)
        if args.poll:
            poll(config, stop, output)
            return 0
        report = collect_once(config, stop=stop,**({'reset_source':True} if args.reset_source_errors else {}))
        output(report)
    except (ValueError, OSError, ParseError, sqlite3.Error, RuntimeError) as error:
        # No response bodies/credentials/news text in stderr. Detailed item codes are in the report.
        print(json.dumps({"status": "run_error", "error_type": type(error).__name__}), file=sys.stderr)
        return 2
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    if report.get('source_error'):
        print(json.dumps({"status": "source_error", "error_type": report['source_error']}), file=sys.stderr)
        return 2
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
