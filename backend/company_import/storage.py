"""Single-transaction writer restricted to explicitly marked loopback test databases."""
import copy
import json
import re

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from . import VERSION
from .validation import Audit, ImportProblem, SOURCE

MARKER = 'pulse:isolated-company-import:v1'
NAMESPACE = '_company_profile_csv_v1'


def target_url(value, expected_database):
    try:
        url = make_url(value)
        if (url.drivername != 'postgresql+asyncpg' or url.host not in {'127.0.0.1', '::1'}
                or not url.port or not url.username or not url.password or url.query
                or not re.fullmatch(r'test_[a-z0-9_]{1,80}', expected_database or '')
                or url.database != expected_database):
            raise ValueError
        return url
    except Exception:
        raise ImportProblem('ISOLATED_TARGET_REQUIRED') from None


async def apply_audit(audit: Audit, url, expected_database, *, update_existing=False, allow_partial=False):
    """No implicit retries: a commit with an uncertain outcome must be checked by reimport."""
    url = target_url(url, expected_database)
    if audit.rejected_lines and not allow_partial:
        raise ImportProblem('PARTIAL_IMPORT_CONFIRMATION_REQUIRED')
    if not audit.accepted:
        raise ImportProblem('NO_ELIGIBLE_PROFILES')
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True,
                                 connect_args={'timeout': 5, 'command_timeout': 30})
    counts = dict(created=0, updated=0, unchanged=0, dated_revenue_preserved=0)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            await connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            target = (await connection.execute(text('''
                SELECT current_database() AS name,
                       shobj_description(oid, 'pg_database') AS marker
                FROM pg_catalog.pg_database WHERE datname=current_database()
            '''))).mappings().one()
            if target['name'] != expected_database or target['marker'] != MARKER:
                raise ImportProblem('ISOLATED_DATABASE_MARKER_REQUIRED')
            # Stable lock order plus UNIQUE(source_id) handles independent concurrent importers.
            for profile in sorted(audit.accepted, key=lambda item: item.source_id):
                values = {'source_id': profile.source_id, 'industry': profile.attributes['MAINOKVED_NAME'],
                          'region': profile.attributes['REGION'], 'revenue': profile.revenue,
                          'status': profile.status}
                created = (await connection.execute(text('''
                    INSERT INTO public.companies(source_id,name,industry,region,revenue,client_status)
                    VALUES (:source_id,'',:industry,:region,:revenue,:status)
                    ON CONFLICT(source_id) DO NOTHING RETURNING id
                '''), values)).scalar_one_or_none()
                old = (await connection.execute(text('''
                    SELECT id, industry,region,revenue,revenue_year,client_status,source_data
                    FROM public.companies WHERE source_id=:source_id FOR UPDATE
                '''), values)).mappings().one()
                data = copy.deepcopy(old['source_data'])
                if not isinstance(data, dict):
                    raise ImportProblem('SOURCE_DATA_OBJECT_REQUIRED')
                previous = data.get(NAMESPACE)
                if previous is not None and (not isinstance(previous, dict)
                        or previous.get('source') != SOURCE or not isinstance(previous.get('history'), list)
                        or not isinstance(previous.get('current'), dict)):
                    raise ImportProblem('IMPORT_PROVENANCE_CONFLICT')
                revenue = old['revenue'] if old['revenue_year'] is not None else profile.revenue
                if old['revenue_year'] is not None and old['revenue'] != profile.revenue:
                    counts['dated_revenue_preserved'] += 1
                changed = (old['industry'] != values['industry'] or old['region'] != values['region']
                           or old['revenue'] != revenue or old['client_status'] != profile.status)
                attributes_changed = previous is not None and previous['current'].get('attributes') != profile.attributes
                if created is None and not update_existing and (previous is None or changed or attributes_changed):
                    raise ImportProblem('EXISTING_PROFILE_REQUIRES_UPDATE')
                current = {'file_sha256': audit.file_hash, 'row_sha256': profile.row_hash,
                           'lines': profile.lines, 'attributes': profile.attributes, 'importer_version': VERSION}
                if previous is not None and previous['current'] == current and not changed:
                    counts['unchanged'] += 1
                    continue
                history = previous['history'] + [previous['current']] if previous else []
                data[NAMESPACE] = {'source': SOURCE, 'current': current, 'history': history}
                values.update(id=old['id'], revenue=revenue, data=json.dumps(data, ensure_ascii=False))
                await connection.execute(text('''
                    UPDATE public.companies SET industry=:industry,region=:region,revenue=:revenue,
                        client_status=:status,source_data=CAST(:data AS jsonb),updated_at=now()
                    WHERE id=:id
                '''), values)
                counts['created' if created is not None else 'updated'] += 1
        return counts
    finally:
        await engine.dispose()
