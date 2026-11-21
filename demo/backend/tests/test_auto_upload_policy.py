"""Synthetic Phase 2 counterexample and side-effect-free explicit-slot boundary."""
from copy import deepcopy
from hashlib import sha256
from unittest.mock import AsyncMock, Mock

import pymupdf
import pytest
from sqlmodel import select
from starlette.datastructures import UploadFile

from demo.backend import models
from demo.backend.api import documents, review
from demo.backend.ocr.file_evidence import objective_image_quality
from demo.backend.tests.test_generic_programs import client, fill, publish, start, pdf

AUTO_DETAIL = (
    '자동 서류 분류 업로드는 현재 지원하지 않습니다. '
    '서류 종류에 맞는 업로드 항목을 선택해 다시 제출해 주세요.'
)


def low_resolution_text_layer_pdf():
    """Exact Phase 2 geometry/content; no OCR or verdict mocks."""
    image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 283), False)
    image.clear_with(235)
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=image.tobytes('png'))
        page.insert_text((50, 85), '면접용사진사본', fontname='korea', fontsize=25)
        page.insert_text((50, 135), '발급일:2026-11-22', fontname='korea', fontsize=18)
        page.insert_text((50, 185), 'SYNTHETIC', fontsize=14)
        assert len(page.get_text().strip()) < 50
        return document.tobytes()


def database_snapshot():
    with models.engine.connect() as connection:
        return {table.name: deepcopy([dict(row) for row in connection.execute(
            table.select().order_by(*table.primary_key.columns)).mappings()])
            for table in models.SQLModel.metadata.sorted_tables}


def file_snapshot():
    return {str(path.relative_to(documents.STORAGE)): sha256(path.read_bytes()).hexdigest()
            for path in documents.STORAGE.rglob('*') if path.is_file()}


def test_phase2_low_resolution_auto_cannot_create_submittable_pass(client, monkeypatch, tmp_path):
    data = low_resolution_text_layer_pdf()
    source = tmp_path / 'FAKE-low-resolution.pdf'
    source.write_bytes(data)
    assert objective_image_quality(str(source)) == .5
    posting = publish(client, ['photo_1_photo'])
    row, _, layout = start(client, posting)
    fill(client, row, layout)
    monkeypatch.setenv('ENGINE_V2_OCR', 'own')
    base = f'/api/applications/{row["id"]}'
    before, originals = database_snapshot(), file_snapshot()
    response = client.post(base + '/documents', data={'slot_key': 'auto'},
                           files={'file': ('FAKE-low-resolution.pdf', data, 'application/pdf')})
    assert response.status_code == 400, response.json()
    assert response.json() == {'detail': AUTO_DETAIL}
    assert database_snapshot() == before and file_snapshot() == originals
    assert not client.get(base + '/final-check').json()['can_submit']
    assert client.post(base + '/submit').status_code == 400
    with models.get_session() as session:
        assert not session.exec(select(models.Document)).all()
        assert not session.exec(select(models.Review)).all()


def test_same_phase2_pdf_explicit_slot_keeps_real_quality_fail(client, monkeypatch):
    posting = publish(client, ['photo_1_photo'])
    row, _, layout = start(client, posting)
    fill(client, row, layout)
    monkeypatch.setenv('ENGINE_V2_OCR', 'own')
    base = f'/api/applications/{row["id"]}'
    response = client.post(base + '/documents', data={'slot_key': 'photo_1_photo'},
                           files={'file': ('FAKE-low-resolution.pdf', low_resolution_text_layer_pdf(), 'application/pdf')})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'FAIL'
    assert any(f['code'] == 'LOW_IMAGE_QUALITY' for f in response.json()['findings'])
    assert not client.get(base + '/final-check').json()['can_submit']
    assert client.post(base + '/submit').status_code == 400
    with models.get_session() as session:
        row = session.exec(select(models.Document)).one()
        assert row.ocr_json['image_quality'] == .5
        assert row.stage1_status == 'FAIL'
        assert not session.exec(select(models.Review)).all()


@pytest.fixture(params=['double_savings', 'job_package', 'generic'])
def prepared(client, request):
    if request.param == 'generic':
        posting = publish(client, ['photo_1_photo'])
        row, _, layout = start(client, posting)
        fill(client, row, layout)
    else:
        result = client.post('/api/applications', json={'program_code': request.param})
        assert result.status_code == 200, result.text
        row = result.json()
    aid = row['id']
    # Isolated historical seed: mixed verdicts, unassigned evidence and officer
    # memo make accidental replacement/review changes visible in full snapshots.
    with models.get_session() as session:
        for index, status in enumerate(['PASS', 'FAIL', 'NEEDS_REVIEW']):
            slot = ['resident_abstract', 'photo_1_photo', models.UNASSIGNED_SLOT][index]
            path = documents.DOCUMENTS / row['application_no'] / slot / 'FAKE-existing.pdf'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pdf())
            session.add(models.Document(application_id=aid, slot_key=slot,
                file_path=str(path.relative_to(documents.STORAGE.parent)), file_format='pdf',
                stage1_status=status, ocr_json={'confidence': .4, 'fields': {}},
                findings_json=[{'code': 'SYNTHETIC_EXISTING', 'severity': status, 'message': '합성 기존 판정'}]))
        session.add(models.Review(application_id=aid, final_status='NEEDS_REVIEW',
            stage1_status='FAIL', officer_memo='합성 기존 검토 메모', review_payload_json={'synthetic': True}))
        session.commit()
    return aid


