"""Evidence-bound human checks for submitted generic program applications."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel, select

from . import generic_programs as generic
from .models import Application, Document, Review, get_session


class GenericReviewChecks(SQLModel, table=True):
    application_id: int = Field(primary_key=True, foreign_key='application.id')
    checks_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=datetime.now)


def criteria_for(app: Application, review: Review | None) -> list[dict[str, Any]]:
    """Read frozen criteria and recorded rule outcomes without calculating verdicts."""
    frozen = generic.snapshot(app).snapshot_json
    candidates = frozen.get('criteria') or []
    if not candidates:
        candidates = [{'id': 'program_manual', 'type': 'checklist', 'label': '공고문 기준 확인',
                       'values': {}, 'needs_review': False}]
    payload = (review.review_payload_json or {}) if review else {}
    raw_results = payload.get('criteria_results', payload.get('generic_criteria_results', []))
    if isinstance(raw_results, dict):
        results = raw_results
    else:
        results = {row.get('id'): row for row in raw_results if isinstance(row, dict)}
    rows = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        identifier = str(candidate.get('id') or f'criterion_{index}')
        raw = results.get(identifier, {})
        result = raw if isinstance(raw, dict) else {'status': raw}
        kind = candidate.get('type', 'checklist')
        status = result.get('status', result.get('result', 'NEEDS_REVIEW'))
        if status not in {'PASS', 'FAIL', 'NEEDS_REVIEW'}:
            status = 'NEEDS_REVIEW'
        rows.append({**candidate, 'id': identifier, 'type': kind, 'result': status,
                     'basis': result.get('basis', result.get('message', '담당자가 공고문과 원본을 확인해 주세요.')),
                     'source_document_ids': result.get('source_document_ids', []),
                     'requires_check': kind == 'checklist' or status != 'PASS'})
    return rows


def _file_digest(file_path: str | None) -> str | None:
    if not file_path:
        return None
    from .api.common import STORAGE
    root = STORAGE.resolve()
    target = (root.parent / file_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return hashlib.sha256(target.read_bytes()).hexdigest()


def evidence(app: Application, review: Review | None) -> tuple[str, list[str], list[str]]:
    with get_session() as session:
        documents = list(session.exec(select(Document).where(Document.application_id == app.id)).all())
    documents.sort(key=lambda row: row.id or 0)
    document_ids = [str(row.id) for row in documents] + ['written']
    criteria = criteria_for(app, review)
    checklist_ids = [row['id'] for row in criteria if row['requires_check']]
    state = {
        'documents': [{'row': row.model_dump(mode='json'), 'file_digest': _file_digest(row.file_path)}
                      for row in documents],
        'written_digest': _file_digest(app.written_forms_archive_path),
        'form_values': app.form1_json,
        'identity': app.identity_json,
        'criteria': criteria,
        'review': {'final_status': review.final_status, 'stage1_status': review.stage1_status,
                   'stage2_status': review.stage2_status, 'payload': review.review_payload_json} if review else None,
        'snapshot': generic.snapshot(app).snapshot_json,
    }
    encoded = json.dumps(state, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest(), document_ids, checklist_ids


def checks_for(app: Application, review: Review | None) -> dict[str, Any]:
    fingerprint, document_ids, checklist_ids = evidence(app, review)
    with get_session() as session:
        stored = session.get(GenericReviewChecks, app.id)
    saved = stored.checks_json if stored else {}
    current = bool(saved) and saved.get('fingerprint') == fingerprint
    return {'fingerprint': fingerprint, 'current': current,
            'document_ids': saved.get('document_ids', []) if current else [],
            'checklist_ids': saved.get('checklist_ids', []) if current else [],
            'required_document_ids': document_ids, 'required_checklist_ids': checklist_ids}


def approval_blockers(app: Application, review: Review | None) -> list[str]:
    problems = []
    if review is None:
        problems.append('서류 검토 결과가 필요합니다.')
    from .api.common import STORAGE
    root = STORAGE.resolve()
    with get_session() as session:
        originals = list(session.exec(select(Document).where(Document.application_id == app.id)).all())
    paths = [row.file_path for row in originals] + [app.written_forms_archive_path]
    for file_path in paths:
        path = (root.parent / file_path).resolve() if file_path else None
        if path is None or not path.is_relative_to(root) or not path.is_file():
            problems.append('확인할 원본 파일이 없어 최종 선정할 수 없습니다.')
            break
    checks = checks_for(app, review)
    if not set(checks['required_document_ids']).issubset(checks['document_ids']):
        problems.append('제출 서류와 작성한 서식 원본을 모두 확인해 주세요.')
    if not set(checks['required_checklist_ids']).issubset(checks['checklist_ids']):
        problems.append('사업 기준 체크리스트를 모두 확인해 주세요.')
    return problems


def validate_decision(app: Application, review: Review | None, decision: str, memo: str) -> None:
    """Shared guard for both generic and pre-existing decision entry points."""
    if not generic.is_generic(app.program_code):
        return
    if app.status == 'decided':
        raise HTTPException(409, '이미 최종 처리한 신청 건입니다.')
    if decision in {'hold', 'reject'} and not memo.strip():
        raise HTTPException(422, '보류·반려 사유를 입력해 주세요.')
    if decision == 'approve':
        problems = approval_blockers(app, review)
        if problems:
            raise HTTPException(409, ' '.join(problems))


def validate_bulk_decisions(application_ids: list[int], decision: str, memo: str) -> None:
    """Preflight generic rows before any member of a bulk request changes."""
    valid_ids = sorted({identifier for identifier in application_ids if 0 < identifier < 2**63})
    with get_session() as session:
        applications = list(session.exec(select(Application).where(Application.id.in_(valid_ids))).all())
        reviews = {row.application_id: row for row in session.exec(
            select(Review).where(Review.application_id.in_(valid_ids))).all()}
    for app in applications:
        if not generic.is_generic(app.program_code) or app.status == 'draft':
            continue
        if application_ids.count(app.id) > 1:
            raise HTTPException(422, '같은 신청 건을 중복해서 처리할 수 없습니다.')
        review = reviews.get(app.id)
        if decision == 'approve' and (review is None or review.final_status != 'PASS'):
            raise HTTPException(409, '확인 필요 건은 심사 화면에서 건별로 처리해 주세요.')
        validate_decision(app, review, decision, memo)
