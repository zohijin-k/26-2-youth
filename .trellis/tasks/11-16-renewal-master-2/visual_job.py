"""Synthetic job-package setup and real-HTTP security matrix for visual checks.

Mount seed_job only as a sync handler in the isolated visual wrapper. It stages
inputs through existing service functions and leaves submission to the browser.
No verdict, final status, access hash, or engine configuration is changed here.
"""
from __future__ import annotations

import asyncio
import base64
from io import BytesIO
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import urlsplit

import pymupdf
from fastapi import UploadFile
from starlette.datastructures import Headers
from starlette.requests import Request

SUITE = 'renewal-master-2'
MARKER = '.renewal-master2-synthetic'
NAME = '합성취업'
BIRTH = '1999-04-10'
FORM = {
    'name': NAME, 'birth': {'y': '1999', 'm': '4', 'd': '10'},
    'address': '전북특별자치도 전주시 완산구 합성동 0', 'gender': '여',
    'mobile': '010-0000-0000', 'email': 'synthetic-job@example.test',
    'bankName': '합성은행', 'accountNo': '000-SYNTHETIC-000', 'accountHolder': NAME,
}
SELF_CHECK = {'answers': {'1': '예', '2': '예'}}
CONSENTS = {'consents': [{'consent_type': key, 'agreed': True} for key in ('privacy', 'third_party')]}
ITEMS = {'items': [{'item_type': 'interview', 'count': 1, 'receipts': []}]}


def _isolated_root() -> Path:
    from demo.backend import models
    from demo.backend.api import common

    configured = os.environ.get('RENEWAL_VISUAL_ROOT')
    assert configured, 'An isolated visual root is required'
    root = Path(configured).resolve()
    allowed = (Path('/tmp').resolve(), Path(tempfile.gettempdir()).resolve())
    assert any(root.is_relative_to(parent) for parent in allowed), 'Visual root must be temporary'
    assert (root / MARKER).read_text().strip() == SUITE, 'Synthetic marker is required'
    assert Path(models.engine.url.database).resolve().is_relative_to(root), 'Unexpected visual database'
    assert common.STORAGE.resolve().is_relative_to(root), 'Unexpected visual storage'
    assert os.environ.get('ENGINE_V2_OCR') == 'off', 'Visual OCR must use the offline path'
    assert os.environ.get('JBAI_ALLOW_REAL_DOCS', 'false').lower() == 'false', 'Visual external OCR must be disabled'
    return root


def visual_identity() -> dict[str, Any]:
    _isolated_root()
    return {'suite': SUITE, 'synthetic_only': True}


def synthetic_pdf(label: str) -> bytes:
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        page.insert_text((40, 60), 'SYNTHETIC VISUAL FIXTURE - TEST ONLY', fontsize=17)
        page.insert_text((40, 105), label, fontsize=14)
        page.insert_text((40, 140), 'This artificial page intentionally contains no authoritative evidence.')
        page.insert_text((40, 165), 'Uncertain recognition must remain a human-review item.')
        return document.tobytes()


def synthetic_signature() -> bytes:
    with pymupdf.open() as document:
        page = document.new_page(width=360, height=140)
        for start, end in [((35, 95), (95, 35)), ((95, 35), (120, 105)), ((120, 105), (225, 45)),
                           ((225, 45), (240, 100)), ((240, 100), (325, 70))]:
            page.draw_line(start, end, color=(.05, .05, .05), width=5)
        return page.get_pixmap().tobytes('png')


def identity_payload() -> dict[str, Any]:
    return {'name': NAME, 'birth': BIRTH, 'phone': '01000000000', 'pledge': True,
            'signature_kind': 'electronic',
            'signature_data_url': 'data:image/png;base64,' + base64.b64encode(synthetic_signature()).decode('ascii')}


def _job_document_inputs():
    return [('bank_account', 'synthetic-bank.pdf', 'SYNTHETIC BANK COPY', None),
            ('resident_abstract', 'synthetic-resident.pdf', 'SYNTHETIC RESIDENCE INPUT', '2026-11-15'),
            ('interview_1_confirmation', 'synthetic-interview.pdf', 'SYNTHETIC INTERVIEW INPUT', None)]


