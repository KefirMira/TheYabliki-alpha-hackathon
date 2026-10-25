"""Dedicated synthetic submission provisioning. No SDK, real dataset or ORM DDL."""
import asyncio
import csv
import io
import json
import os
import re
import tempfile
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from company_import.validation import HEADERS,audit_file
from company_import.storage import apply_audit,target_url,MARKER
from services.auth_service import HASHER,verify_password

DATABASE="test_submission_demo"
LOGIN="demo-analyst"

async def seed():
    password=os.environ.get("SUBMISSION_DEMO_PASSWORD","")
    if not 12<=len(password)<=256 or password.startswith("REPLACE_"):
        raise ValueError("PASSWORD_REQUIRED")
    url=target_url(os.environ.get("SUBMISSION_SEED_DATABASE_URL"),DATABASE)
    if not re.fullmatch(r"[a-fA-F0-9]{32,128}",url.password or ""):
        raise ValueError("LOCAL_HEXADECIMAL_DB_PASSWORD_REQUIRED")
    fixture=json.loads((Path(__file__).parent/"fixtures/submission_profiles.json").read_text(encoding="utf-8"))
    if fixture.get("synthetic") is not True or len(fixture["profiles"])!=2:
        raise ValueError("SYNTHETIC_FIXTURE_REQUIRED")
    rows=fixture["profiles"]
    engine=create_async_engine(url,poolclass=NullPool,hide_parameters=True)
    try:
        async with engine.connect() as c:
            if await c.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"))!=MARKER:
                raise ValueError("ISOLATION_MARKER_REQUIRED")
            extras=await c.scalar(text("SELECT count(*) FROM companies WHERE source_id NOT IN (:a,:b) OR source_id IS NULL"),
                {"a":rows[0]["SYNTHETIC_U"],"b":rows[1]["SYNTHETIC_U"]})
            if extras:raise ValueError("DEDICATED_DATABASE_REQUIRED")
        buffer=io.StringIO(newline="")
        writer=csv.DictWriter(buffer,fieldnames=HEADERS,delimiter=";",lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"synthetic.csv"
            path.write_bytes(buffer.getvalue().encode())
            audit=audit_file(path)
            counts=await apply_audit(audit,url,DATABASE)
        uid=uuid5(NAMESPACE_URL,"pulse-submission-demo-analyst-v1")
        async with engine.begin() as c:
            await c.execute(text("SELECT pg_advisory_xact_lock(1270001)"))
            user=(await c.execute(text("SELECT id,password_hash,is_active FROM auth_users WHERE login=:login FOR UPDATE"),
                {"login":LOGIN})).mappings().one_or_none()
            if user is None:
                await c.execute(text("INSERT INTO auth_users(id,login,password_hash) VALUES(:id,:login,:hash)"),
                    {"id":uid,"login":LOGIN,"hash":HASHER.hash(password)})
            elif user["id"]!=uid or not user["is_active"] or not verify_password(user["password_hash"],password):
                raise ValueError("EXISTING_ACCOUNT_MISMATCH")
            await c.execute(text("""INSERT INTO auth_user_companies(user_id,company_id,can_analyze)
                SELECT :user,id,true FROM companies ON CONFLICT DO NOTHING"""),{"user":uid})
            allowed=await c.scalar(text("SELECT count(*) FROM auth_user_companies WHERE user_id=:user AND can_analyze"),{"user":uid})
            if allowed!=2:raise ValueError("MEMBERSHIP_MISMATCH")
        print(json.dumps({"status":"SYNTHETIC_SEED_READY","profiles":counts,"companies":2,"account":LOGIN,"llm_calls":0}))
    finally:
        await engine.dispose()

if __name__=="__main__":
    try:asyncio.run(seed())
    except Exception:raise SystemExit("SUBMISSION_SEED_FAILED: check isolated database, unchanged env and password length; no secrets printed")
