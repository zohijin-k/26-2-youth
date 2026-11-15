"""Automatic field suggestions for managed posting PDFs."""
from datetime import datetime
from typing import Any
from fastapi import HTTPException
from ..forms.draft import draft_layout
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
