"""Per-program generic review detail and evidence-confirmation API."""
from __future__ import annotations


from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlmodel import select
import pymupdf
from engine_v2.pipeline.privacy import mask_data

from ..models import transactional_write
from .. import generic_programs as generic
from ..generic_review import GenericReviewChecks, approval_blockers, checks_for, criteria_for, evidence
from ..models import Application, Document, ProgramPosting, Review, get_session
from ..rules.roles import ROLE_PROVINCE, decision_label, get_role
from . import officer
from .common import checklist_for, list_documents

router = APIRouter(prefix='/api/officer/programs', tags=['generic officer review'])


def _load(posting_id: int, application_id: int) -> tuple[Application, Review | None, ProgramPosting]:
    if not 0 < posting_id < 2**63 or not 0 < application_id < 2**63:
        raise HTTPException(404, '심사할 수 있는 신청 건을 찾을 수 없습니다.')
    with get_session() as session:
        posting = session.get(ProgramPosting, posting_id)
        app = session.get(Application, application_id)
        if (posting is None or posting.rule_code is not None or app is None or app.status == 'draft'
                or app.program_code != f'posting_{posting_id}'):
            raise HTTPException(404, '심사할 수 있는 신청 건을 찾을 수 없습니다.')
        review = session.exec(select(Review).where(Review.application_id == application_id)).first()
    if generic.snapshot(app).posting_id != posting_id:
        raise HTTPException(404, '심사할 수 있는 신청 건을 찾을 수 없습니다.')
    return app, review, posting


def _role(key: str):
    try:
        return get_role(key)
    except ValueError:
        raise HTTPException(400, '담당자 역할을 확인해 주세요.') from None


def _written(app: Application, posting_id: int) -> dict[str, Any]:
    return {'document_id': -(app.id or 0), 'check_id': 'written', 'slot_key': 'written',
            'label': '작성한 서식', 'file_url': f'/api/officer/programs/{posting_id}/applications/{app.id}/written.pdf',
            'file_name': '작성한 서식.pdf', 'file_format': 'pdf', 'status': 'NEEDS_REVIEW',
            'findings': [], 'extracted': {}, 'bboxes': {}, 'page_index': None,
            'expected_doc_type': None, 'detected_doc_type': None, 'classification_evidence': '',
            'ocr_confidence': None, 'ocr_tier': None, 'ocr_engine': None,
            'ocr_fallback_reason': None, 'ocr_quality_note': None,
            'declared_issue_date': None, 'uploaded_at': None}


def _original_bytes(relative: str | None) -> bytes:
    from .common import STORAGE
    if not relative:
        raise HTTPException(404, '서류 원본을 찾을 수 없습니다.')
    root = STORAGE.resolve()
    target = (root.parent / relative).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404, '서류 원본을 찾을 수 없습니다.')
    return target.read_bytes()


def _preview_metadata(document: dict[str, Any], relative: str | None,
                      posting_id: int, application_id: int) -> dict[str, Any]:
    if document.get('file_format') != 'pdf':
        return document
    try:
        with pymupdf.open(stream=_original_bytes(relative), filetype='pdf') as original:
            if original.needs_pass or not original.page_count:
                return document
            document['page_count'] = original.page_count
            if original.page_count == 1:
                document['page_image_url'] = (f'/api/officer/programs/{posting_id}/applications/'
                    f'{application_id}/documents/{document["document_id"]}/page.png')
    except Exception:
        # Missing/corrupt originals retain their existing viewer/error handling;
        # filesystem or PDF exceptions must not expose stored paths.
        pass
    return document


@router.get('/{posting_id}/applications/{application_id}/documents/{document_id}/page.png')
def single_original_page(posting_id: int, application_id: int, document_id: int) -> Response:
    application, _, _ = _load(posting_id, application_id)
    if document_id == -application_id:
        relative = application.written_forms_archive_path
    else:
        with get_session() as session:
            row = session.get(Document, document_id) if 0 < document_id < 2**63 else None
            if row is None or row.application_id != application_id or (row.file_format or '').lower() != 'pdf':
                raise HTTPException(404, '서류 원본을 찾을 수 없습니다.')
            relative = row.file_path
    data = _original_bytes(relative)
    try:
        with pymupdf.open(stream=data, filetype='pdf') as original:
            if original.needs_pass or original.page_count != 1:
                raise ValueError('single page unavailable')
            png = original[0].get_pixmap(dpi=150).tobytes('png')
    except Exception:
        raise HTTPException(404, '서류 원본의 쪽을 표시할 수 없습니다.') from None
    return Response(png, media_type='image/png',
                    headers={'Content-Disposition': 'inline', 'Cache-Control': 'no-store'})