def seed_job(application_id: int) -> dict[str, Any]:
    """Populate a clearly synthetic draft in the isolated visual-server database."""
    _isolated_root()
    from demo.backend import models
    from demo.backend.api import applications, documents, review, subsidy

    with models.get_session() as session:
        app = session.get(models.Application, application_id)
        assert app is not None and app.program_code == 'job_package' and app.status == 'draft', 'Synthetic job draft required'
        assert (app.identity_json or {}).get('name') == NAME, 'Synthetic identity marker required'
        assert app.identity_json.get('birth') == BIRTH, 'Synthetic birth marker required'
        assert app.identity_json.get('pledge_signature_path'), 'Complete the real identity API first'
    applications.patch(application_id, applications.PatchRequest(form1=dict(FORM)))
    checked = applications.self_check(application_id, applications.SelfCheckRequest(**SELF_CHECK))
    assert checked['eligible'], 'Synthetic self-check is incomplete'
    request = Request({'type': 'http', 'method': 'POST', 'path': '/__visual__/job/seed',
                       'headers': [], 'query_string': b'', 'scheme': 'http',
                       'server': ('127.0.0.1', 8010), 'client': ('127.0.0.1', 0)})
    applications.save_consents(application_id, applications.ConsentRequest(**CONSENTS), request)
    subsidy.save_subsidy_items(application_id, subsidy.SubsidyRequest(**ITEMS))

    async def upload_inputs():
        results = []
        for slot, filename, label, declared in _job_document_inputs():
            file = UploadFile(file=BytesIO(synthetic_pdf(label)), filename=filename,
                              headers=Headers({'content-type': 'application/pdf'}))
            result = await documents.upload_document(application_id, file, slot, declared)
            assert result['status'] == 'NEEDS_REVIEW', 'Synthetic uncertainty must remain reviewable'
            results.append({'slot_key': slot, 'document_id': result['document_id'], 'status': result['status']})
        return results

    uploaded = asyncio.run(upload_inputs())
    final = review.final_check(application_id)
    assert final['can_submit'], 'Current final-check rejected synthetic setup'
    with models.get_session() as session:
        assert session.get(models.Application, application_id).status == 'draft', 'Submission belongs to the browser'
    return {'application_id': application_id, 'can_submit': final['can_submit'], 'documents': uploaded,
            'source': 'synthetic inputs through existing validators'}


def _call(client: Any, base_url: str, method: str, path: str, **kwargs):
    return client.request(method, base_url.rstrip('/') + path, **kwargs)


def _ok(response: Any, expected: int = 200) -> Any:
    assert response.status_code == expected, f'Synthetic request failed with HTTP {response.status_code}'
    return response


def _check_visual_server(client: Any, base_url: str) -> None:
    location = urlsplit(base_url)
    assert location.scheme == 'http' and location.hostname in {'127.0.0.1', 'localhost'}, 'Loopback visual server required'
    assert location.port == 8010, 'Use the authorized backend port'
    response = _ok(_call(client, base_url, 'GET', '/__visual__/identity'))
    assert response.json() == {'suite': SUITE, 'synthetic_only': True}, 'Synthetic visual server identity required'


