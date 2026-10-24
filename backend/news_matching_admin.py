"""Local, single-news administration. Not registered with FastAPI; never imports AI."""
import argparse
import asyncio
import json
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.news_matching_service import NewsMatchingService


def arguments(argv=None):
    parser = argparse.ArgumentParser(description='Deterministic single-news matching; no AI')
    parser.add_argument('action', choices=['match', 'show'])
    parser.add_argument('--news-id', required=True, type=int)
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--confirm-write', action='store_true')
    args = parser.parse_args(argv)
    if args.news_id < 1 or (args.run_id is not None and args.run_id < 1):
        parser.error('Identifiers must be positive')
    if args.action == 'match' and (not args.confirm_write or args.run_id is not None):
        parser.error('match requires --confirm-write and does not accept --run-id')
    return args


async def execute(args, sessions):
    service = NewsMatchingService(sessions)
    if args.action == 'match':
        return await service.match(args.news_id)
    return await service.show(args.news_id, args.run_id)


async def main_async(args):
    url = os.environ.get('DATABASE_URL', '')
    if not url.startswith('postgresql+asyncpg://'):
        raise ValueError('DATABASE_URL must use postgresql+asyncpg')
    engine = create_async_engine(url, hide_parameters=True,
                                 connect_args={'timeout': 5, 'command_timeout': 15})
    try:
        return await execute(args, async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


def main(argv=None):
    args = arguments(argv)
    try:
        print(json.dumps(asyncio.run(main_async(args)), ensure_ascii=False, default=str))
        return 0
    except LookupError as error:
        print(json.dumps({'code': str(error)}))
    except Exception:
        # No DSN, SQL parameters, news body or credentials in error diagnostics.
        print(json.dumps({'code': 'MATCHING_DATABASE_OR_CONFIGURATION_ERROR'}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
