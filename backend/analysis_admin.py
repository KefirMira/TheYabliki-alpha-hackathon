"""Local administration only. No public retry endpoint and no AI imports."""
import argparse
import asyncio
import json
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from repositories.news_analysis_job_repository import NewsAnalysisJobRepository, AnalysisConflict


def arguments(argv=None):
    parser = argparse.ArgumentParser(description='Inspect uncertain attempts or authorize a bounded retry; never calls AI')
    parser.add_argument('action', choices=['inspect','close','approve-retry'])
    parser.add_argument('--company-source-id')
    parser.add_argument('--news-id',type=int)
    parser.add_argument('--run-id',type=int)
    parser.add_argument('--actor')
    parser.add_argument('--reason')
    parser.add_argument('--confirm-worker-stopped',action='store_true')
    parser.add_argument('--confirm-provider-finished',action='store_true')
    args=parser.parse_args(argv)
    if args.action!='inspect' and (not args.company_source_id or not args.news_id or args.news_id<1
            or not args.run_id or args.run_id<1 or not args.actor or not args.reason
            or not args.confirm_worker_stopped or not args.confirm_provider_finished):
        parser.error('Mutations require company/news/run, actor/reason and both termination confirmations')
    return args


async def execute(args, sessions):
    async with sessions() as session, session.begin():
        if args.action=='inspect':
            await session.execute(text('SET TRANSACTION READ ONLY'))
            return await NewsAnalysisJobRepository(session).inspect_stalled()
        await session.execute(text("SET LOCAL lock_timeout='5s'"))
        company=await session.scalar(text('SELECT id FROM public.companies WHERE source_id=:source'),
                                     {'source':args.company_source_id})
        if company is None:
            raise AnalysisConflict('COMPANY_NOT_FOUND')
        await NewsAnalysisJobRepository(session).administer(company,args.news_id,args.run_id,args.action,
            args.actor,args.reason,args.confirm_worker_stopped,args.confirm_provider_finished)
        return {'status':'updated','run_id':args.run_id,'action':args.action}


async def main_async(args):
    url=os.environ.get('DATABASE_URL','')
    if not url.startswith('postgresql+asyncpg://'):
        raise ValueError('DATABASE_URL must use postgresql+asyncpg')
    engine=create_async_engine(url,hide_parameters=True,connect_args={'timeout':5,'command_timeout':10})
    try:
        return await execute(args,async_sessionmaker(engine,expire_on_commit=False))
    finally:
        await engine.dispose()


def main(argv=None):
    args=arguments(argv)
    try:
        print(json.dumps(asyncio.run(main_async(args)),default=str,ensure_ascii=False))
        return 0
    except AnalysisConflict as error:
        print(json.dumps({'code':error.code,'run_id':error.run_id}))
    except Exception:
        print(json.dumps({'code':'ADMIN_DATABASE_OR_CONFIGURATION_ERROR'}))
    return 1


if __name__=='__main__':
    raise SystemExit(main())
