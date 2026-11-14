"""Cookie ownership guard for the newly added generic application surface."""
from __future__ import annotations

from hashlib import sha256
import hmac
from typing import Any

from pydantic import TypeAdapter, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .models import Application, Document, get_session
from .generic_programs import is_generic

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
        return application if application and is_generic(application.program_code) else None


class GenericApplicantAccess:
    """Protect generic data/files while preserving legacy and officer APIs."""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope['type'] != 'http' or scope.get('method') == 'OPTIONS':
            await self.app(scope, receive, send)
            return
        application = _application_for_path(scope.get('path', ''))
        if application is not None:
            request = Request(scope)
            token = request.cookies.get(f'applicant_access_{application.id}', '')
            expected = application.applicant_access_hash or ''
            actual = sha256(token.encode('utf-8')).hexdigest() if token else ''
            if not token or not expected or not hmac.compare_digest(actual, expected):
                response = JSONResponse({'detail': '신청자 본인만 접근할 수 있습니다.'}, status_code=403,
                                        headers={'Cache-Control': 'private, no-store'})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
