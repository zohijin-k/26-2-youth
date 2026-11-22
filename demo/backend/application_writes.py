"""Single-host, cross-worker serialization of applicant writes.

Locks are advisory POSIX file locks: all workers must share this local lock
namespace and database. Multi-host/remote-database deployments require database
row/advisory locking instead. Lock files are deliberately never unlinked.
"""
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from hashlib import sha256
import asyncio
import fcntl
import os
from pathlib import Path
import tempfile

from . import models

_active = ContextVar('application_write_guards', default=frozenset())


def _key(application_id: int) -> str:
    url = models.engine.url
    database = str(url)
    if url.get_backend_name() == 'sqlite' and url.database and url.database != ':memory:':
        database = str(url.set(database=str(Path(url.database).resolve())))
    return sha256(database.encode()).hexdigest() + '-' + str(application_id)


def _open(key: str):
    directory = Path(tempfile.gettempdir()) / f'jeonbuk-application-writes-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    return os.open(directory / (key + '.lock'), os.O_CREAT | os.O_RDWR, 0o600)


@contextmanager
def application_write(application_id: int):
    if models._session_bind.get() is not None:
        # An outer SQLite writer already serializes this service composition.
        # Never acquire a file guard in DB -> file order.
        yield
        return
    key = _key(application_id)
    if key in _active.get():
        yield
        return
    fd = _open(key)
    token = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        token = _active.set(_active.get() | {key})
        yield
    finally:
        if token is not None:
            _active.reset(token)
        os.close(fd)


@asynccontextmanager
async def async_application_write(application_id: int):
    if models._session_bind.get() is not None:
        # An outer SQLite writer already serializes this service composition.
        # Never acquire a file guard in DB -> file order.
        yield
        return
    key = _key(application_id)
    if key in _active.get():
        yield
        return
    fd = _open(key)
    token = None
    try:
        # Nonblocking retries keep the event loop responsive and make cancellation
        # close this descriptor immediately; no orphan worker can acquire later.
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                await asyncio.sleep(.01)
        token = _active.set(_active.get() | {key})
        yield
    finally:
        if token is not None:
            _active.reset(token)
        os.close(fd)


def guarded_write(function):
    """Also protect internal calls which do not pass through ASGI middleware."""
    from functools import wraps
    from inspect import iscoroutinefunction, signature
    parameters = signature(function)
    def identifier(args, kwargs):
        values = parameters.bind(*args, **kwargs).arguments
        if 'application_id' in values:
            return values['application_id']
        return values['app'].id or 0
    if iscoroutinefunction(function):
        @wraps(function)
        async def asynchronous(*args, **kwargs):
            async with async_application_write(identifier(args, kwargs)):
                return await function(*args, **kwargs)
        return asynchronous
    @wraps(function)
    def synchronous(*args, **kwargs):
        with application_write(identifier(args, kwargs)):
            return function(*args, **kwargs)
    return synchronous
