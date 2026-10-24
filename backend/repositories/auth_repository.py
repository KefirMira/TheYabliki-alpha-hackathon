"""Auth projections use SQL-owned tables; no ORM DDL or global connections."""
from sqlalchemy import text


class AuthRepository:
    def __init__(self, session):
        self.session = session

    async def user(self, login, lock=False):
        result = await self.session.execute(text(
            'SELECT id,login,password_hash,is_active FROM public.auth_users WHERE login=:login'
            + (' FOR UPDATE' if lock else '')), {'login': login})
        return result.mappings().one_or_none()

    async def principal(self, token_hash):
        result = await self.session.execute(text('''SELECT u.id,u.login
            FROM public.auth_sessions s JOIN public.auth_users u ON u.id=s.user_id
            WHERE s.token_hash=:hash AND s.revoked_at IS NULL
            AND s.expires_at>clock_timestamp() AND u.is_active'''), {'hash': token_hash})
        return result.mappings().one_or_none()

    async def create_session(self, user_id, token_hash):
        await self.session.execute(text('''INSERT INTO public.auth_sessions(token_hash,user_id,expires_at)
            VALUES (:hash,:user_id,now()+interval '1 hour')'''), {'hash':token_hash,'user_id':user_id})

    async def revoke(self, token_hash):
        await self.session.execute(text('''UPDATE public.auth_sessions SET revoked_at=clock_timestamp()
            WHERE token_hash=:hash AND revoked_at IS NULL'''), {'hash':token_hash})

    async def company_allowed(self, user_id, source_id, write=False):
        return bool(await self.session.scalar(text('''SELECT EXISTS(
            SELECT 1 FROM public.auth_user_companies m JOIN public.companies c ON c.id=m.company_id
            JOIN public.auth_users u ON u.id=m.user_id
            WHERE m.user_id=:user_id AND c.source_id=:source_id AND u.is_active
            AND (:write=FALSE OR m.can_analyze))'''), dict(user_id=user_id,source_id=source_id,write=write)))

    async def news_allowed(self, user_id, news_id):
        return bool(await self.session.scalar(text('''SELECT EXISTS(SELECT 1 FROM public.auth_news_grants
            WHERE user_id=:user_id AND news_id=:news_id)'''), dict(user_id=user_id,news_id=news_id)))

    async def grant_news(self, user_id, news_id):
        # Called only on a newly inserted row or by the restricted provisioning CLI.
        await self.session.execute(text('''INSERT INTO public.auth_news_grants(user_id,news_id)
            VALUES (:user_id,:news_id) ON CONFLICT DO NOTHING'''), dict(user_id=user_id,news_id=news_id))

    async def memberships(self, user_id):
        result = await self.session.execute(text('''SELECT c.source_id,
            CASE WHEN btrim(c.name) IN ('',btrim(c.source_id)) THEN NULL ELSE c.name END AS name,
            m.can_analyze FROM public.auth_user_companies m JOIN public.companies c ON c.id=m.company_id
            WHERE m.user_id=:user_id AND c.source_id IS NOT NULL ORDER BY c.source_id'''), {'user_id':user_id})
        return list(result.mappings().all())
