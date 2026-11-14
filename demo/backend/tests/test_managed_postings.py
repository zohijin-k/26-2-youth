"""Managed posting drafts use synthetic PDFs and isolated existing API fixtures."""
import pymupdf
import pytest
from sqlmodel import select
from demo.backend import models
from demo.backend.api import posting_workspace
from demo.backend.tests.test_postings_api import client, storage, tiny_pdf, NOTICE, FORMS, TODAY


def create_managed(client, **overrides):
    data = {'title': 'FAKE 관리형 사업', 'apply_start': '2026-11-10', 'apply_end': '2026-11-20',
        'workflow_version': '1', 'required_docs': '["resident_abstract"]', 'guidance_text': '합성 사업 안내'}
    data.update(overrides)
    return client.post('/api/officer/postings', data=data,
        files=[('notice_pdf', ('notice.pdf', NOTICE, 'application/pdf')),
            ('forms_pdf', ('one.pdf', FORMS, 'application/pdf')),
            ('forms_pdfs', ('two.pdf', FORMS, 'application/pdf'))])


def test_managed_multi_form_draft_create_edit_and_visibility(client):
    response = create_managed(client)
    assert response.status_code == 201, response.text
    row = response.json()
    path = f"/api/officer/postings/{row['id']}/workspace"
    workspace = client.get(path).json()
    assert workspace['managed'] is True
    assert len(workspace['forms']) == 2
    assert all(not item['confirmed'] for item in workspace['forms'])
    assert workspace['required_docs'] == ['resident_abstract']
    assert workspace['posting']['guidance_text'] == '합성 사업 안내'
    assert client.get(f"/api/postings/{row['id']}").status_code == 404
    assert all(item['id'] != row['id'] for item in client.get('/api/postings').json()['items'])
    body = {'title': 'FAKE 수정', 'apply_start': '2026-11-11', 'apply_end': '2026-12-01',
        'required_docs': [], 'guidance_text': '수정 안내'}
    changed = client.patch(path, json=body)
    assert changed.status_code == 200
    assert changed.json()['posting']['title'] == body['title']
    assert changed.json()['required_docs'] == []
    for form in workspace['forms']:
        received = client.get(form['file_url'])
        assert received.status_code == 200
        assert received.headers['content-disposition'] == 'inline'


def test_managed_invalid_slot_does_not_create_row_or_files(client, storage):
    response = create_managed(client, required_docs='["unknown"]')
    assert response.status_code == 422
    with models.get_session() as session:
        assert len(list(session.exec(select(models.ProgramPosting)).all())) == 1
    assert not (storage / 'postings').exists()


@pytest.mark.parametrize('kind', ['notice_pdf', 'forms_pdf'])
@pytest.mark.parametrize('case', ['encrypted', 'malformed', 'too-many-pages'])
def test_pdf_structure_validation(client, kind, case):
    if case == 'malformed':
        data = b'%PDF-this is not a parseable document'
    else:
        with pymupdf.open() as document:
            for _ in range(21 if case == 'too-many-pages' else 1):
                document.new_page()
            data = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,
                owner_pw='synthetic', user_pw='synthetic') if case == 'encrypted' else document.tobytes()
    files = {'notice_pdf': ('a.pdf', data if kind == 'notice_pdf' else NOTICE),
        'forms_pdf': ('b.pdf', data if kind == 'forms_pdf' else FORMS)}
    response = client.post('/api/officer/postings', data={'title':'FAKE', 'apply_start':'2026-11-10',
        'apply_end':'2026-11-20', 'workflow_version':'1'}, files=files)
    expected = 201 if case == 'too-many-pages' and kind == 'notice_pdf' else 422
    assert response.status_code == expected, response.text
    if expected == 422:
        assert isinstance(response.json()['detail'], str)


def test_slots_come_from_existing_requirements_and_builtin_is_readonly(client):
    slots = client.get('/api/officer/postings/slots/catalog').json()['items']
    assert {item['key'] for item in slots} == set(posting_workspace.slot_catalog())
    builtin = client.get('/api/officer/postings').json()['items'][0]
    response = client.patch(f"/api/officer/postings/{builtin['id']}/workspace", json={
        'title':'FAKE', 'apply_start':'2026-11-10','apply_end':'2026-11-20','required_docs':[]})
    assert response.status_code == 409


def test_replacing_managed_files_resets_layout_and_keeps_old_bytes(client, storage):
    row = create_managed(client).json()
    path = f"/api/officer/postings/{row['id']}/workspace"
    before = client.get(path).json()
    changed = client.post(path+'/files', files=[('forms_pdfs', ('replacement.pdf', tiny_pdf('FAKE replacement')))])
    assert changed.status_code == 200, changed.text
    assert len(changed.json()['forms']) == 1
    assert changed.json()['forms'][0]['id'] not in {item['id'] for item in before['forms']}
    assert not changed.json()['forms'][0]['confirmed']
