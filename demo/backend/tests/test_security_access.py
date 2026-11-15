"""Synthetic ownership/authentication boundary checks, without runtime settings."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

from demo.backend import models, officer_auth
from demo.backend.api import applications, common, documents, files, forms, postings
from demo.backend.main import app


@pytest.fixture
def security(tmp_path, monkeypatch):
    isolated = create_engine(f'sqlite:///{tmp_path / "synthetic-security.db"}', connect_args={'check_same_thread': False})
    monkeypatch.setattr(models, 'engine', isolated)
    storage = tmp_path / 'storage'
    for module in (applications, common, documents, files, forms, postings):
        monkeypatch.setattr(module, 'STORAGE', storage)
    monkeypatch.setattr(applications, 'SIGNATURES', storage / 'signatures')
    monkeypatch.setattr(documents, 'DOCUMENTS', storage / 'documents')
    monkeypatch.setenv('OFFICER_PASSWORD', 'synthetic-officer-password')
    monkeypatch.setenv('OFFICER_SESSION_SECRET', 'synthetic-session-key-for-security-tests')
    monkeypatch.setenv('ENGINE_V2_OCR', 'off')
    officer_auth._failures.clear()
    officer_auth._revoked.clear()
    with TestClient(app) as client:
        yield client
    isolated.dispose()


def new_application(client, version=0):
    response = client.post('/api/applications', json={'program_code': 'job_package', 'applicant_flow_version': version})
    assert response.status_code == 200, response.text
    return response


def login(client):
    return client.post('/api/officer/login', json={'password': 'synthetic-officer-password'})


PRIVATE_ROUTES = [
    ('GET', ''), ('PATCH', ''), ('GET', '/documents'), ('GET', '/required-documents'),
    ('GET', '/final-check'), ('GET', '/status'), ('GET', '/consents'), ('POST', '/consents'),
    ('GET', '/subsidy-items'), ('POST', '/subsidy-items'), ('GET', '/forms'),
    ('GET', '/forms/job_application.pdf'), ('GET', '/forms/files/written.pdf'),
    ('GET', '/forms/files/job_application/filled.pdf'),
    ('GET', '/forms/job_application/pages/1.png?preview=true'),
    ('GET', '/forms/interview-confirmation/filled.pdf'), ('GET', '/forms/signature-scan.png'),
    ('GET', '/identity-pledge.png'), ('POST', '/identity'), ('POST', '/self-check'), ('PUT', '/doc-context'), ('POST', '/submit'),
]


@pytest.mark.parametrize('version', [0, 1])
@pytest.mark.parametrize('method,tail', PRIVATE_ROUTES)
def test_every_builtin_private_route_rejects_missing_and_other_owner(security, version, method, tail):
    created = new_application(security, version).json()
    path = f'/api/applications/{created["id"]}{tail}'
    outsider = TestClient(app)
    other = new_application(outsider, version).json()
    assert other['id'] != created['id']
    for cookies in ({}, dict(outsider.cookies)):
        stranger = TestClient(app)
        stranger.cookies.update(cookies)
        result = stranger.request(method, path, json={})
        assert result.status_code == 403, (method, tail, result.text)
        assert result.json() == {'detail': '신청자 본인만 접근할 수 있습니다.'}
        assert result.headers['cache-control'] == 'private, no-store'
    assert security.get(f'/api/applications/{created["id"]}').status_code == 200


@pytest.mark.parametrize('version', [0, 1])
def test_owner_cookie_scopes_originals_and_patch_has_no_private_columns(security, version):
    created = new_application(security, version)
    assert 'Path=/api;' in created.headers['set-cookie']
    assert 'HttpOnly' in created.headers['set-cookie'] and 'SameSite=lax' in created.headers['set-cookie']
    identifier = created.json()['id']
    response = security.patch(f'/api/applications/{identifier}', json={'form1': {'name': '합성신청'}})
    assert response.status_code == 200
    assert not {'applicant_access_hash', 'written_forms_archive_path', 'written_forms_archive_count'} & response.json().keys()
    payload = b'%PDF-1.4\n% synthetic original\n'
    root = common.STORAGE
    root.mkdir(parents=True)
    target = root / 'synthetic.pdf'
    target.write_bytes(payload)
    with models.get_session() as session:
        document = models.Document(application_id=identifier, slot_key='synthetic', file_path=str(target.relative_to(root.parent)), file_format='pdf')
        session.add(document)
        session.commit()
        session.refresh(document)
        document_id = document.id
    original = security.get(f'/api/files/{document_id}')
    assert original.status_code == 200 and original.content == payload
    assert original.headers['content-disposition'].startswith('inline')
    outsider = TestClient(app)
    assert outsider.get(f'/api/files/{document_id}').status_code == 403
    assert outsider.get('/api/files/9999999').status_code == 403
    assert outsider.get('/api/applications/9999999').status_code == 403
    assert login(outsider).status_code == 200
    assert outsider.get(f'/api/files/{document_id}').status_code == 200
    assert outsider.patch(f'/api/applications/{identifier}', json={'form1': {}}).status_code == 403


@pytest.mark.parametrize('tail', [
    '/forms/layouts/job_application', '/forms/templates/job_application.pdf',
    '/forms/job_application/pages/1.png?preview=false', '/forms/job_application/pages/1.png',
    '/forms/files/job_application/blank.pdf', '/forms/files/job_application/source.hwp',
    '/forms/files/original-hwp/options', '/forms/files/original-hwp',
])
def test_builtin_public_assets_do_not_require_owner(security, tail):
    created = new_application(security).json()
    outsider = TestClient(app)
    result = outsider.get(f'/api/applications/{created["id"]}{tail}')
    assert result.status_code == 200, (tail, result.text[:200])
    assert created['application_no'] not in result.headers.get('content-disposition', '')


def test_old_tokenless_application_and_integer_aliases_stay_closed(security):
    with models.get_session() as session:
        row = models.Application(application_no='SYNTHETIC-LEGACY', program_code='job_package')
        session.add(row)
        session.commit()
        session.refresh(row)
        identifier = row.id
    for alias in (str(identifier), f'+{identifier}', f'0{identifier}', f'{identifier}.0'):
        assert security.get(f'/api/applications/{alias}').status_code == 403
    # A cookie selected by the client cannot mint a credential for historical data.
    security.cookies.set(f'applicant_access_{identifier}', 'synthetic-forged', path='/api')
    assert security.get(f'/api/applications/{identifier}').status_code == 403


@pytest.mark.parametrize('path', ['/api/officer/applications', '/api/officer/roles', '/api/officer/postings', '/api/officer/criteria/job_package', '/api/officer/unknown'])
def test_every_officer_namespace_requires_session(security, path):
    assert security.get(path).status_code == 401
    assert security.get(path + '?role=province', headers={'Authorization': 'Bearer province'}).status_code == 401


def test_login_expiry_forgery_logout_and_replay(security, monkeypatch):
    result = login(security)
    assert result.status_code == 200
    header = result.headers['set-cookie']
    assert 'HttpOnly' in header and 'SameSite=lax' in header and 'Path=/api' in header and 'Max-Age=28800' in header
    assert security.get('/api/officer/session').status_code == 200
    assert security.get('/api/officer/applications').status_code == 200
    token = security.cookies.get('officer_session')
    stranger = TestClient(app)
    stranger.cookies.set('officer_session', token[:-1] + ('a' if token[-1] != 'a' else 'b'), path='/api')
    assert stranger.get('/api/officer/session').status_code == 401
    real_time = officer_auth.time.time
    monkeypatch.setattr(officer_auth.time, 'time', lambda: real_time() + 28801)
    assert security.get('/api/officer/session').status_code == 401
    monkeypatch.setattr(officer_auth.time, 'time', real_time)
    assert security.post('/api/officer/logout').status_code == 200
    assert security.get('/api/officer/session').status_code == 401
    stranger.cookies.set('officer_session', token, path='/api')
    assert stranger.get('/api/officer/session').status_code == 401


def test_five_login_failures_enforce_cooldown_and_success_resets_count(security, monkeypatch):
    for _ in range(4):
        assert security.post('/api/officer/login', json={'password': 'wrong'}).status_code == 401
    assert login(security).status_code == 200
    security.cookies.clear()
    for _ in range(5):
        assert security.post('/api/officer/login', json={'password': 'wrong'}).status_code == 401
    blocked = login(security)
    assert blocked.status_code == 429 and 1 <= int(blocked.headers['retry-after']) <= 60
    real_time = officer_auth.time.time
    monkeypatch.setattr(officer_auth.time, 'time', lambda: real_time() + 61)
    assert login(security).status_code == 200


@pytest.mark.parametrize('path,method', [('/api/officer/login', 'POST'), ('/api/officer/applications', 'GET'), ('/api/officer/postings', 'GET'), ('/api/officer/logout', 'POST')])
def test_unset_password_disables_whole_officer_namespace(security, monkeypatch, path, method):
    assert login(security).status_code == 200
    monkeypatch.setenv('OFFICER_PASSWORD', '')
    response = security.request(method, path, json={'password': 'anything'})
    assert response.status_code == 503
    assert response.json()['detail'] == officer_auth.UNCONFIGURED


def test_secret_unset_and_https_cookie(security, monkeypatch):
    secure = TestClient(app, base_url='https://testserver')
    assert 'Secure' in login(secure).headers['set-cookie']
    monkeypatch.setenv('OFFICER_SESSION_SECRET', '')
    assert login(security).status_code == 503


def test_public_program_guidance_does_not_require_session(security):
    stranger = TestClient(app)
    assert stranger.get('/api/programs').status_code == 200
    assert stranger.get('/api/programs/job_package').status_code == 200
    assert stranger.get('/api/postings').status_code == 200


def test_pledge_signature_projection_and_inline_owner_officer_access(security, tmp_path):
    identifier = new_application(security).json()['id']
    root = common.STORAGE
    root.mkdir(parents=True)
    target = root / 'synthetic-pledge.pdf'
    target.write_bytes(b'%PDF-1.4 synthetic pledge')
    with models.get_session() as session:
        row = session.get(models.Application, identifier)
        row.identity_json = {'name': '합성신청', 'pledge_signature_path': str(target.relative_to(root.parent))}
        session.add(row)
        session.commit()
    response = security.get(f'/api/applications/{identifier}')
    url = response.json()['identity_json']['pledge_signature_path']
    assert url == f'/api/applications/{identifier}/identity-pledge.pdf'
    assert 'synthetic-pledge' not in response.text
    assert security.patch(f'/api/applications/{identifier}', json={}).json()['identity_json']['pledge_signature_path'] == url
    owner = security.get(url)
    assert owner.status_code == 200 and owner.content == target.read_bytes()
    assert owner.headers['content-disposition'] == 'inline'
    stranger = TestClient(app)
    assert stranger.get(url).status_code == 403
    assert login(stranger).status_code == 200
    assert stranger.get(url).status_code == 200
    outside = root.parent / 'synthetic-outside.pdf'
    outside.write_bytes(b'%PDF synthetic outside')
    with models.get_session() as session:
        row = session.get(models.Application, identifier)
        row.identity_json = {'pledge_signature_path': outside.name}
        session.add(row)
        session.commit()
    assert security.get(url).status_code == 404


@pytest.mark.parametrize('version', [0, 1])
def test_builtin_free_text_is_masked_before_database_persistence(security, version):
    from demo.backend.tests.test_generic_programs import signature
    identifier = new_application(security, version).json()['id']
    base = f'/api/applications/{identifier}'
    number = '900101-1654321'
    suffix = '654321'
    image = signature()
    result = security.patch(base, json={
        'form1': {'name': '합성신청', 'address': number, 'nested': {number: [number]}, 'job.signature': image},
        'form5': {'name': number, 'signature': image}, 'self_check': {'1': number},
    })
    assert result.status_code == 200, result.text
    assert suffix not in result.text
    assert result.json()['form1_json']['job.signature'] == image
    assert result.json()['form5_json']['signature'] == image
    response = security.post(base + '/identity', json={'name': number, 'birth': '1990-01-01',
        'phone': '01012345678', 'pledge': True, 'signature_data_url': image})
    assert response.status_code == 200, response.text
    assert suffix not in response.text
    response = security.post(base + '/self-check', json={'answers': {'1': number, '2': '예'}})
    assert response.status_code == 200, response.text
    with models.get_session() as session:
        row = session.get(models.Application, identifier)
        snapshot = repr([row.form1_json, row.form5_json, row.self_check_json, row.identity_json, row.doc_context_json])
        assert suffix not in snapshot
        assert row.form1_json['job.signature'] == image
        assert row.form5_json['signature'] == image
    assert suffix not in security.get(base).text


def test_consent_text_and_request_metadata_are_masked_before_storage(security):
    from demo.backend.tests.test_generic_programs import signature
    from sqlmodel import select
    identifier = new_application(security).json()['id']
    number = '900101-1654321'
    response = security.post(f'/api/applications/{identifier}/consents', headers={'user-agent': number},
        json={'consents': [{'consent_type': number, 'agreed': True, 'signature_kind': number,
                            'signature_data_url': signature()}]})
    assert response.status_code == 200, response.text
    assert '654321' not in response.text
    with models.get_session() as session:
        row = session.exec(select(models.Consent).where(models.Consent.application_id == identifier)).one()
        assert '654321' not in repr(row.model_dump())
    assert '654321' not in security.get(f'/api/applications/{identifier}/consents').text