@router.get('/{posting_id}/applications/{application_id}')
def detail(posting_id: int, application_id: int, role: str = Query(ROLE_PROVINCE)) -> dict[str, Any]:
    app, review, posting = _load(posting_id, application_id)
    role_config = _role(role)
    labels = {row.slot_key: row.label for row in checklist_for(app)}
    documents = [_preview_metadata(dict(officer._document_view(row, labels), check_id=str(row.id)),
                                  row.file_path, posting_id, application_id)
                 for row in list_documents(application_id)]
    documents.append(_preview_metadata(_written(app, posting_id), app.written_forms_archive_path,
                                       posting_id, application_id))
    problems = approval_blockers(app, review)
    payload = mask_data({'application_id': app.id, 'posting_id': posting_id,
        'application_no': app.application_no, 'name': (app.identity_json or {}).get('name', ''),
        'program_code': app.program_code, 'program_name': posting.title,
        'status': app.status, 'submitted_at': app.submitted_at.isoformat() if app.submitted_at else None,
        'ai': {'final_status': review.final_status if review else None,
               'final_status_label': officer.AI_STATUS_LABELS.get(review.final_status, '미심사') if review else '미심사',
               'stage1_status': review.stage1_status if review else None,
               'stage2_status': review.stage2_status if review else None},
        'documents': documents, 'criteria': criteria_for(app, review),
        'decision': {'decision': review.officer_decision if review else None,
                     'memo': review.officer_memo if review else None,
                     'officer_role': review.officer_role if review else None,
                     'label': decision_label(review.officer_role, review.officer_decision) if review else '미처리'},
        'role': officer._role_dict(role_config),
        'can_approve': not problems and app.status != 'decided', 'approval_blockers': problems})
    payload['checks'] = checks_for(app, review)
    return payload


class ChecksRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    checklist_ids: list[str] = Field(default_factory=list)
    fingerprint: str = Field(min_length=64, max_length=64)


@router.put('/{posting_id}/applications/{application_id}/checks')
@transactional_write
def confirm_checks(posting_id: int, application_id: int, body: ChecksRequest) -> dict[str, Any]:
    app, review, _ = _load(posting_id, application_id)
    if app.status == 'decided':
        raise HTTPException(409, '이미 최종 처리한 신청 건입니다.')
    fingerprint, document_ids, checklist_ids = evidence(app, review)
    if body.fingerprint != fingerprint:
        raise HTTPException(409, '검토 자료가 바뀌었습니다. 새로고침한 뒤 다시 확인해 주세요.')
    if not set(body.document_ids).issubset(document_ids) or not set(body.checklist_ids).issubset(checklist_ids):
        raise HTTPException(422, '이 신청 건의 서류와 기준만 확인할 수 있습니다.')
    with get_session() as session:
        row = session.get(GenericReviewChecks, application_id) or GenericReviewChecks(application_id=application_id)
        row.checks_json = {'fingerprint': fingerprint, 'document_ids': sorted(set(body.document_ids)),
                           'checklist_ids': sorted(set(body.checklist_ids))}
        row.updated_at = datetime.now()
        session.add(row)
        session.commit()
    return detail(posting_id, application_id, ROLE_PROVINCE)


@router.post('/{posting_id}/applications/{application_id}/decision')
@transactional_write
def decide(posting_id: int, application_id: int, body: officer.DecisionRequest) -> dict[str, Any]:
    _load(posting_id, application_id)
    role = _role(body.role)
    officer._check_action(role, body.decision)
    officer._apply_decision(application_id, role, body.decision, body.memo, body.notice)
    return detail(posting_id, application_id, body.role)


@router.get('/{posting_id}/applications/{application_id}/written.pdf')
def written_original(posting_id: int, application_id: int) -> FileResponse:
    app, _, _ = _load(posting_id, application_id)
    from .common import STORAGE
    if not app.written_forms_archive_path:
        raise HTTPException(404, '작성한 서식 원본을 찾을 수 없습니다.')
    root = STORAGE.resolve()
    path = (root.parent / app.written_forms_archive_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, '작성한 서식 원본을 찾을 수 없습니다.')
    return FileResponse(path, media_type='application/pdf',
                        headers={'Content-Disposition': 'inline', 'Cache-Control': 'no-store'})