def prepare_job(client: Any, base_url: str, application_id: int | None = None) -> dict[str, Any]:
    """Stage all job-package inputs through real HTTP using an owner cookie jar."""
    _check_visual_server(client, base_url)
    if application_id is None:
        response = _ok(_call(client, base_url, 'POST', '/api/applications',
            json={'program_code': 'job_package', 'applicant_flow_version': 1}))
        application_id = response.json()['id']
        _ok(_call(client, base_url, 'POST', f'/api/applications/{application_id}/identity', json=identity_payload()))
    base = f'/api/applications/{application_id}'
    current = _ok(_call(client, base_url, 'GET', base)).json()
    assert current['program_code'] == 'job_package' and current['identity_json']['name'] == NAME, 'Synthetic owner required'
    _ok(_call(client, base_url, 'PATCH', base, json={'form1': dict(FORM)}))
    _ok(_call(client, base_url, 'POST', base + '/self-check', json=SELF_CHECK))
    _ok(_call(client, base_url, 'POST', base + '/consents', json=CONSENTS))
    _ok(_call(client, base_url, 'POST', base + '/subsidy-items', json=ITEMS))
    uploaded = []
    for slot, filename, label, declared in _job_document_inputs():
        data = {'slot_key': slot}
        if declared:
            data['declared_issue_date'] = declared
        response = _ok(_call(client, base_url, 'POST', base + '/documents', data=data,
            files={'file': (filename, synthetic_pdf(label), 'application/pdf')}))
        result = response.json()
        assert result['status'] == 'NEEDS_REVIEW', 'Synthetic uncertainty must remain reviewable'
        uploaded.append(result)
    final = _ok(_call(client, base_url, 'GET', base + '/final-check')).json()
    assert final['can_submit'], 'Current final-check rejected synthetic setup'
    return {'application_id': application_id, 'documents': uploaded, 'can_submit': True}