@pytest.fixture
def no_processing(monkeypatch):
    spies = {}
    for name in ['read_document', 'assess_upload', 'check_document', 'split_pdf_pages',
                 '_save_row', '_replace_existing', '_refresh_nhis_identity']:
        spies[name] = Mock(side_effect=AssertionError(f'Rejected request called {name}'))
        monkeypatch.setattr(documents, name, spies[name])
    for name in ['_upload_merged', '_upload_bankbook']:
        spies[name] = AsyncMock(side_effect=AssertionError(f'Rejected request called {name}'))
        monkeypatch.setattr(documents, name, spies[name])
    spies['read'] = AsyncMock(side_effect=AssertionError('Rejected request read upload bytes'))
    monkeypatch.setattr(UploadFile, 'read', spies['read'])
    spies['review'] = Mock(side_effect=AssertionError('Rejected request ran review'))
    monkeypatch.setattr(review, '_run_review', spies['review'])
    return spies


def assert_rejected_unchanged(client, aid, spies, *, data=None, query='', payload=None, detail=None):
    queue = client.get('/api/officer/applications')
    assert queue.status_code == 200, queue.text
    before, originals = database_snapshot(), file_snapshot()
    response = client.post(f'/api/applications/{aid}/documents{query}', data=data,
        files={'file': ('FAKE-rejected.pdf', payload or low_resolution_text_layer_pdf(), 'application/pdf')})
    assert response.status_code == 400, response.text
    assert isinstance(response.json().get('detail'), str)
    if detail is not None:
        assert response.json() == {'detail': detail}
    assert database_snapshot() == before
    assert file_snapshot() == originals
    assert client.get('/api/officer/applications').json() == queue.json()
    assert database_snapshot() == before
    for spy in spies.values():
        spy.assert_not_called()


@pytest.mark.parametrize('data,query', [
    ({'slot_key': 'auto'}, ''), (None, ''), ({'slot_key': ''}, ''),
    ({'slot_key': None}, ''), (None, '?slot_key=resident_abstract'),
    ({'slot_key': ''}, '?slot_key=resident_abstract'),
    ({'slot_key': 'auto'}, '?slot_key=resident_abstract'),
], ids=['auto', 'omitted', 'empty', 'multipart-null', 'query-only', 'empty-query', 'auto-query'])
def test_unsafe_form_rejected_without_processing_or_persistent_side_effects(
    client, prepared, no_processing, data, query,
):
    assert_rejected_unchanged(client, prepared, no_processing, data=data, query=query, detail=AUTO_DETAIL)


@pytest.mark.parametrize('slot', [' ', '\t', '\n', ' auto ', 'AUTO', 'unassigned',
                                  'FAKE-unknown', '../resident_abstract', 'application_form'])
def test_invalid_or_non_upload_slot_rejected_before_read(client, prepared, no_processing, slot):
    assert_rejected_unchanged(client, prepared, no_processing, data={'slot_key': slot})


@pytest.mark.parametrize('kind', ['multipage', 'image', 'unclassified'])
def test_auto_content_cannot_reach_split_or_ocr(client, prepared, no_processing, kind):
    with pymupdf.open() as document:
        if kind == 'image':
            image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 283), False)
            image.clear_with(235)
            page = document.new_page()
            page.insert_image(page.rect, stream=image.tobytes('png'))
        else:
            for _ in range(3 if kind == 'multipage' else 1):
                document.new_page().insert_text((30, 30), 'SYNTHETIC UNKNOWN DOCUMENT')
        payload = document.tobytes()
    assert_rejected_unchanged(client, prepared, no_processing,
                              data={'slot_key': 'auto'}, payload=payload, detail=AUTO_DETAIL)


def test_auto_rejected_even_before_application_load(monkeypatch):
    import asyncio
    from io import BytesIO
    from fastapi import HTTPException
    load = Mock(side_effect=AssertionError('auto must be rejected before application load'))
    monkeypatch.setattr(documents, '_load', load)
    upload = UploadFile(filename='FAKE.pdf', file=BytesIO(pdf()))
    for slot in ['', 'auto']:
        with pytest.raises(HTTPException) as caught:
            asyncio.run(documents.upload_document(1, upload, slot, None))
        assert caught.value.status_code == 400 and caught.value.detail == AUTO_DETAIL
    load.assert_not_called()


@pytest.mark.parametrize('aggregate_status', ['PASS', 'FAIL', 'NEEDS_REVIEW'])
def test_rejected_auto_preserves_submitted_queue_aggregate_and_human_checks(
    client, prepared, no_processing, aggregate_status,
):
    from datetime import datetime
    from demo.backend import generic_programs
    from demo.backend.generic_review import GenericReviewChecks
    with models.get_session() as session:
        app = session.get(models.Application, prepared)
        app.status = 'submitted'
        app.submitted_at = datetime(2026, 11, 22, 12)
        session.add(app)
        saved = session.exec(select(models.Review).where(models.Review.application_id == prepared)).one()
        saved.final_status = aggregate_status
        session.add(saved)
        if generic_programs.is_generic(app.program_code):
            session.add(GenericReviewChecks(application_id=prepared, checks_json={
                'fingerprint': 'SYNTHETIC-HISTORICAL', 'document_ids': ['1', 'written'],
                'checklist_ids': ['program_manual']}))
        session.commit()
    queue = client.get('/api/officer/applications').json()
    assert queue['total'] == 1
    assert queue['rows'][0]['application_id'] == prepared
    assert_rejected_unchanged(client, prepared, no_processing,
                              data={'slot_key': 'auto'}, detail=AUTO_DETAIL)
