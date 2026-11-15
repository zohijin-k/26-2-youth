"""Automatic field suggestions for managed posting PDFs."""
from datetime import datetime
import math
from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel
from ..forms.draft import draft_layout, snap_field
from ..models import ProgramForm, get_session
from . import postings, posting_workspace as workspace

@postings.officer_router.post('/{posting_id}/workspace/forms/{form_id}/draft')
def draft_form(posting_id: int, form_id: int) -> dict[str, Any]:
    with get_session() as s:
        posting = postings._find(s, posting_id)
        workspace.editable(posting)
        row = s.get(ProgramForm, form_id)
        if row is None or row.posting_id != posting_id:
            raise HTTPException(404, '서식 PDF를 찾을 수 없습니다.')
        layout = draft_layout(workspace.form_path(row).read_bytes(), form_no=f'form_{row.id}',
            title=row.file_name, template=row.file_path)
        row.layout_json = layout
        row.confirmed_hash = None
        row.updated_at = datetime.now()
        s.add(row)
        s.commit()
        s.refresh(posting)
    return workspace.view(posting)


class SnapBody(BaseModel):
    page: int
    x: float
    y: float


@postings.officer_router.post('/{posting_id}/workspace/forms/{form_id}/snap')
def snap_form_field(posting_id: int, form_id: int, body: SnapBody) -> dict[str, Any]:
    """Suggest a box for one officer click; ``{"box": null}`` when nothing surrounds it."""
    if not all(math.isfinite(value) for value in (body.x, body.y)):
        raise HTTPException(422, '좌표를 확인해 주세요.')
    with get_session() as s:
        postings._find(s, posting_id)
        row = s.get(ProgramForm, form_id)
        if row is None or row.posting_id != posting_id:
            raise HTTPException(404, '서식 PDF를 찾을 수 없습니다.')
        path = workspace.form_path(row)
    try:
        suggestion = snap_field(path.read_bytes(), body.page, body.x, body.y)
    except IndexError:
        raise HTTPException(422, '서식 쪽 번호를 확인해 주세요.') from None
    except ValueError:
        raise HTTPException(422, '서식 PDF를 읽을 수 없습니다.') from None
    return suggestion or {'box': None}
