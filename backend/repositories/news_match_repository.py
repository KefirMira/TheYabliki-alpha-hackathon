"""Additive match history, independent of paid analyses and their evidence."""
import json

from sqlalchemy import text


class NewsMatchRepository:
    def __init__(self, session):
        self.session = session

    async def lock_news(self, news_id):
        row = (await self.session.execute(text('''SELECT id,title,content
            FROM public.news_articles WHERE id=:id FOR UPDATE'''), {'id': news_id})).mappings().first()
        if row is None:
            raise LookupError('NEWS_NOT_FOUND')
        return dict(row)

    async def catalogue(self):
        # One statement = one READ COMMITTED snapshot, even during registry updates.
        rows = (await self.session.execute(text('''
            SELECT c.id,c.source_id,c.name,c.inn,c.ogrn,
              coalesce(jsonb_agg(jsonb_build_object('alias_id',a.id,'name',a.name,
                'verified_by',a.verified_by,'provenance',a.provenance) ORDER BY a.id)
                FILTER (WHERE a.id IS NOT NULL), '[]'::jsonb) AS aliases
            FROM public.companies c LEFT JOIN public.company_verified_names a ON a.company_id=c.id
            GROUP BY c.id ORDER BY c.id'''))).mappings().all()
        return [dict(row) for row in rows]

    async def find(self, news_id, version, news_hash, dictionary_hash):
        return await self.session.scalar(text('''SELECT id FROM public.news_company_match_runs
            WHERE news_id=:news AND algorithm_version=:version AND news_hash=:nh AND dictionary_hash=:dh'''),
            {'news': news_id, 'version': version, 'nh': news_hash, 'dh': dictionary_hash})

    async def save(self, news_id, version, news_hash, dictionary_hash, snapshot, result):
        run_id = await self.session.scalar(text('''INSERT INTO public.news_company_match_runs
            (news_id,algorithm_version,news_hash,dictionary_hash,status,news_snapshot)
            VALUES (:news,:version,:nh,:dh,:status,CAST(:snapshot AS jsonb)) RETURNING id'''),
            {'news': news_id, 'version': version, 'nh': news_hash, 'dh': dictionary_hash,
             'status': result['status'], 'snapshot': json.dumps(snapshot, ensure_ascii=False)})
        for candidate in result['candidates']:
            await self.session.execute(text('''INSERT INTO public.news_company_match_candidates
                (run_id,company_id,company_snapshot,evidence)
                VALUES (:run,:company,CAST(:snapshot AS jsonb),CAST(:evidence AS jsonb))'''),
                {'run': run_id, 'company': candidate['company_id'],
                 'snapshot': json.dumps(candidate['company_snapshot'], ensure_ascii=False),
                 'evidence': json.dumps(candidate['evidence'], ensure_ascii=False)})
        return run_id

    async def get(self, news_id, run_id=None):
        run = (await self.session.execute(text('''SELECT * FROM public.news_company_match_runs
            WHERE news_id=:news AND (CAST(:run AS bigint) IS NULL OR id=:run) ORDER BY id DESC LIMIT 1'''),
            {'news': news_id, 'run': run_id})).mappings().first()
        if run is None:
            raise LookupError('MATCH_RESULT_NOT_FOUND')
        candidates = (await self.session.execute(text('''SELECT company_id,company_snapshot,evidence
            FROM public.news_company_match_candidates WHERE run_id=:run ORDER BY company_id'''),
            {'run': run['id']})).mappings().all()
        return {**dict(run), 'candidates': [dict(c) for c in candidates],
                'matched_company_ids': [c['company_id'] for c in candidates] if run['status'] == 'MATCHED' else []}
