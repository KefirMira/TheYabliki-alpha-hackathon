"""Additive offline collection import. NO real release exists during preparation.

The public CLI never imports fake records. Tests call the internal transaction
with explicitly labelled fake records only in their own isolated PostgreSQL.
"""
import asyncio
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from company_import.storage import target_url
from saved_pilot_demo import approved, MARKER, LOGIN, ARTIFACT_SHA256, VERSION as LEGACY_VERSION
from services.auth_service import verify_password
from services.synthetic_gateway_input import fixture, canonical
from services.pilot_collection_input import registry, scenario_input, digest
from services.pilot_collection_records import validate_record
from repositories.analysis_run_repository import AnalysisRunRepository
from repositories.company_analysis_repository import CompanyAnalysisRepository
from repositories.evidence_repository import EvidenceRepository

RELEASE = Path(__file__).with_name('fixtures')/'saved_pilot_collection_v1.json'
# Set ONLY after a separately authorized real generation and human export review.
RELEASE_SHA256 = '0c8dbcabdd3a0a343c6c669638b6d5e7bd9ceed22c62279b34af0c721f4f7cc2'
IMPORT_KEY = 'saved_pilot_collection_import'


def approved_records():
    if not RELEASE.exists():
        return []
    if RELEASE_SHA256 is None:
        raise ValueError('COLLECTION_RELEASE_NOT_APPROVED')
    if RELEASE.stat().st_size > 1_000_000:
        raise ValueError('COLLECTION_RELEASE_TOO_LARGE')
    data = json.loads(RELEASE.read_bytes())
    if digest(data) != RELEASE_SHA256:
        raise ValueError('COLLECTION_RELEASE_CHANGED')
    records = data['records']
    if len(records) != 8 or len({r['scenario_id'] for r in records}) != len(records):
        raise ValueError('COLLECTION_RELEASE_SHAPE')
    for record in records:
        validate_record(record, require_real=True)
    return records


async def legacy_anchor(c):
    data, bundle = approved()
    company = await c.scalar(text('SELECT id FROM companies WHERE source_id=:source'),
                             {'source':fixture()['source_id']})
    if company is None:
        raise ValueError('LEGACY_SEED_REQUIRED')
    rows = (await c.execute(text("""SELECT a.*, n.content AS news_content, r.status AS run_status,
        r.model_name FROM company_news_analyses a JOIN news_articles n ON n.id=a.news_id
        JOIN analysis_runs r ON r.id=a.analysis_run_id
        WHERE a.company_id=:company AND a.validation->'saved_pilot_import'->>'artifact_sha256'=:sha"""),
        {'company':company,'sha':ARTIFACT_SHA256})).mappings().all()
    if len(rows)!=1:
        raise ValueError('LEGACY_ANCHOR_AMBIGUOUS')
    row=rows[0]
    expected=json.loads(data['content'])
    pairs={'impact_summary':'summary','relevance_level':'relevance','risks':'risks',
           'opportunities':'opportunities','recommendations':'recommendations'}
    if any(row[k]!=expected[v] for k,v in pairs.items()):
        raise ValueError('LEGACY_CONTENT_CHANGED')
    if (row['news_content']!=fixture()['news'] or row['run_status']!='COMPLETED'
            or row['model_name']!=data['metadata']['model']
            or row['validation']['financial_review']!=data['financial_review']
            or row['validation']['orchestration']!=data['orchestration']):
        raise ValueError('LEGACY_PROVENANCE_CHANGED')
    expected_sources=[{**e.model_dump(exclude={'text'}),'synthetic':True,
        'provenance':{'declared_format':'TXT','format_verified':False,
                      'publisher':None,'attribution_status':'UNKNOWN'}} for e in bundle.evidence]
    if row['source_snapshot']!=expected_sources:
        raise ValueError('LEGACY_SOURCE_SNAPSHOT_CHANGED')
    evidence=(await c.execute(text("""SELECT evidence_text,document_name,document_page,chunk_id
        FROM insight_evidence WHERE company_news_analysis_id=:id ORDER BY id"""),{'id':row['id']})).all()
    if [tuple(e) for e in evidence] != [(e.text,e.document,e.page,e.chunk_id) for e in bundle.evidence]:
        raise ValueError('LEGACY_EVIDENCE_CHANGED')
    return company


