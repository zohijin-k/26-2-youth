"""Submitted generic evidence must remain present after a passing review."""
from sqlmodel import select

from demo.backend import models
from demo.backend.api import documents
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_generic_programs import client, fill, pdf, publish, start, TODAY


def test_owner_cannot_remove_or_replace_submitted_passing_evidence(client, monkeypatch):
    posting = publish(client, ['photo_1_photo'])
    row, _form, layout = start(client, posting)
    fill(client, row, layout)
    monkeypatch.setattr(documents, 'read_document', lambda path, expected: OcrResult(
        detected_doc_type=DocType.ID_PHOTO_COPY, confidence=.99, image_quality=1,
        issue_date=TODAY, fields={'발급일': TODAY.isoformat()}, tier='synthetic', engine='synthetic'))
    base = f'/api/applications/{row["id"]}'
    source = pdf()
    response = client.post(base + '/documents', data={'slot_key': 'photo_1_photo'},
                           files={'file': ('FAKE-photo.pdf', source, 'application/pdf')})
    assert response.status_code == 200, response.text
    uploaded = response.json()
    assert uploaded['status'] == 'PASS'
    assert client.post(base + '/submit').status_code == 200
    with models.get_session() as session:
        review = session.exec(select(models.Review).where(models.Review.application_id == row['id'])).one()
        assert review.final_status == 'PASS'
    assert client.delete(base + f'/documents/{uploaded["document_id"]}').status_code == 409
    assert client.post(base + '/documents', data={'slot_key': 'photo_1_photo'},
                       files={'file': ('FAKE-photo.pdf', pdf(True), 'application/pdf')}).status_code == 409
    assert client.get(uploaded['file_url']).content == source
    listed = client.get('/api/officer/applications', params={'role': 'province',
                        'program': f'posting_{posting["id"]}', 'queue': 'pass'}).json()
    assert listed['total'] == 1
    assert listed['rows'][0]['application_id'] == row['id']
    assert listed['rows'][0]['missing_count'] == 0
