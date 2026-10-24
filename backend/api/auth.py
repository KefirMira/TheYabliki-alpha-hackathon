"""Fail-closed HTTP auth. All DB scopes end before analysis execution."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.exc import SQLAlchemyError
from db.session import get_session_factory, unavailable
from repositories.auth_repository import AuthRepository
from schemas.auth import CurrentUser, LoginInput, SessionResponse
from schemas.http_docs import APIError
from services.auth_service import AuthService, denied, unauthorized, TOKEN_PATTERN

bearer = HTTPBearer(auto_error=False)
router = APIRouter(tags=['authentication'])
AUTH_ERRORS = {401:{'model':APIError},403:{'model':APIError},503:{'model':APIError}}


def factory(request):
    return get_session_factory(request)


async def current_actor(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    # Missing/malformed credentials must be 401 even when the database is unavailable.
    if (credentials is None or credentials.scheme.lower() != 'bearer'
            or not TOKEN_PATTERN.fullmatch(credentials.credentials)):
        raise unauthorized()
    try:
        return await AuthService(factory(request)).authenticate(credentials.credentials)
    except (SQLAlchemyError,OSError,TimeoutError):
        raise unavailable() from None


async def company_read(source_id: str, request: Request, actor=Depends(current_actor)):
    return await company_access(source_id,request,actor,False)


async def company_write(source_id: str, request: Request, actor=Depends(current_actor)):
    return await company_access(source_id,request,actor,True)


async def company_access(source_id,request,actor,write):
    try:
        async with factory(request)() as session:
            allowed = await AuthRepository(session).company_allowed(actor.user_id,source_id,write)
        if not allowed:
            raise denied()
        return actor
    except (SQLAlchemyError,OSError,TimeoutError):
        raise unavailable() from None


async def legacy_denied(actor=Depends(current_actor)):
    # No user permission in this slice can enable a legacy paid endpoint.
    raise denied()


@router.post('/api/auth/login',response_model=SessionResponse,
             responses={401:{'model':APIError},422:{'model':APIError},429:{'model':APIError},503:{'model':APIError}},
             description='Индивидуальная сессия на час. Пароль и токен не журналируются; без публичной регистрации.')
async def login(body: LoginInput, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    try:
        peer = request.client.host if request.client else '<unknown>'
        return await AuthService(factory(request)).login(body.login,body.password.get_secret_value(),peer)
    except (SQLAlchemyError,OSError,TimeoutError):
        raise unavailable() from None


@router.get('/api/me',response_model=CurrentUser,responses=AUTH_ERRORS,
            description='Текущий пользователь и серверный список доступных компаний.')
async def me(request: Request, response: Response, actor=Depends(current_actor)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        async with factory(request)() as session:
            companies = await AuthRepository(session).memberships(actor.user_id)
        return CurrentUser(user_id=actor.user_id,login=actor.login,companies=companies)
    except (SQLAlchemyError,OSError,TimeoutError):
        raise unavailable() from None


@router.post('/api/auth/logout',status_code=204,responses=AUTH_ERRORS,
             description='Отзыв текущего Bearer-токена. Другие сессии не затрагиваются.')
async def logout(request: Request, actor=Depends(current_actor)):
    try:
        async with factory(request)() as session, session.begin():
            await AuthRepository(session).revoke(actor.token_hash)
    except (SQLAlchemyError,OSError,TimeoutError):
        raise unavailable() from None
    return Response(status_code=204,headers={'Cache-Control':'no-store'})
