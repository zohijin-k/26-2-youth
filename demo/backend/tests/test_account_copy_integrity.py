"""Synthetic managed-account integrity and immutable stored originals."""
from pathlib import Path

from demo.backend import models
from demo.backend.api import documents
from demo.backend.tests.test_account_attachment import client, fake_pdf, upload_bankbook


def managed_application(client):
    response = client.post('/api/applications', json={'program_code': 'job_package', 'applicant_flow_version': 1})
    assert response.status_code == 200, response.text
    return response.json()['id']


def missing_copy(client, aid):
    response = client.get(f'/api/applications/{aid}/final-check')
    assert response.status_code == 200, response.text
    return any(item['target'] == 'bankbookFileName' for item in response.json()['blockers'])


def test_managed_filename_spoof_cannot_satisfy_account_copy(client):
    aid = managed_application(client)
    response = client.patch(f'/api/applications/{aid}', json={'form1': {'bankbookFileName': 'FAKE-spoof.pdf'}})
    assert response.status_code == 200
    assert not response.json()['form1_json'].get('bankbookFileName')
    assert missing_copy(client, aid)
    assert client.put(f'/api/applications/{aid}/doc-context', json={}).status_code == 200
    client.patch(f'/api/applications/{aid}', json={'form1': {'bankbookFileName': 'FAKE-spoof.pdf'}})
    assert missing_copy(client, aid)


def test_deleting_real_copy_restores_requirement_even_after_stale_autosave(client):
    aid = managed_application(client)
    uploaded = upload_bankbook(client, aid).json()
    assert not missing_copy(client, aid)
    assert client.delete(f'/api/applications/{aid}/documents/{uploaded["document_id"]}').status_code == 200
    response = client.patch(f'/api/applications/{aid}', json={'form1': {'bankbookFileName': uploaded['file_name']}})
    assert not response.json()['form1_json'].get('bankbookFileName')
    assert missing_copy(client, aid)


def test_missing_stored_bytes_cannot_satisfy_copy_requirement(client):
    aid = managed_application(client)
    uploaded = upload_bankbook(client, aid).json()
    with models.get_session() as session:
        row = session.get(models.Document, uploaded['document_id'])
        (documents.STORAGE.parent / row.file_path).unlink()
    assert missing_copy(client, aid)


def test_same_named_replacements_preserve_earlier_original_bytes(client):
    aid = managed_application(client)
    original = fake_pdf()
    first = upload_bankbook(client, aid, original, 'FAKE-same.pdf').json()
    with models.get_session() as session:
        first_path = Path(session.get(models.Document, first['document_id']).file_path)
    replacement = original + b'\n%FAKE replacement\n'
    second = upload_bankbook(client, aid, replacement, 'FAKE-same.pdf').json()
    with models.get_session() as session:
        second_path = Path(session.get(models.Document, second['document_id']).file_path)
    assert first_path != second_path
    assert first_path.name == second_path.name == 'FAKE-same.pdf'
    assert (documents.STORAGE.parent / first_path).read_bytes() == original
    assert (documents.STORAGE.parent / second_path).read_bytes() == replacement


def test_submitted_copy_cannot_be_replaced_or_deleted(client):
    aid = managed_application(client)
    uploaded = upload_bankbook(client, aid).json()
    with models.get_session() as session:
        saved = session.get(models.Application, aid)
        saved.status = models.STATUS_SUBMITTED
        session.add(saved)
        session.commit()
    assert upload_bankbook(client, aid).status_code == 409
    assert client.delete(f'/api/applications/{aid}/documents/{uploaded["document_id"]}').status_code == 409
    assert client.get(uploaded['file_url']).status_code == 200
