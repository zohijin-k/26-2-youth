"""사업 저장소 API (리뉴얼 1단계).

담당자가 사업을 올리고(`/api/officer/postings`), 신청자가 게시된 사업을 찾아
읽는다(`/api/postings`). 두 화면이 같은 `ProgramPosting` 행을 본다 — 담당자가
게시하면 신청자 목록에 나타나고, 마감하면 신청자 목록에서 마감으로 바뀐다.

이 모듈이 지키는 것 셋:

  1. **작성 중인 사업은 신청자에게 보이지 않는다.** 목록에서 빠지고, 단건 조회와
     공고문 파일도 404다.
  2. **파일은 인라인으로만 나간다.** 공고문·서식 PDF는 `api/files.py`와 같은
     방식(`Content-Disposition: inline`)으로 브라우저 안에서만 열린다.
  3. **신청 건수는 담당자 목록과 같은 기준으로 센다.** AI 판정과 담당자 판단을
     다시 풀지 않고 `api/officer.py`의 `Entry`를 그대로 읽는다. 여기서 따로 세면
     사업 카드의 숫자와 목록의 행 수가 언젠가 어긋난다.

`/api/programs`(규칙 세트 조회)는 그대로 둔다. 이쪽은 담당자가 게시하는 단위다.
"""

import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import select

from .. import models
from ..models import (
    POSTING_CLOSED,
    POSTING_DRAFT,
    POSTING_PUBLISHED,
    ProgramPosting,
    get_session,
)
from .common import STORAGE
from .files import DISPOSITION, INLINE_MEDIA_TYPES
from .officer import QUEUE_NEEDS_CHECK, _load_entries, queue_of

public_router = APIRouter(prefix="/api/postings", tags=["postings"])
officer_router = APIRouter(prefix="/api/officer/postings", tags=["officer postings"])

#: 저장소 루트 아래 사업 파일 폴더. 사업마다 `postings/<id>/`를 쓴다.
POSTINGS_DIR = "postings"

#: 올릴 수 있는 PDF 한 개의 최대 크기.
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_LABEL = "20MB"

#: PDF 파일의 첫 바이트. 확장자나 브라우저가 보낸 형식은 믿지 않는다.
PDF_MAGIC = b"%PDF-"

TITLE_MAX = 100
#: 안내 문구 길이 상한. 신청자 화면에 그대로 나가는 글이다.
GUIDANCE_MAX = 20_000

#: 접수 단계. 상태(draft/published/closed)와 오늘 날짜로 정해진다.
PHASE_DRAFT = "draft"
PHASE_UPCOMING = "upcoming"
PHASE_OPEN = "open"
PHASE_CLOSED = "closed"

PHASE_LABELS = {
    PHASE_DRAFT: "작성 중",
    PHASE_UPCOMING: "접수 예정",
    PHASE_OPEN: "접수 중",
    PHASE_CLOSED: "마감",
}

#: 목록 순서. 신청자 목록에는 작성 중인 사업이 없으므로 한 표로 같이 쓴다.
PHASE_ORDER = {PHASE_DRAFT: 0, PHASE_OPEN: 1, PHASE_UPCOMING: 2, PHASE_CLOSED: 3}

#: 기본 사업의 신청 화면 진입 경로. 새로 올린 사업의 신청 화면은 4단계에서 만든다.
APPLY_PATH = "/apply/identity"

#: 파일 종류 → (경로 컬럼, 원래 이름 컬럼, 오류 문구에 쓰는 이름).
FILE_KINDS: dict[str, tuple[str, str, str]] = {
    "notice": ("notice_path", "notice_file_name", "공고문 PDF"),
    "forms": ("forms_path", "forms_file_name", "서식 PDF"),
}

#: 오류 문구에 쓰는 입력 항목 이름.
LABEL_TITLE = "사업명"
LABEL_START = "접수 시작일"
LABEL_END = "접수 종료일"

_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def _today() -> date:
    """오늘 날짜. 기본 사업을 올릴 때와 같은 출처(`models.posting_today`)를 본다."""
    return models.posting_today()


# ---------------------------------------------------------------- 파생 값


def phase_of(posting: ProgramPosting, today: date) -> str:
    """접수 단계.

    기간이 지난 게시 사업은 담당자가 마감을 누르지 않았어도 마감이다. 신청자에게
    "접수 중"으로 보이는데 기간이 끝나 있는 일을 막는다.
    """
    if posting.status == POSTING_DRAFT:
        return PHASE_DRAFT
    if posting.status == POSTING_CLOSED or today > posting.apply_end:
        return PHASE_CLOSED
    if today < posting.apply_start:
        return PHASE_UPCOMING
    return PHASE_OPEN


