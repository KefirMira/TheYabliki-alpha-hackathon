"""Individual revocable sessions. No JWT signing secret or shared demo token."""
import asyncio
import hashlib
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException
from repositories.auth_repository import AuthRepository
from schemas.auth import Principal, SessionResponse

HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(24))
KDF_GATE = threading.BoundedSemaphore(4)
KDF_EXECUTOR = ThreadPoolExecutor(max_workers=4,thread_name_prefix='auth-kdf')
TOKEN_PATTERN = re.compile(r'[A-Za-z0-9_-]{43}')


def denied():
    return HTTPException(403, detail={'code':'ACCESS_DENIED','message':'Доступ запрещён'})


def unauthorized():
    return HTTPException(401, detail={'code':'AUTHENTICATION_REQUIRED','message':'Нужна действующая сессия'},
                         headers={'WWW-Authenticate':'Bearer'})


def token_digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def normalized_login(value):
    value = value.strip().lower()
    return value if re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,63}', value) else ''


def verify_password(encoded, password):
    try:
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


class LoginLimiter:
    """Bounded single-process throttle; replicas require a shared limiter before deployment."""
    def __init__(self, clock=time.monotonic, capacity=10000):
        self.clock, self.capacity = clock, capacity
        self.entries = {}
        self.lock = threading.Lock()
        self.salt = secrets.token_bytes(32)

    def check(self, login, peer):
        with self.lock:
            now = self.clock()
            self.entries = {k:v for k,v in self.entries.items() if v[0]>now}
            keys = [(hashlib.sha256(self.salt+b'login:'+login.encode()).digest(),5),
                    (hashlib.sha256(self.salt+b'peer:'+peer.encode()).digest(),30)]
            if (len(self.entries)+sum(k not in self.entries for k,_ in keys)>self.capacity
                    or any(self.entries.get(k,(now+900,0))[1]>=limit for k,limit in keys)):
                raise HTTPException(429,detail={'code':'LOGIN_RATE_LIMITED','message':'Попробуйте позже'},
                                    headers={'Retry-After':'900'})
            for k,_ in keys:
                end,count = self.entries.get(k,(now+900,0))
                self.entries[k] = (end,count+1)


LOGIN_LIMITER = LoginLimiter()


class AuthService:
    def __init__(self, sessions):
        self.sessions = sessions

    async def login(self, login, password, peer):
        normalized = normalized_login(login)
        LOGIN_LIMITER.check(normalized or '<invalid>',peer)
        async with self.sessions() as session:
            row = await AuthRepository(session).user(normalized)
        encoded = row['password_hash'] if row else DUMMY_HASH
        if not KDF_GATE.acquire(blocking=False):
            raise HTTPException(429,detail={'code':'LOGIN_RATE_LIMITED','message':'Попробуйте позже'},
                                headers={'Retry-After':'5'})
        try:
            work = KDF_EXECUTOR.submit(verify_password,encoded,password)
        except Exception:
            KDF_GATE.release()
            raise
        # Cancellation must not free a slot while the Argon2 worker still runs.
        work.add_done_callback(lambda _: KDF_GATE.release())
        valid = await asyncio.shield(asyncio.wrap_future(work))
        if not valid or row is None or not row['is_active']:
            raise HTTPException(401,detail={'code':'INVALID_CREDENTIALS','message':'Неверные учётные данные'},
                                headers={'WWW-Authenticate':'Bearer'})
        token = secrets.token_urlsafe(32)
        async with self.sessions() as session, session.begin():
            repository = AuthRepository(session)
            current = await repository.user(normalized,lock=True)
            if not current or not current['is_active'] or current['password_hash'] != encoded:
                raise unauthorized()
            await repository.create_session(current['id'],token_digest(token))
        return SessionResponse(access_token=token)

    async def authenticate(self, token):
        if not TOKEN_PATTERN.fullmatch(token):
            raise unauthorized()
        digest = token_digest(token)
        async with self.sessions() as session:
            row = await AuthRepository(session).principal(digest)
        if row is None:
            raise unauthorized()
        return Principal(row['id'],row['login'],digest)