async def owned_digest(c, insight):
    # Scope only this imported result and its source rows. User-owned rows do not
    # invalidate upgrades. The digest excludes only its own self-referential field.
    value=await c.scalar(text("""SELECT jsonb_build_object(
        'analysis',to_jsonb(a) || jsonb_build_object('validation',a.validation #- '{saved_pilot_collection_import,owned_sha256}'),
        'news',to_jsonb(n),'run',to_jsonb(r),
        'evidence',(SELECT jsonb_agg(to_jsonb(e) ORDER BY e.id) FROM insight_evidence e
                    WHERE e.company_news_analysis_id=a.id))
        FROM company_news_analyses a JOIN news_articles n ON n.id=a.news_id
        JOIN analysis_runs r ON r.id=a.analysis_run_id WHERE a.id=:id"""),{'id':insight})
    return digest(value)


async def _apply_records(value, expected_database, password, records, *, fake_test=False):
    url=target_url(value,expected_database)
    if fake_test and not expected_database.startswith('test_news_identity_'):
        raise ValueError('DEDICATED_FAKE_TEST_DATABASE_REQUIRED')
    if not records or len(records)>8 or len({r['scenario_id'] for r in records})!=len(records):
        raise ValueError('COLLECTION_RECORD_SET_INVALID')
    bundles=[validate_record(r,require_real=not fake_test) for r in records]
    if fake_test and any(r['mode']!='FAKE_TEST_ONLY' for r in records):
        raise ValueError('FAKE_TEST_RECORD_REQUIRED')
    engine=create_async_engine(url,poolclass=NullPool,hide_parameters=True,
        connect_args={'timeout':5,'command_timeout':30})
    counts={'created':0,'unchanged':0,'new_llm_requests':0,
            'mode':'FAKE_TEST_ONLY' if fake_test else 'SAVED_REAL_COLLECTION'}
    try:
        async with engine.begin() as c:
            await c.execute(text('SELECT pg_advisory_xact_lock(1251001)'))
            marker=await c.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"))
            if marker!=MARKER:raise ValueError('ISOLATED_PILOT_MARKER_REQUIRED')
            legacy = await c.scalar(text('SELECT id FROM companies WHERE source_id=:source'), {'source':fixture()['source_id']})
            if legacy is None:
                from saved_pilot_demo import import_pilot
                await import_pilot(value,expected_database,password,apply=True,_connection=c)
            await legacy_anchor(c)
            uid=uuid5(NAMESPACE_URL,LEGACY_VERSION+':'+LOGIN)
            user=(await c.execute(text('SELECT id,password_hash,is_active FROM auth_users WHERE login=:login FOR UPDATE'),{'login':LOGIN})).mappings().one()
            if user['id']!=uid or not user['is_active'] or not await asyncio.to_thread(verify_password,user['password_hash'],password):
                raise ValueError('COLLECTION_ACCOUNT_MISMATCH')
            allowed=[p['source_id'] for p in registry()['companies']]
            scope=(await c.execute(text("""SELECT c.source_id,m.can_analyze FROM auth_user_companies m
                JOIN companies c ON c.id=m.company_id WHERE m.user_id=:user"""),{'user':uid})).all()
            if any(row.source_id not in allowed or row.can_analyze for row in scope):
                raise ValueError('COLLECTION_ACCOUNT_SCOPE_MISMATCH')
            for record,bundle in zip(records,bundles):
                scenario,profile,fragments=scenario_input(record['scenario_id'])
                existing=(await c.execute(text("""SELECT id,company_id,news_id,validation FROM company_news_analyses
                    WHERE validation->'saved_pilot_collection_import'->>'scenario_id'=:scenario"""),
                    {'scenario':record['scenario_id']})).mappings().all()
                if existing:
                    if len(existing)!=1:raise ValueError('COLLECTION_IDENTITY_AMBIGUOUS')
                    meta=existing[0]['validation'][IMPORT_KEY]
                    if meta['record_sha256']!=digest(record) or meta['owned_sha256']!=await owned_digest(c,existing[0]['id']):
                        raise ValueError('COLLECTION_IMPORTED_RECORD_CHANGED')
                    acl=await c.scalar(text('SELECT EXISTS(SELECT 1 FROM auth_user_companies WHERE user_id=:user AND company_id=:company AND NOT can_analyze) AND EXISTS(SELECT 1 FROM auth_news_grants WHERE user_id=:user AND news_id=:news)'),{'user':uid,'company':existing[0]['company_id'],'news':existing[0]['news_id']})
                    if acl is not True:raise ValueError('COLLECTION_ACL_CHANGED')
                    counts['unchanged']+=1
                    continue
                source=profile['source_id']
                company=(await c.execute(text('SELECT id,source_data FROM companies WHERE source_id=:source FOR UPDATE'),{'source':source})).mappings().one_or_none()
                if company is None:
                    company_id=await c.scalar(text("""INSERT INTO companies(source_id,name,industry,source_data)
                        VALUES(:source,:name,:industry,CAST(:data AS jsonb)) RETURNING id"""),
                        {'source':source,'name':profile['display_name'],
                         'industry':profile['context']['facts']['industry']['value'],
                         'data':canonical({'synthetic':True,'pilot_collection_context':profile['context']})})
                else:
                    company_id=company['id']
                    if source!=fixture()['source_id'] and company['source_data'].get('pilot_collection_context')!=profile['context']:
                        raise ValueError('COLLECTION_COMPANY_COLLISION')
                await c.execute(text('INSERT INTO auth_user_companies(user_id,company_id,can_analyze) VALUES(:user,:company,false) ON CONFLICT DO NOTHING'),{'user':uid,'company':company_id})
                collision = await c.scalar(text("SELECT EXISTS(SELECT 1 FROM news_articles WHERE source_name='synthetic-pilot-collection' AND source_id=:scenario)"), {'scenario':scenario['scenario_id']})
                if collision:
                    raise ValueError('COLLECTION_NEWS_COLLISION')
                news=await c.scalar(text("""INSERT INTO news_articles(title,content,input_kind,source_name,source_id)
                    VALUES(:title,:content,'MANUAL','synthetic-pilot-collection',:scenario) RETURNING id"""),
                    {'title':scenario['title'],'content':scenario['news'],'scenario':scenario['scenario_id']})
                await c.execute(text('INSERT INTO auth_news_grants(user_id,news_id) VALUES(:user,:news)'),{'user':uid,'news':news})
                async with async_sessionmaker(bind=c,expire_on_commit=False,join_transaction_mode='create_savepoint')() as session, session.begin():
                    run=await AnalysisRunRepository(session).start(company_id)
                    insight=await CompanyAnalysisRepository(session).create(run,company_id,news,bundle.model_copy(update={'orchestration':None}))
                    for fragment in bundle.evidence:await EvidenceRepository(session).create(insight,fragment)
                    await AnalysisRunRepository(session).finish(run,'COMPLETED',model_name=bundle.model_name,prompt_version=bundle.prompt_version)
                    await session.flush()
                sources=[{**fragment,'synthetic':False,'provenance':{
                    'declared_format':'TXT','format_verified':False,'publisher':None,
                    'attribution_status':'UNKNOWN','origin_url':fragment['origin_url'],
                    'origin_publisher':fragment['origin_publisher'],
                    'original_format':'HTML','locator':fragment['locator'],
                    'page_is_exported_excerpt':True}} for fragment in fragments]
                await c.execute(text("""UPDATE company_news_analyses SET source_snapshot=CAST(:sources AS jsonb),
                    validation=validation || jsonb_build_object(CAST(:key AS text),CAST(:metadata AS jsonb),'orchestration',CAST(:trace AS jsonb)) WHERE id=:id"""),
                    {'id':insight,'sources':canonical(sources),'key':IMPORT_KEY,'trace':canonical(record['orchestration']),
                     'metadata':canonical({'scenario_id':scenario['scenario_id'],'record_sha256':digest(record),
                         'mode':record['mode'],'generated_at':record['generated_at'],
                         'model':record['model'],'content_sha256':record['content_sha256'],
                         'generation_metadata':record.get('generation_metadata',{}),
                         'expert_review':record.get('expert_review',{}),'imported_at':datetime.now(timezone.utc).isoformat(),
                         'new_llm_requests':0,'input_sha256':record['plan']['dto_sha256']})})
                owned=await owned_digest(c,insight)
                await c.execute(text("""UPDATE company_news_analyses SET validation=jsonb_set(validation,
                    '{saved_pilot_collection_import,owned_sha256}',to_jsonb(CAST(:sha AS text))) WHERE id=:id"""),{'id':insight,'sha':owned})
                counts['created']+=1
            return counts
    finally:await engine.dispose()


async def import_approved_collection(value,expected_database,password):
    records=approved_records()
    if not records:raise ValueError('NO_APPROVED_COLLECTION')
    return await _apply_records(value,expected_database,password,records)
