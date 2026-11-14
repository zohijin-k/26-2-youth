"""Versioned form-workflow metadata extending the existing postings registry."""
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
import json

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import select

from ..models import ProgramForm, ProgramPosting, get_session
from ..rules.programs import get_program
from ..rules.required_docs import ApplicantDocInput, WorkCategory, build_checklist
from ..rules.subsidy import Selection
from . import postings


def managed(posting: ProgramPosting) -> bool:
    return (posting.template_json or {}).get('workflow_version') == 1


def slot_catalog() -> dict[str, Any]:
    """Reuse existing requirements, retaining validators instead of inventing slots."""
    rows = {}
    for code in ('job_package', 'double_savings'):
        for category in (None, *WorkCategory):
            context = ApplicantDocInput(work_category=category, admin_fixed_term=True,
                handwritten_admin_consent=True,
                subsidy_selections=[Selection(item_type=kind) for kind in ('interview', 'suit', 'photo', 'certificate')])
            for req in build_checklist(get_program(code), context):
                if req.upload:
                    rows.setdefault(req.slot_key, req)
    return rows


def validate_slots(raw: str | list[str]) -> list[str]:
    try:
        values = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        raise HTTPException(422, '제출 서류 목록을 확인해 주세요.') from None
    catalog = slot_catalog()
    if not isinstance(values, list) or any(not isinstance(x, str) or x not in catalog for x in values):
        raise HTTPException(422, '제출 서류 목록에서 서류를 선택해 주세요.')
    return list(dict.fromkeys(values))


def form_rows(posting_id: int) -> list[ProgramForm]:
    with get_session() as s:
        return list(s.exec(select(ProgramForm).where(ProgramForm.posting_id == posting_id).order_by(ProgramForm.id)).all())


def form_path(row: ProgramForm) -> Path:
    root = postings.STORAGE.resolve()
    path = (root / row.file_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, '서식 PDF를 찾을 수 없습니다.')
    return path


def _form_dict(row: ProgramForm) -> dict[str, Any]:
    import pymupdf
    layout = dict(row.layout_json or {})
    if not layout.get('page_sizes'):
        with pymupdf.open(form_path(row)) as pdf:
            layout['page_sizes'] = [{'width': page.rect.width, 'height': page.rect.height} for page in pdf]
    return {'id': row.id, 'file_name': row.file_name,
        'file_url': f'/api/officer/postings/{row.posting_id}/workspace/forms/{row.id}.pdf',
        'layout': layout, 'confirmed': bool(row.confirmed_hash),
        'updated_at': row.updated_at.isoformat(timespec='seconds')}


def view(posting: ProgramPosting) -> dict[str, Any]:
    metadata = posting.template_json or {}
    return {'posting': postings._officer_view(posting), 'managed': managed(posting),
        'required_docs': metadata.get('required_docs', []),
        'slot_options': [{'key': key, 'label': req.label} for key, req in slot_catalog().items()],
        'forms': [_form_dict(row) for row in form_rows(posting.id or 0)]}


def editable(posting: ProgramPosting) -> None:
    if posting.rule_code is not None:
        raise HTTPException(409, '기본 사업은 읽기 전용입니다.')
    if posting.status != 'draft':
        raise HTTPException(409, '게시를 취소한 뒤 수정해 주세요.')
    if not managed(posting):
        raise HTTPException(409, '이전 방식으로 만든 사업입니다. 새 사업 올리기를 이용해 주세요.')


def initialize(s: Any, posting: ProgramPosting, required_docs: list[str],
        forms: list[tuple[bytes, str]], guidance: str) -> None:
    posting.template_json = {'workflow_version': 1, 'required_docs': required_docs}
    posting.guidance_text = guidance
    for index, (data, name) in enumerate(forms):
        relative = f'postings/{posting.id}/form-{uuid4().hex}.pdf'
        (postings.STORAGE / relative).write_bytes(data)
        s.add(ProgramForm(posting_id=posting.id, file_name=name, file_path=relative))
    s.add(posting)


@postings.officer_router.get('/slots/catalog')
def read_slots() -> dict[str, Any]:
    return {'items': [{'key': key, 'label': req.label} for key, req in slot_catalog().items()]}


@postings.officer_router.get('/{posting_id}/workspace')
def read_workspace(posting_id: int) -> dict[str, Any]:
    return view(postings._load(posting_id))


class WorkspacePatch(BaseModel):
    title: str
    apply_start: str
    apply_end: str
    guidance_text: str = ''
    required_docs: list[str] = []


@postings.officer_router.patch('/{posting_id}/workspace')
def update_workspace(posting_id: int, body: WorkspacePatch) -> dict[str, Any]:
    slots = validate_slots(body.required_docs)
    title = postings._clean_title(body.title)
    start = postings._parse_day(body.apply_start, postings.LABEL_START)
    end = postings._parse_day(body.apply_end, postings.LABEL_END)
    postings._check_period(start, end)
    if len(body.guidance_text) > postings.GUIDANCE_MAX:
        raise HTTPException(422, '안내 문구는 20,000자 이하로 입력해 주세요.')
    with get_session() as s:
        posting = postings._find(s, posting_id)
        editable(posting)
        posting.title, posting.apply_start, posting.apply_end = title, start, end
        posting.guidance_text = body.guidance_text
        posting.template_json = {**posting.template_json, 'required_docs': slots}
        posting.updated_at = datetime.now()
        s.add(posting)
        s.commit()
        s.refresh(posting)
    return view(posting)


@postings.officer_router.post('/{posting_id}/workspace/files')
def replace_files(posting_id: int, notice_pdf: UploadFile | None = File(None),
        forms_pdfs: list[UploadFile] = File(default=[])) -> dict[str, Any]:
    posting = postings._load(posting_id)
    editable(posting)
    notice = postings._read_pdf(notice_pdf, 'notice') if notice_pdf else None
    forms = [postings._read_pdf(upload, 'forms') for upload in forms_pdfs]
    if len(forms) > 10:
        raise HTTPException(422, '서식 PDF는 10개 이하로 올려 주세요.')
    with get_session() as s:
        posting = postings._find(s, posting_id)
        editable(posting)
        if notice:
            relative = f'postings/{posting_id}/notice-{uuid4().hex}.pdf'
            (postings.STORAGE / relative).write_bytes(notice[0])
            posting.notice_path, posting.notice_file_name = relative, notice[1]
        if forms:
            for old in s.exec(select(ProgramForm).where(ProgramForm.posting_id == posting_id)).all():
                s.delete(old)
            initialize(s, posting, posting.template_json.get('required_docs', []), forms, posting.guidance_text)
            posting.forms_path = s.exec(select(ProgramForm).where(ProgramForm.posting_id == posting_id)).first().file_path
            posting.forms_file_name = forms[0][1]
        posting.updated_at = datetime.now()
        s.add(posting)
        s.commit()
        s.refresh(posting)
    return view(posting)


@postings.officer_router.get('/{posting_id}/workspace/forms/{form_id}.pdf')
def officer_form(posting_id: int, form_id: int) -> FileResponse:
    postings._load(posting_id)
    with get_session() as s:
        row = s.get(ProgramForm, form_id)
        if row is None or row.posting_id != posting_id:
            raise HTTPException(404, '서식 PDF를 찾을 수 없습니다.')
    return FileResponse(form_path(row), media_type='application/pdf',
        headers={'Content-Disposition': 'inline', 'Cache-Control': 'no-store'})
