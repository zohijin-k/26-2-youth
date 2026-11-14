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


def fake_split(path, folder, stem):
    target = Path(folder) / f'{stem}_p1.pdf'
    target.write_bytes(Path(path).read_bytes())
    return [(0, target, photo_result())]


def upload(client, aid, source, slot='photo_1_photo'):
    response = client.post(f'/api/applications/{aid}/documents', data={'slot_key': slot},
                           files={'file': ('FAKE-same.pdf', source, 'application/pdf')})
    assert response.status_code == 200, response.text
    return response.json()


def stored(document_id):
    with models.get_session() as session:
        row = session.get(models.Document, document_id)
        return row.file_path, row.source_file_path


def test_generic_same_name_direct_and_merged_uploads_preserve_earlier_bytes(client, monkeypatch):
    posting = publish(client, ['photo_1_photo'])
    row, _form, layout = start(client, posting)
    fill(client, row, layout)
    monkeypatch.setattr(documents, 'read_document', lambda path, expected: photo_result())
    monkeypatch.setattr(documents, 'split_pdf_pages', fake_split)
    first_source, second_source = pdf(), pdf(True)
    first = upload(client, row['id'], first_source)
    first_path, _ = stored(first['document_id'])
    second = upload(client, row['id'], second_source)
    second_path, _ = stored(second['document_id'])
    assert first_path != second_path
    assert Path(first_path).name == Path(second_path).name == 'FAKE-same.pdf'
    assert (documents.STORAGE.parent / first_path).read_bytes() == first_source
    assert (documents.STORAGE.parent / second_path).read_bytes() == second_source
    first_merge = upload(client, row['id'], first_source, 'auto')
    first_page, first_original = stored(first_merge['unassigned'][0]['document_id'])
    second_merge = upload(client, row['id'], second_source, 'auto')
    second_page, second_original = stored(second_merge['unassigned'][0]['document_id'])
    assert first_page != second_page and first_original != second_original
    assert (documents.STORAGE.parent / first_page).read_bytes() == first_source
    assert (documents.STORAGE.parent / first_original).read_bytes() == first_source
    assert (documents.STORAGE.parent / second_page).read_bytes() == second_source


def test_interrupted_generic_merge_keeps_partial_pages_for_review_and_prior_valid_rows(client, monkeypatch):
    posting = publish(client, ['photo_1_photo'])
    row, _form, layout = start(client, posting)
    fill(client, row, layout)
    monkeypatch.setattr(documents, 'read_document', lambda path, expected: photo_result())
    def two_pages(path, folder, stem):
        result = []
        for index in range(2):
            page = Path(folder) / f'{stem}_p{index + 1}.pdf'
            page.write_bytes(Path(path).read_bytes())
            result.append((index, page, photo_result()))
        return result
    monkeypatch.setattr(documents, 'split_pdf_pages', two_pages)
    original_save = documents._save_row
    count = 0
    def fail_second(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('synthetic interrupted merge')
        return original_save(*args, **kwargs)
    monkeypatch.setattr(documents, '_save_row', fail_second)
    with pytest.raises(RuntimeError, match='synthetic interrupted merge'):
        client.post(f'/api/applications/{row["id"]}/documents', data={'slot_key': 'auto'},
                    files={'file': ('FAKE-interrupted.pdf', pdf(), 'application/pdf')})
    with models.get_session() as session:
        partial = session.exec(select(models.Document).where(models.Document.application_id == row['id'])).one()
        assert partial.stage1_status == 'NEEDS_REVIEW'
        assert partial.source_file_path and (documents.STORAGE.parent / partial.source_file_path).is_file()
        assert any(item['code'] == 'MERGED_PROCESSING_INTERRUPTED' for item in partial.findings_json)
    monkeypatch.setattr(documents, '_save_row', original_save)
    other, _form, other_layout = start(client, posting)
    fill(client, other, other_layout)
    prior = upload(client, other['id'], pdf())
    prior_path, _ = stored(prior['document_id'])
    def fail_first(*args, **kwargs):
        raise RuntimeError('synthetic before any save')
    monkeypatch.setattr(documents, '_save_row', fail_first)
    with pytest.raises(RuntimeError, match='synthetic before any save'):
        client.post(f'/api/applications/{other["id"]}/documents', data={'slot_key': 'auto'},
                    files={'file': ('FAKE-interrupted.pdf', pdf(True), 'application/pdf')})
    with models.get_session() as session:
        kept = session.exec(select(models.Document).where(models.Document.application_id == other['id'])).one()
        assert kept.file_path == prior_path and kept.stage1_status == 'PASS'


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
