"""Explicit local provisioning, never a public registration endpoint.

Uses the existing isolated-import address guard and a separate database marker.
Passwords are read interactively, never from argv, environment, files or output.
"""
import argparse
import asyncio
import getpass
import json
import os
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from company_import.storage import target_url
from services.auth_service import HASHER, normalized_login

MARKER='pulse:isolated-auth-demo:v1'


async def provision(value,expected_database,login,password,company):
    url=target_url(value,expected_database)
    if (not normalized_login(login) or not login.startswith('synthetic-')
            or not 12<=len(password)<=256 or company not in {'SYNTH-AUTH-A','SYNTH-AUTH-B'}):
        raise ValueError('SYNTHETIC_ACCOUNT_REQUIRED')
    encoded=await asyncio.to_thread(HASHER.hash,password)
    engine=create_async_engine(url,poolclass=NullPool,hide_parameters=True,
                               connect_args={'timeout':5,'command_timeout':10})
    try:
        async with engine.begin() as c:
            marker=await c.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"))
            if marker!=MARKER:raise ValueError('ISOLATED_AUTH_MARKER_REQUIRED')
            # Existing real/demo profiles cannot be repurposed by this CLI.
            await c.execute(text('''INSERT INTO companies(source_id,name,source_data)
                VALUES (:source,'Synthetic authentication fixture',jsonb_build_object('auth_demo_fixture',true))
                ON CONFLICT(source_id) DO NOTHING'''),{'source':company})
            row=(await c.execute(text('SELECT id,source_data FROM companies WHERE source_id=:source FOR UPDATE'),
                                 {'source':company})).mappings().one()
            if row['source_data']!={'auth_demo_fixture':True}:raise ValueError('SYNTHETIC_COMPANY_REQUIRED')
            user_id=uuid4()
            await c.execute(text('INSERT INTO auth_users(id,login,password_hash) VALUES (:id,:login,:hash)'),
                            {'id':user_id,'login':normalized_login(login),'hash':encoded})
            await c.execute(text('INSERT INTO auth_user_companies(user_id,company_id,can_analyze) VALUES (:id,:company,true)'),
                            {'id':user_id,'company':row['id']})
    finally:
        await engine.dispose()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Create one isolated synthetic account; never resets existing credentials')
    parser.add_argument('--confirm-isolated',action='store_true',required=True)
    parser.add_argument('--expected-database',required=True)
    parser.add_argument('--login',required=True)
    parser.add_argument('--company',choices=['SYNTH-AUTH-A','SYNTH-AUTH-B'],required=True)
    args=parser.parse_args(argv)
    try:
        password=getpass.getpass('Synthetic password (12-256 characters): ')
        confirmation=getpass.getpass('Repeat password: ')
        if password!=confirmation:raise ValueError('PASSWORD_CONFIRMATION_MISMATCH')
        asyncio.run(provision(os.environ.get('AUTH_DEMO_DATABASE_URL',''),args.expected_database,args.login,password,args.company))
    except Exception:
        print(json.dumps({'code':'AUTH_DEMO_PROVISION_FAILED_VERIFY_TARGET'}))
        return 1
    print(json.dumps({'created':True,'synthetic':True}))
    return 0


if __name__=='__main__':raise SystemExit(main())