def _stored_file(posting: ProgramPosting, kind: str) -> Path | None:
    """저장된 PDF의 실제 경로. 없으면 None. 저장소 밖으로 나가는 경로는 없는 것으로 본다."""
    relative = getattr(posting, FILE_KINDS[kind][0])
    if not relative:
        return None
    root = STORAGE.resolve()
    target = (STORAGE / relative).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target


def _sort_key(posting: ProgramPosting, today: date) -> tuple[int, int, int]:
    """단계 순서 → 접수 시작일이 늦은 것부터 → 나중에 만든 것부터."""
    return (
        PHASE_ORDER[phase_of(posting, today)],
        -posting.apply_start.toordinal(),
        -(posting.id or 0),
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _public_dict(posting: ProgramPosting, today: date) -> dict[str, Any]:
    """신청자 목록의 사업 한 건."""
    phase = phase_of(posting, today)
    builtin = posting.rule_code is not None
    can_apply = phase == PHASE_OPEN and builtin
    return {
        "id": posting.id,
        "title": posting.title,
        "apply_start": posting.apply_start.isoformat(),
        "apply_end": posting.apply_end.isoformat(),
        "phase": phase,
        "phase_label": PHASE_LABELS[phase],
        "builtin": builtin,
        "can_apply": can_apply,
        "apply_path": APPLY_PATH if can_apply else None,
        "has_notice": _stored_file(posting, "notice") is not None,
    }


def _public_detail_dict(posting: ProgramPosting, today: date) -> dict[str, Any]:
    """신청자 사업 안내 화면이 읽는 전부."""
    data = _public_dict(posting, today)
    data["guidance_text"] = posting.guidance_text or ""
    data["notice_url"] = (
        f"/api/postings/{posting.id}/files/notice.pdf" if data["has_notice"] else None
    )
    return data


def _officer_dict(
    posting: ProgramPosting, today: date, counts: dict[str, tuple[int, int]]
) -> dict[str, Any]:
    """담당자 화면의 사업 한 건.

    파일 주소는 담당자 경로를 가리킨다. 작성 중인 사업의 공고문은 신청자 경로에서
    404이므로, 담당자가 게시 전에 열어 볼 수 있는 주소는 이쪽뿐이다.
    """
    data = _public_detail_dict(posting, today)
    has_forms = _stored_file(posting, "forms") is not None
    base = f"/api/officer/postings/{posting.id}/files"
    application_count, needs_check_count = counts.get(posting.rule_code or "", (0, 0))
    data.update(
        {
            "notice_url": f"{base}/notice.pdf" if data["has_notice"] else None,
            "status": posting.status,
            "has_forms": has_forms,
            "forms_url": f"{base}/forms.pdf" if has_forms else None,
            "notice_file_name": posting.notice_file_name,
            "forms_file_name": posting.forms_file_name,
            "application_count": application_count,
            "needs_check_count": needs_check_count,
            # 이름을 고치고 지울 수 있는 사업인가. 기본 사업도 기간과 안내 문구는 고친다.
            "editable": not data["builtin"],
            "created_at": _iso(posting.created_at),
            "updated_at": _iso(posting.updated_at),
            "published_at": _iso(posting.published_at),
        }
    )
    return data


def _counts(postings: list[ProgramPosting]) -> dict[str, tuple[int, int]]:
    """규칙 코드별 (신청 건수, 확인 필요 건수).

    제출된 신청 건만 센다(`_load_entries`가 임시저장을 뺀다). 확인 필요는 담당자
    판단이 아직 없고 AI 판정이 적합이 아닌 건 — 확인필요·부적합·미심사 — 이다.
    신청 목록의 확인 필요 탭과 같은 함수(`officer.queue_of`)로 가른다.
    규칙 코드가 없는 사업은 신청 화면이 아직 없어 여기에 잡히지 않고 0으로 나간다.
    """
    codes = {p.rule_code for p in postings if p.rule_code}
    if not codes:
        return {}
    tally = {code: [0, 0] for code in codes}
    for entry in _load_entries():
        row = tally.get(entry.app.program_code)
        if row is None:
            continue
        row[0] += 1
        if queue_of(entry) == QUEUE_NEEDS_CHECK:
            row[1] += 1
    return {code: (total, needs) for code, (total, needs) in tally.items()}


def _officer_view(posting: ProgramPosting) -> dict[str, Any]:
    return _officer_dict(posting, _today(), _counts([posting]))


# ---------------------------------------------------------------- 조회·검증


#: SQLite 정수 범위. 이보다 큰 번호는 조회 자체가 오류가 되므로 없는 사업으로 답한다.
_ID_LIMIT = 2**63


def _find(session: Any, posting_id: int) -> ProgramPosting:
    """번호로 사업을 찾는다. 없거나 번호가 범위를 벗어나면 404."""
    posting = session.get(ProgramPosting, posting_id) if 0 < posting_id < _ID_LIMIT else None
    if posting is None:
        raise HTTPException(404, "사업을 찾을 수 없습니다.")
    return posting


def _load(posting_id: int) -> ProgramPosting:
    with get_session() as s:
        posting = _find(s, posting_id)
        return posting


def _load_public(posting_id: int) -> ProgramPosting:
    """신청자가 볼 수 있는 사업만. 작성 중인 사업은 없는 것과 같게 답한다."""
    posting = _load(posting_id)
    if posting.status == POSTING_DRAFT:
        raise HTTPException(404, "사업을 찾을 수 없습니다.")
    return posting


def _clean_title(value: str | None) -> str:
    # 줄바꿈·탭·연속 공백은 한 칸으로 줄인다. 그 밖의 제어 문자는 받지 않는다.
    title = " ".join((value or "").split())
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
        raise HTTPException(422, f"{LABEL_TITLE}에 쓸 수 없는 문자가 있습니다.")
    if not title:
        raise HTTPException(422, f"{LABEL_TITLE}을 입력해 주세요.")
    if len(title) > TITLE_MAX:
        raise HTTPException(422, f"{LABEL_TITLE}은 {TITLE_MAX}자 이하로 입력해 주세요.")
    return title


def _parse_day(value: str | None, label: str) -> date:
    text = (value or "").strip()
    if not text:
        raise HTTPException(422, f"{label}을 입력해 주세요.")
    if not _ISO_DAY.fullmatch(text):
        raise HTTPException(422, f"{label}은 YYYY-MM-DD 형식으로 입력해 주세요.")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise HTTPException(422, f"{label}이 올바른 날짜가 아닙니다.") from None


def _check_period(start: date, end: date) -> None:
    if start > end:
        raise HTTPException(422, f"{LABEL_START}은 {LABEL_END}보다 늦을 수 없습니다.")


def _read_pdf(upload: UploadFile | None, kind: str) -> tuple[bytes, str]:
    """올린 PDF의 바이트와 원래 이름. 한도보다 1바이트만 더 읽어 크기를 잰다."""
    label = FILE_KINDS[kind][2]
    if upload is None or not upload.filename:
        raise HTTPException(422, f"{label} 파일을 올려 주세요.")
    data = upload.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(422, f"{label}는 {MAX_PDF_LABEL} 이하만 올릴 수 있습니다.")
    if not data.startswith(PDF_MAGIC):
        raise HTTPException(422, f"{label}는 PDF 파일만 올릴 수 있습니다.")
    import pymupdf
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise HTTPException(422, f"{label}의 암호를 해제한 뒤 올려 주세요.")
            if not pdf.page_count:
                raise HTTPException(422, f"{label}에 쪽이 없습니다.")
            if kind == "forms" and pdf.page_count > 20:
                raise HTTPException(422, "서식 PDF는 파일당 20쪽 이하로 올려 주세요.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, f"{label}를 읽을 수 없습니다. 정상적인 PDF를 올려 주세요.") from None
    name = Path(upload.filename.replace("\\", "/")).name.strip()[:200]
    return data, name or f"{kind}.pdf"


def _folder(posting_id: int) -> Path:
    return STORAGE / POSTINGS_DIR / str(posting_id)


def _serve(posting: ProgramPosting, kind: str) -> FileResponse:
    """저장된 PDF를 브라우저 안에서 연다. `api/files.py`와 같은 헤더를 쓴다."""
    _, name_column, label = FILE_KINDS[kind]
    target = _stored_file(posting, kind)
    if target is None:
        raise HTTPException(404, f"{label} 파일을 찾을 수 없습니다.")
    name = quote(getattr(posting, name_column) or target.name)
    return FileResponse(
        target,
        media_type=INLINE_MEDIA_TYPES["pdf"],
        headers={
            "Content-Disposition": f"{DISPOSITION}; filename*=UTF-8''{name}",
            "Cache-Control": "no-store",
        },
    )


# ---------------------------------------------------------------- 신청자


@public_router.get("")
def list_public_postings() -> dict[str, Any]:
    """게시됐거나 마감된 사업. 접수 중 → 접수 예정 → 마감 순이다."""
    today = _today()
    with get_session() as s:
        rows = list(
            s.exec(
                select(ProgramPosting).where(ProgramPosting.status != POSTING_DRAFT)
            ).all()
        )
    rows.sort(key=lambda p: _sort_key(p, today))
    return {"items": [_public_dict(p, today) for p in rows]}


@public_router.get("/{posting_id}")
def read_public_posting(posting_id: int) -> dict[str, Any]:
    return _public_detail_dict(_load_public(posting_id), _today())


@public_router.get("/{posting_id}/files/notice.pdf")
def public_notice_file(posting_id: int) -> FileResponse:
    """공고문 PDF. 신청자에게는 공고문만 열린다 — 서식 PDF 경로는 담당자 쪽에만 있다."""
    return _serve(_load_public(posting_id), "notice")


# ---------------------------------------------------------------- 담당자


class PostingPatch(BaseModel):
    title: str | None = None
    #: YYYY-MM-DD
    apply_start: str | None = None
    apply_end: str | None = None
    guidance_text: str | None = None


@officer_router.get("")
def list_officer_postings() -> dict[str, Any]:
    """사업 전체. 작성 중인 사업이 맨 앞이고 나머지는 신청자 목록과 같은 순서다."""
    today = _today()
    with get_session() as s:
        rows = list(s.exec(select(ProgramPosting)).all())
    rows.sort(key=lambda p: _sort_key(p, today))
    counts = _counts(rows)
    return {"items": [_officer_dict(p, today, counts) for p in rows]}


@officer_router.post("", status_code=201)
def create_posting(
    title: str | None = Form(None),
    apply_start: str | None = Form(None),
    apply_end: str | None = Form(None),
    notice_pdf: UploadFile | None = File(None),
    forms_pdf: UploadFile | None = File(None),
    forms_pdfs: list[UploadFile] = File(default=[]),
    workflow_version: int = Form(0),
    required_docs: str = Form("[]"),
    guidance_text: str = Form(""),
) -> dict[str, Any]:
    """새 사업을 작성 중 상태로 만든다.

    입력을 전부 확인한 뒤에야 행과 파일을 만든다. 파일을 쓰다 실패하면 행도
    남기지 않는다 — 파일 없는 사업이 목록에 떠 있으면 담당자가 게시를 못 한 채
    이유를 찾게 된다.
    """
    clean_title = _clean_title(title)
    start = _parse_day(apply_start, LABEL_START)
    end = _parse_day(apply_end, LABEL_END)
    _check_period(start, end)
    notice_bytes, notice_name = _read_pdf(notice_pdf, "notice")
    forms_bytes, forms_name = _read_pdf(forms_pdf, "forms")

    if workflow_version not in (0, 1):
        raise HTTPException(422, "사업 작성 방식을 확인해 주세요.")
    from . import posting_workspace
    slots = posting_workspace.validate_slots(required_docs)
    extras = [_read_pdf(upload, "forms") for upload in forms_pdfs]
    if len(extras) > 9:
        raise HTTPException(422, "서식 PDF는 10개 이하로 올려 주세요.")
    if len(guidance_text) > GUIDANCE_MAX:
        raise HTTPException(422, "안내 문구는 20,000자 이하로 입력해 주세요.")

    posting = ProgramPosting(
        title=clean_title,
        apply_start=start,
        apply_end=end,
        status=POSTING_DRAFT,
        notice_file_name=notice_name,
        forms_file_name=forms_name,
    )
    with get_session() as s:
        s.add(posting)
        s.flush()
        folder = _folder(posting.id or 0)
        try:
            # 지운 사업의 번호가 다시 쓰일 수 있다. 남은 폴더가 있으면 비우고 시작한다.
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True)
            (folder / "notice.pdf").write_bytes(notice_bytes)
            (folder / "forms.pdf").write_bytes(forms_bytes)
            posting.notice_path = f"{POSTINGS_DIR}/{posting.id}/notice.pdf"
            posting.forms_path = f"{POSTINGS_DIR}/{posting.id}/forms.pdf"
            if workflow_version == 1:
                posting_workspace.initialize(s, posting, slots, [(forms_bytes, forms_name), *extras], guidance_text)
            s.add(posting)
            s.commit()
        except Exception:
            s.rollback()
            shutil.rmtree(folder, ignore_errors=True)
            raise
        s.refresh(posting)
    return _officer_view(posting)


@officer_router.get("/{posting_id}")
def read_officer_posting(posting_id: int) -> dict[str, Any]:
    return _officer_view(_load(posting_id))


@officer_router.patch("/{posting_id}")
def update_posting(posting_id: int, body: PostingPatch) -> dict[str, Any]:
    """기본 항목 수정. 보낸 항목만 바꾼다.

    기본 사업의 이름은 규칙 세트(`rules/programs.py`)에서 온 값이라 여기서 바꾸지
    못한다. 접수 기간과 안내 문구는 담당자가 고칠 수 있다 — 이 기간은 목록과 신청
    가능 여부에만 쓰이고, 규칙 세트의 기준일·심사 기준과는 별개다.
    """
    with get_session() as s:
        posting = _find(s, posting_id)
        if posting.rule_code is not None and body.title is not None:
            raise HTTPException(409, "기본 사업의 이름은 바꿀 수 없습니다.")

        if body.title is not None:
            posting.title = _clean_title(body.title)
        start = (
            _parse_day(body.apply_start, LABEL_START)
            if body.apply_start is not None
            else posting.apply_start
        )
        end = (
            _parse_day(body.apply_end, LABEL_END)
            if body.apply_end is not None
            else posting.apply_end
        )
        _check_period(start, end)
        posting.apply_start = start
        posting.apply_end = end
        if body.guidance_text is not None:
            if len(body.guidance_text) > GUIDANCE_MAX:
                raise HTTPException(422, f"안내 문구는 {GUIDANCE_MAX:,}자 이하로 입력해 주세요.")
            posting.guidance_text = body.guidance_text
        posting.updated_at = datetime.now()
        s.add(posting)
        s.commit()
        s.refresh(posting)
    return _officer_view(posting)


@officer_router.post("/{posting_id}/publish")
def publish_posting(posting_id: int) -> dict[str, Any]:
    """작성 중이거나 마감한 사업을 게시한다. 게시하는 순간 신청자 목록에 나타난다."""
    with get_session() as s:
        posting = _find(s, posting_id)
        if posting.status == POSTING_PUBLISHED:
            raise HTTPException(409, "이미 게시한 사업입니다.")
        if posting.rule_code is None:
            for kind, (_, _, label) in FILE_KINDS.items():
                if _stored_file(posting, kind) is None:
                    raise HTTPException(409, f"{label}가 없어 게시할 수 없습니다.")
        now = datetime.now()
        posting.status = POSTING_PUBLISHED
        if posting.published_at is None:
            posting.published_at = now
        posting.updated_at = now
        s.add(posting)
        s.commit()
        s.refresh(posting)
    return _officer_view(posting)


@officer_router.post("/{posting_id}/close")
def close_posting(posting_id: int) -> dict[str, Any]:
    """게시한 사업을 마감한다. 신청자 목록에는 마감으로 남는다."""
    with get_session() as s:
        posting = _find(s, posting_id)
        if posting.status != POSTING_PUBLISHED:
            raise HTTPException(409, "게시한 사업만 마감할 수 있습니다.")
        posting.status = POSTING_CLOSED
        posting.updated_at = datetime.now()
        s.add(posting)
        s.commit()
        s.refresh(posting)
    return _officer_view(posting)


@officer_router.delete("/{posting_id}", status_code=204)
def delete_posting(posting_id: int) -> Response:
    """작성 중인 사업을 파일과 함께 지운다. 게시한 적이 있는 사업과 기본 사업은 지우지 못한다."""
    with get_session() as s:
        posting = _find(s, posting_id)
        if posting.rule_code is not None:
            raise HTTPException(409, "기본 사업은 지울 수 없습니다.")
        if posting.status != POSTING_DRAFT:
            raise HTTPException(409, "작성 중인 사업만 지울 수 있습니다.")
        s.delete(posting)
        s.commit()
    shutil.rmtree(_folder(posting_id), ignore_errors=True)
    return Response(status_code=204)


@officer_router.get("/{posting_id}/files/{kind}.pdf")
def officer_posting_file(posting_id: int, kind: str) -> FileResponse:
    """공고문(`notice`) 또는 서식(`forms`) PDF. 작성 중인 사업도 담당자는 열 수 있다."""
    if kind not in FILE_KINDS:
        raise HTTPException(404, "볼 수 있는 파일이 아닙니다.")
    return _serve(_load(posting_id), kind)
