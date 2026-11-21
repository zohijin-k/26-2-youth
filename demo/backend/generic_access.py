"""Cookie ownership guard shared by every application version."""
from __future__ import annotations

from hashlib import sha256
import asyncio
import hmac
from typing import Any
from weakref import WeakKeyDictionary, WeakValueDictionary

from pydantic import TypeAdapter, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .models import Application, Document, get_session
from .application_writes import async_application_write
from .generic_programs import is_generic
from .officer_auth import is_officer

_INTEGER = TypeAdapter(int)


def _route_id(segment: str) -> int | None:
    # Match the same integer coercion as the endpoint, including +1 and 1.0.
    # Checking only a digit-shaped URL would leave alternate spellings unguarded.
    try:
        value = _INTEGER.validate_python(segment)
    except (ValidationError, ValueError, TypeError):
        return None
    return value if 0 < value < 2**63 else None


def _application_for_path(path: str) -> Application | None:
    parts = path.split('/')
    if len(parts) < 4 or parts[1] != 'api' or parts[2] not in {'applications', 'files'}:
        return None
    identifier = _route_id(parts[3])
    if identifier is None:
        return None
    with get_session() as session:
        if parts[2] == 'files':
            document = session.get(Document, identifier)
            if document is None:
                return None
            identifier = document.application_id
        application = session.get(Application, identifier)
        return application


def _public_asset(parts: list[str], request: Request) -> bool:
    if request.method != 'GET' or parts[2] != 'applications':
        return False
    tail = parts[4:]
    if tail == ['program']:
        return True
    if len(tail) == 3 and tail[:2] in (['forms', 'layouts'], ['forms', 'templates']):
        return True
    if len(tail) == 4 and tail[0] == 'forms' and tail[2] == 'pages':
        # Pydantic accepts several false spellings. Everything else stays guarded
        # (including malformed values); a handler's future default cannot expose data.
        return request.query_params.get('preview', 'false').lower() in {'false', '0', 'off', 'no'}
    if tail in (['forms', 'files', 'original-hwp'], ['forms', 'files', 'original-hwp', 'options']):
        return True
    return len(tail) == 4 and tail[:2] == ['forms', 'files'] and tail[3] in {'blank.pdf', 'source.hwp', 'options'}


class GenericApplicantAccess:
    """Protect application data and originals; public blank assets stay public."""

    def __init__(self, app: Any):
        self.app = app
        # Local demo: one uvicorn worker. Weak loop/lock references keep idle
        # application entries from accumulating after requests finish.
        self._write_locks: WeakKeyDictionary[Any, WeakValueDictionary[int, asyncio.Lock]] = WeakKeyDictionary()

    def _write_lock(self, application_id: int) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        locks = self._write_locks.get(loop)
        if locks is None:
            locks = WeakValueDictionary()
            self._write_locks[loop] = locks
        lock = locks.get(application_id)
        if lock is None:
            lock = asyncio.Lock()
            locks[application_id] = lock
        return lock

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope['type'] != 'http' or scope.get('method') == 'OPTIONS':
            await self.app(scope, receive, send)
            return
        path = scope.get('path', '')
        parts = path.split('/')
        # Creation has no application identifier. All routes beneath an identifier
        # are private unless explicitly classified as blank public assets below.
        protected = len(parts) >= 4 and parts[1] == 'api' and parts[2] in {'applications', 'files'}
        if not protected:
            await self.app(scope, receive, send)
            return
        application = _application_for_path(path)
        request = Request(scope)
        if application is not None and not is_generic(getattr(application, 'program_code', 'posting_unknown')) and _public_asset(parts, request):
            # Browsers from before the ownership rollout send the existing token
            # only beneath forms/files. A public blank-asset request can widen
            # that same credential's scope after proving it matches the stored
            # hash. No credential is created or recovered for a missing token.
            name = f'applicant_access_{application.id}'
            token = request.cookies.get(name, '')
            expected = application.applicant_access_hash or ''
            upgrade = (parts[4:6] == ['forms', 'files'] and token and expected
                       and hmac.compare_digest(sha256(token.encode('utf-8')).hexdigest(), expected))
            if upgrade:
                cookies = Response()
                attributes = {'httponly': True, 'secure': request.url.scheme == 'https', 'samesite': 'lax'}
                cookies.set_cookie(name, token, path='/api', max_age=5 * 365 * 24 * 60 * 60, **attributes)
                cookies.set_cookie(name, token, path=f'/api/applications/{application.id}/forms/files', max_age=0, **attributes)
                cookie_headers = [(key, value) for key, value in cookies.raw_headers if key == b'set-cookie']
                async def migration_send(message: dict[str, Any]) -> None:
                    if message['type'] == 'http.response.start' and 200 <= message['status'] < 300:
                        message = dict(message)
                        message['headers'] = [(key, value) for key, value in message.get('headers', [])
                                              if key.lower() != b'cache-control'] + cookie_headers + [
                                                  (b'cache-control', b'private, no-store')]
                    await send(message)
                await self.app(scope, receive, migration_send)
            else:
                await self.app(scope, receive, send)
            return
        # Officer sessions may view originals inline. They never authorize PATCH,
        # applicant state changes, or general applicant data endpoints.
        officer_view = scope.get('method') == 'GET' and (parts[2] == 'files' or (len(parts) >= 5 and (parts[4] == 'forms' or parts[4].startswith('identity-pledge.'))))
        if officer_view and is_officer(request):
            await self.app(scope, receive, send)
            return
        token = request.cookies.get(f'applicant_access_{application.id}', '') if application else ''
        expected = application.applicant_access_hash or '' if application else ''
        actual = sha256(token.encode('utf-8')).hexdigest() if token else ''
        if not application or not token or not expected or not hmac.compare_digest(actual, expected):
            response = JSONResponse({'detail': '신청자 본인만 접근할 수 있습니다.'}, status_code=403,
                                    headers={'Cache-Control': 'private, no-store'})
            await response(scope, receive, send)
            return
        if scope.get('method') in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            async with self._write_lock(application.id), async_application_write(application.id):
                await self.app(scope, receive, send)
            return
        await self.app(scope, receive, send)