def route_requests(base_url: str, owner: Any, other: Any, officer: Any = None,
                   application_id: int | None = None,
                   rows_out: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Request sensitive read/write routes using isolated real cookie jars.

    Return only methods, paths, HTTP statuses and expected access classes.
    Credentials, cookies, bodies and personal input values are never retained.
    """
    import httpx

    prepared = prepare_job(owner, base_url, application_id)
    application_id = prepared['application_id']
    base = f'/api/applications/{application_id}'
    _ok(_call(other, base_url, 'POST', '/api/applications', json={'program_code': 'job_package'}))
    _ok(_call(owner, base_url, 'POST', base + '/forms/signature-scan',
        files={'file': ('synthetic-signature.png', synthetic_signature(), 'image/png')}))
    private = [('GET', base), ('PATCH', base), *[('GET', base + tail) for tail in [
        '/documents', '/required-documents', '/final-check', '/status', '/consents', '/subsidy-items', '/forms',
        '/forms/job_application.pdf', '/forms/job_consent.pdf', '/forms/files/written.pdf',
        '/forms/files/job_application/filled.pdf', '/forms/files/job_consent/filled.pdf',
        '/forms/job_application/pages/1.png?preview=true', '/forms/job_consent/pages/1.png?preview=true',
        '/forms/interview-confirmation/filled.pdf', '/forms/signature-scan.png', '/identity-pledge.png']]]
    private.extend(('GET', row['file_url']) for row in prepared['documents'])
    public = ['/api/programs', '/api/programs/job_package', '/api/programs/job_package/criteria', '/api/postings',
              base + '/forms/layouts/job_application', base + '/forms/templates/job_application.pdf',
              base + '/forms/job_application/pages/1.png?preview=false',
              base + '/forms/files/job_application/blank.pdf', base + '/forms/files/job_application/source.hwp',
              base + '/forms/files/original-hwp/options', base + '/forms/files/original-hwp']
    if officer is not None:
        private_officer = ['/api/officer/session', '/api/officer/roles', '/api/officer/applications', '/api/officer/postings']
        postings = _ok(_call(officer, base_url, 'GET', '/api/officer/postings')).json()['items']
        for posting in postings:
            if posting.get('notice_url') and posting.get('status') == 'published':
                public.append(f'/api/postings/{posting["id"]}/files/notice.pdf')
        for path in private_officer:
            private.append(('OFFICER', path))
    rows = rows_out if rows_out is not None else []
    with httpx.Client(timeout=30, trust_env=False) as anonymous:
        def owner_request(method: str, path: str, **kwargs):
            unauth = _call(anonymous, base_url, method, path, **kwargs).status_code
            wrong = _call(other, base_url, method, path, **kwargs).status_code
            allowed = _call(owner, base_url, method, path, **kwargs)
            rows.append({'method': method, 'path': path, 'anonymous': unauth, 'other': wrong,
                         'owner_or_officer': allowed.status_code, 'expected': 'owner'})
            return allowed

        for method, path in private:
            officer_route = method == 'OFFICER'
            request_method = 'GET' if officer_route else method
            kwargs = {'json': {}} if request_method == 'PATCH' else {}
            unauth = _call(anonymous, base_url, request_method, path, **kwargs).status_code
            wrong = _call(other, base_url, request_method, path, **kwargs).status_code
            allowed = _call(officer if officer_route else owner, base_url, request_method, path, **kwargs).status_code
            rows.append({'method': request_method, 'path': path, 'anonymous': unauth, 'other': wrong,
                         'owner_or_officer': allowed, 'expected': 'officer' if officer_route else 'owner'})
        for path in public:
            rows.append({'method': 'GET', 'path': path,
                         'anonymous': _call(anonymous, base_url, 'GET', path).status_code,
                         'other': _call(other, base_url, 'GET', path).status_code,
                         'owner_or_officer': _call(owner, base_url, 'GET', path).status_code,
                         'expected': 'public'})

        # Identity is intentionally immutable after the first successful call.
        # A separate owner-created synthetic draft exercises its successful
        # creation path without weakening that policy or altering the prepared
        # main application's identity before its final submission.
        fresh = _ok(_call(owner, base_url, 'POST', '/api/applications',
            json={'program_code': 'job_package', 'applicant_flow_version': 1})).json()['id']
        _ok(owner_request('POST', f'/api/applications/{fresh}/identity', json=identity_payload()))
        owner_request('POST', base + '/self-check', json=SELF_CHECK)
        owner_request('POST', base + '/consents', json=CONSENTS)
        owner_request('POST', base + '/subsidy-items', json=ITEMS)
        owner_request('PUT', base + '/doc-context', json={'workplace_count': 1})

        def interview_upload():
            return owner_request('POST', base + '/documents', data={'slot_key': 'interview_1_confirmation'},
                files={'file': ('synthetic-interview-matrix.pdf', synthetic_pdf('SYNTHETIC INTERVIEW MATRIX INPUT'),
                                'application/pdf')})

        uploaded = _ok(interview_upload()).json()
        # The POST replaced the old slot, so delete its current identifier.
        # Earlier GET-original records referred to identifiers valid at the
        # time those requests were sent, before this replacement.
        _ok(owner_request('DELETE', base + f'/documents/{uploaded["document_id"]}'))
        _ok(interview_upload())

        def signature_upload():
            return owner_request('POST', base + '/forms/signature-scan',
                files={'file': ('synthetic-signature.png', synthetic_signature(), 'image/png')})

        _ok(signature_upload())
        _ok(owner_request('DELETE', base + '/forms/signature-scan'))
        _ok(signature_upload())
        final = _ok(_call(owner, base_url, 'GET', base + '/final-check')).json()
        assert final['can_submit'], 'Synthetic mutations must preserve a submittable draft'
        if officer is not None:
            submit_path = base + '/submit'
            unauth = _call(anonymous, base_url, 'POST', submit_path).status_code
            wrong = _call(other, base_url, 'POST', submit_path).status_code
            submitted = _call(owner, base_url, 'POST', submit_path).status_code
            rows.append({'method': 'POST', 'path': submit_path, 'anonymous': unauth,
                         'other': wrong, 'owner_or_officer': submitted, 'expected': 'owner'})
            assert submitted == 200, 'Synthetic submission failed during security matrix'
            for suffix in ('', '/reasons', '/decision'):
                path = f'/api/officer/applications/{application_id}' + suffix
                method = 'POST' if suffix == '/decision' else 'GET'
                kwargs = {'json': {'role': 'province', 'decision': 'hold', 'memo': '합성 보안 경로 확인'}} if method == 'POST' else {}
                rows.append({'method': method, 'path': path,
                             'anonymous': _call(anonymous, base_url, method, path, **kwargs).status_code,
                             'other': _call(other, base_url, method, path, **kwargs).status_code,
                             'owner_or_officer': _call(officer, base_url, method, path, **kwargs).status_code,
                             'expected': 'officer'})
    return rows
