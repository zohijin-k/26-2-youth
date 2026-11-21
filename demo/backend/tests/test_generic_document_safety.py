"""Generic evidence paths, partial failures and serialized owner writes."""
import asyncio
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import select

from demo.backend import generic_access, models
from demo.backend.api import documents
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_generic_programs import client, fill, pdf, publish, start, TODAY


def photo_result():
    return OcrResult(detected_doc_type=DocType.ID_PHOTO_COPY, confidence=.99,
                     image_quality=1, issue_date=TODAY, tier='synthetic', engine='synthetic')


def upload(client, aid, source, slot='photo_1_photo'):
    response = client.post(f'/api/applications/{aid}/documents', data={'slot_key': slot},
                           files={'file': ('FAKE-same.pdf', source, 'application/pdf')})
    assert response.status_code == 200, response.text
    return response.json()


def stored(document_id):
    with models.get_session() as session:
        row = session.get(models.Document, document_id)
        return row.file_path, row.source_file_path


def test_generic_same_name_explicit_uploads_preserve_earlier_bytes(client, monkeypatch):
    posting = publish(client, ['photo_1_photo'])
    row, _form, layout = start(client, posting)
    fill(client, row, layout)
    monkeypatch.setattr(documents, 'read_document', lambda path, expected: photo_result())
    first_source, second_source = pdf(), pdf(True)
    first = upload(client, row['id'], first_source)
    first_path, _ = stored(first['document_id'])
    second = upload(client, row['id'], second_source)
    second_path, _ = stored(second['document_id'])
    assert first_path != second_path
    assert Path(first_path).name == Path(second_path).name == 'FAKE-same.pdf'
    assert (documents.STORAGE.parent / first_path).read_bytes() == first_source
    assert (documents.STORAGE.parent / second_path).read_bytes() == second_source


@pytest.mark.parametrize('save_failure_at', [1, 2])
def test_generic_auto_is_rejected_before_any_partial_save(client, monkeypatch, save_failure_at):
    posting = publish(client, ['photo_1_photo'])
    row, _form, layout = start(client, posting)
    fill(client, row, layout)
    monkeypatch.setattr(documents, 'read_document', lambda path, expected: photo_result())
    prior = upload(client, row['id'], pdf())
    prior_path, _ = stored(prior['document_id'])
    prior_bytes = (documents.STORAGE.parent / prior_path).read_bytes()
    before_files = {str(path): path.read_bytes() for path in documents.STORAGE.rglob('*') if path.is_file()}
    calls = 0
    original_save = documents._save_row
    def fail_save(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == save_failure_at:
            raise RuntimeError('synthetic interrupted merge')
        return original_save(*args, **kwargs)
    monkeypatch.setattr(documents, '_save_row', fail_save)
    def fail_split(*args, **kwargs):
        raise AssertionError('rejected auto must never split')
    monkeypatch.setattr(documents, 'split_pdf_pages', fail_split)
    response = client.post(f'/api/applications/{row["id"]}/documents', data={'slot_key': 'auto'},
                           files={'file': ('FAKE-interrupted.pdf', pdf(True), 'application/pdf')})
    assert response.status_code == 400, response.text
    assert calls == 0
    with models.get_session() as session:
        kept = session.exec(select(models.Document).where(models.Document.application_id == row['id'])).one()
        assert kept.id == prior['document_id'] and kept.file_path == prior_path and kept.stage1_status == 'PASS'
    assert (documents.STORAGE.parent / prior_path).read_bytes() == prior_bytes
    assert {str(path): path.read_bytes() for path in documents.STORAGE.rglob('*') if path.is_file()} == before_files


def test_generic_http_writes_serialize_per_application_after_ownership_check(monkeypatch):
    token = 'synthetic-owner-token'
    digest = sha256(token.encode()).hexdigest()
    monkeypatch.setattr(generic_access, '_application_for_path', lambda path: SimpleNamespace(
        id=int(path.split('/')[3]), applicant_access_hash=digest))
    async def scenario():
        first_entered, release, different_entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
        entered = []
        async def downstream(scope, receive, send):
            path = scope['path']
            entered.append(path)
            if path.endswith('/slow-upload'):
                first_entered.set()
                await release.wait()
            if '/8/' in path:
                different_entered.set()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'{}'})
        middleware = generic_access.GenericApplicantAccess(downstream)
        async def invoke(path, method='POST', valid=True):
            identifier = int(path.split('/')[3])
            scope = {'type': 'http', 'method': method, 'path': path, 'query_string': b'',
                     'headers': [(b'cookie', f'applicant_access_{identifier}={token if valid else "wrong"}'.encode())]}
            messages = []
            async def receive(): return {'type': 'http.request', 'body': b''}
            async def send(message): messages.append(message)
            await middleware(scope, receive, send)
            return messages[0]['status']
        first = asyncio.create_task(invoke('/api/applications/7/slow-upload'))
        await first_entered.wait()
        second = asyncio.create_task(invoke('/api/applications/07/submit'))
        different = asyncio.create_task(invoke('/api/applications/8/change'))
        await different_entered.wait()
        assert '/api/applications/07/submit' not in entered
        assert await asyncio.wait_for(invoke('/api/applications/7/delete', valid=False), 1) == 403
        assert await invoke('/api/applications/7/status', method='GET') == 200
        release.set()
        assert await asyncio.gather(first, second, different) == [200, 200, 200]
        assert entered.index('/api/applications/7/slow-upload') < entered.index('/api/applications/07/submit')
        assert sum(len(locks) for locks in middleware._write_locks.values()) == 0
    asyncio.run(scenario())
