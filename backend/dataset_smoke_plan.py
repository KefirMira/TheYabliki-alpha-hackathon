"""Explicit --plan only, isolated loopback PostgreSQL, interactive Bearer, no dispatch."""
import argparse
import asyncio
import getpass
import json
import os
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.pool import NullPool
from company_import.storage import target_url
from services.auth_service import AuthService
from services.dataset_analysis import load_manifest
from services.dataset_smoke_plan import prepare_smoke_plan

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",action="store_true",required=True)
    parser.add_argument("--expected-database",required=True)
    parser.add_argument("--company",required=True)
    parser.add_argument("--news-id",type=int,required=True)
    args=parser.parse_args()
    async def run():
        url=target_url(os.environ.get("DATASET_PLAN_DATABASE_URL"),args.expected_database)
        engine=create_async_engine(url,poolclass=NullPool,hide_parameters=True,
            connect_args={"timeout":5,"command_timeout":15})
        try:
            sessions=async_sessionmaker(engine,expire_on_commit=False)
            actor=await AuthService(sessions).authenticate(getpass.getpass("Bearer token (not logged): "))
            plan=await prepare_smoke_plan(sessions,actor,args.company,args.news_id,load_manifest())
            print(json.dumps(plan.summary()))
        finally:
            await engine.dispose()
    try:
        asyncio.run(run())
    except Exception:
        parser.exit(1,"DATASET_PLAN_NOT_PREPARED\n")

if __name__=="__main__":
    main()
