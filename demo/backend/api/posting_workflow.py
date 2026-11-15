"""Human confirmation is required before managed form templates are published."""
from datetime import datetime
import hashlib
import json
import math
import re
from typing import Any

import pymupdf
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..models import ProgramForm, get_session
from . import postings, posting_workspace as workspace

KINDS = {'text', 'number', 'date', 'check', 'radio', 'signature'}
AUTOFILL = {None, '', 'name', 'birth', 'mobile', 'phone', 'address', 'email'}


def layout_hash(layout: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(layout, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _form(s: Any, posting_id: int, form_id: int) -> tuple[Any, ProgramForm]:
    posting = postings._find(s, posting_id)
    workspace.editable(posting)
    row = s.get(ProgramForm, form_id)
    if row is None or row.posting_id != posting_id:
        raise HTTPException(404, '서식 PDF를 찾을 수 없습니다.')
    return posting, row


def validate_layout(row: ProgramForm, raw: dict[str, Any]) -> dict[str, Any]:
    fields = raw.get('fields')
    if not isinstance(fields, dict) or len(fields) > 500:
        raise HTTPException(422, '입력칸은 서식당 500개 이하로 입력해 주세요.')
    with pymupdf.open(workspace.form_path(row)) as pdf:
        sizes = [{'width': page.rect.width, 'height': page.rect.height} for page in pdf]
    clean = {}
    for key, field in fields.items():
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', key) or not isinstance(field, dict):
            raise HTTPException(422, '입력칸 식별자를 확인해 주세요.')
        kind = field.get('field_type', {'image':'signature'}.get(field.get('type'), field.get('type', 'text')))
        page = field.get('page')
        box = field.get('box')
        label = field.get('label', field.get('anchor', '입력칸'))
        source = field.get('autofill_source')
        if not isinstance(kind, str) or kind not in KINDS or not isinstance(source, (str, type(None))) or source not in AUTOFILL:
            raise HTTPException(422, '입력칸 종류와 자동 채움 출처를 확인해 주세요.')
        if not isinstance(label, str) or not label.strip() or len(label) > 200:
            raise HTTPException(422, '입력칸 라벨은 1~200자로 입력해 주세요.')
        if not isinstance(page, int) or isinstance(page, bool) or not 0 <= page < len(sizes):
            raise HTTPException(422, '입력칸 쪽 번호를 확인해 주세요.')
        if (not isinstance(box, list) or len(box) != 4 or any(isinstance(x, bool) or not isinstance(x, (int,float)) or not math.isfinite(x) for x in box)
                or not 0 <= box[0] < box[2] <= sizes[page]['width']
                or not 0 <= box[1] < box[3] <= sizes[page]['height']):
            raise HTTPException(422, '입력칸 상자는 PDF 쪽 안에 있어야 합니다.')
        confidence = field.get('confidence', 0)
        if isinstance(confidence, bool) or not isinstance(confidence, (int,float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise HTTPException(422, '입력칸 신뢰도를 확인해 주세요.')
        raw_size = field.get('size', 10)
        if not isinstance(raw_size, (int, float)) or isinstance(raw_size, bool):
            raise HTTPException(422, '입력칸 글자 크기를 확인해 주세요.')
        size = min(24, max(5, raw_size))
        if not math.isfinite(size):
            raise HTTPException(422, '입력칸 글자 크기를 확인해 주세요.')
        group = field.get('group') or ''
        if not isinstance(group, str) or len(group) > 80:
            raise HTTPException(422, '선택 묶음을 확인해 주세요.')
        clean[key] = {'type': 'image' if kind == 'signature' else 'check' if kind in {'check','radio'} else 'text',
            'field_type':kind, 'page':page, 'box':box, 'x':box[0]+2, 'y':box[3]-3,
            'size':size, 'label':label.strip(), 'anchor':label.strip(), 'required':bool(field.get('required', False)),
            'autofill_source':source or None, 'confidence':confidence,
            'needs_review':field.get('needs_review',True) is not False, 'group':group,
            'align':'left','font_family':'sans'}
    return {'form_no': f'form_{row.id}', 'title': row.file_name, 'template':row.file_path,
        'fields':clean, 'page_sizes':sizes, 'public_form':None, 'internal_form':None,
        'status':'draft' if clean else 'manual_required', 'confirmed':False}


def publish_blockers(posting: Any) -> list[str]:
    if not workspace.managed(posting):
        return []
    problems = []
    if not posting.title.strip(): problems.append('사업명을 입력해 주세요.')
    if posting.apply_start > posting.apply_end or posting.apply_end < postings._today():
        problems.append('신청 기간이 유효하지 않습니다.')
    if postings._stored_file(posting, 'notice') is None: problems.append('공고문 PDF를 올려 주세요.')
    forms = workspace.form_rows(posting.id or 0)
    if not forms: problems.append('서식 PDF를 하나 이상 올려 주세요.')
    for row in forms:
        try: workspace.form_path(row)
        except HTTPException: problems.append(f'{row.file_name}: 서식 PDF가 없습니다.')
        fields = (row.layout_json or {}).get('fields', {})
        if not fields or not row.confirmed_hash or row.confirmed_hash != layout_hash(row.layout_json):
            problems.append(f'{row.file_name}: 서식 틀을 확인하고 확정해 주세요.')
    return problems




class LayoutBody(BaseModel):
    layout: dict[str, Any]


@postings.officer_router.put('/{posting_id}/workspace/forms/{form_id}/layout')
def save_layout(posting_id: int, form_id: int, body: LayoutBody) -> dict[str, Any]:
    with get_session() as s:
        posting, row = _form(s, posting_id, form_id)
        row.layout_json = validate_layout(row, body.layout)
        row.confirmed_hash = None
        row.updated_at = datetime.now()
        s.add(row)
        s.commit()
        s.refresh(posting)
    return workspace.view(posting)


@postings.officer_router.post('/{posting_id}/workspace/forms/{form_id}/confirm')
def confirm_layout(posting_id: int, form_id: int) -> dict[str, Any]:
    with get_session() as s:
        posting, row = _form(s, posting_id, form_id)
        fields = (row.layout_json or {}).get('fields', {})
        if not fields or any(field.get('needs_review',True) for field in fields.values()):
            raise HTTPException(409, '입력칸이 하나 이상이어야 하며 확인 필요 칸을 모두 확인하거나 삭제해 주세요.')
        row.confirmed_hash = layout_hash(row.layout_json)
        row.updated_at = datetime.now()
        s.add(row)
        s.commit()
        s.refresh(posting)
    return workspace.view(posting)


@postings.officer_router.get('/{posting_id}/workspace/forms/{form_id}/pages/{page}.png')
def form_page(posting_id: int, form_id: int, page: int) -> Response:
    with get_session() as s:
        postings._find(s, posting_id)
        row = s.get(ProgramForm, form_id)
        if row is None or row.posting_id != posting_id:
            raise HTTPException(404, '서식을 찾을 수 없습니다.')
    with pymupdf.open(workspace.form_path(row)) as pdf:
        if not 0 <= page < pdf.page_count:
            raise HTTPException(404, '서식 쪽을 찾을 수 없습니다.')
        data = pdf[page].get_pixmap(dpi=110).tobytes('png')
    return Response(data, media_type='image/png', headers={'Cache-Control':'no-store'})


@postings.officer_router.post('/{posting_id}/unpublish')
def unpublish(posting_id: int) -> dict[str, Any]:
    with get_session() as s:
        posting = postings._find(s, posting_id)
        if posting.rule_code is not None:
            raise HTTPException(409, '기본 사업은 읽기 전용입니다.')
        posting.status = 'draft'
        posting.updated_at = datetime.now()
        s.add(posting)
        s.commit()
        s.refresh(posting)
    return workspace.view(posting)
