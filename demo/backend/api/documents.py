"""서류 체크리스트 · 업로드 즉시 판정 (P2).

두배적금은 **보완 요청이 없는 사업**이다. 제출 후에 미비를 알려주면 이미 늦다.
그래서 업로드하는 순간 적합/부적합/확인필요를 돌려주는 것이 이 모듈의 존재 이유다.

판정 로직은 `rules/doc_check.py`(엔진 단건 검사 재사용)에, 판독은 `ocr/`의 3계층
폴백 체인에 맡긴다. 여기서는 파일을 받아 저장하고 둘을 이어붙이는 일만 한다.
"""

import re
import pymupdf
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import select

from ..upload_assessment import assess_nhis_identity, assess_upload
from ..models import UNASSIGNED_SLOT, Application, Document, SubsidyItem, get_session
from .. import generic_programs as generic
from ..ocr import read_document, split_pdf_pages
from ..rules.identity import identity_of
from ..ocr.base import OcrResult
from engine_v2.pipeline.privacy import mask_data
from ..rules.doc_check import CheckFinding, CheckResult, THRESHOLD_NOTES, check_document
from ..rules.doc_types import DocType
from ..rules.criteria import for_application, read_criteria
from ..rules.programs import get_program
from ..rules.required_docs import (
    ACCEPTED_FORMATS,
    WORK_CATEGORIES,
    DocRequirement,
    WorkCategory,
    find_slot,
)
from .common import (
    STORAGE,
    checklist_for,
    document_dict,
    list_documents as load_documents,
    load_application,
)

router = APIRouter(prefix="/api/applications", tags=["documents"])

DOCUMENTS = STORAGE / "documents"

#: 병합 PDF 자동 분리를 요청하는 슬롯 키.
AUTO_SLOT = "auto"

#: 파일명에서 경로 구분자와 제어문자를 제거한다. fixture 매칭을 위해 원래 이름은 유지한다.
_UNSAFE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")


class DocContextRequest(BaseModel):
    """체크리스트를 결정하는 입력. 근로유형이 바뀌면 목록이 실제로 바뀐다."""

    work_category: str | None = None
    admin_fixed_term: bool = False
    workplace_count: int = 1
    handwritten_admin_consent: bool = False
    paper_forms: dict[str, bool] = Field(default_factory=dict)


#: 다른 라우터와 같은 조회·직렬화를 쓴다 (`api/common.py` 참고).
_load = load_application
_checklist = checklist_for
_document_dict = document_dict
_list_documents = load_documents


def _requirement_dict(req: DocRequirement, uploaded: list[Document]) -> dict[str, Any]:
    mine = [d for d in uploaded if d.slot_key == req.slot_key]
    return {
        "slot_key": req.slot_key,
        "doc_type": str(req.doc_type),
        "doc_type_choices": [str(d) for d in req.doc_type_choices],
        "required_fields": req.required_fields,
        "label": req.label,
        "required": req.required,
        "upload": req.upload,
        "fulfilled_by": req.fulfilled_by,
        "requires_signature": req.requires_signature,
        "check_declared_date": req.check_declared_date,
        "date_basis": req.date_basis,
        "date_basis_label": {"issue_date": "발급일", "payment_date": "결제일", "interview_date": "면접일", "exam_date": "응시일", "none": "없음"}.get(req.date_basis, "발급일"),
        "min_issue_date": req.min_issue_date.isoformat() if req.min_issue_date else None,
        "max_issue_date": req.max_issue_date.isoformat() if req.max_issue_date else None,
        "issue_rule_label": req.notes[0] if req.notes else "날짜 기준 없음",
        "issuer": req.issuer,
        "issuer_url": req.issuer_url,
        "notes": req.notes,
        "warnings": req.warnings,
        "alternatives": req.alternatives,
        "accept": req.accept,
        "documents": [_document_dict(d) for d in mine],
    }


def _checklist_response(app: Application) -> dict[str, Any]:
    checklist = _checklist(app)
    if generic.is_generic(app.program_code):
        return generic.checklist_response(app)
    program = get_program(app.program_code)
    criteria_version = for_application(app)
    criteria = read_criteria(criteria_version)
    uploaded = _list_documents(app.id or 0)
    items = [_requirement_dict(r, uploaded) for r in checklist]
    upload_items = [i for i in items if i["upload"]]
    done = [i for i in upload_items if i["documents"]]
    unassigned = [d for d in uploaded if d.slot_key == UNASSIGNED_SLOT]
    return {
        "context": app.doc_context_json or {},
        "work_categories": [str(c) for c in WORK_CATEGORIES],
        "accepted_formats": ACCEPTED_FORMATS,
        # 화면이 사업 코드로 분기하지 않도록, 무엇을 물어야 하는지를 여기서 알려준다.
        "program": {
            "code": program.code,
            "name": program.name,
            "selection": program.selection,
            "allows_supplement": criteria["supplement"]["allowed"],
            "supplement_days": criteria["supplement"]["days"],
            "announcement_date": criteria["announcement_date"],
            "application_period": criteria["application_period"],
            "application_period_2": criteria.get("application_period_2"),
            "criteria_version": criteria_version.version,
            "paper_forms": criteria["paper_forms"],
            "nhis_payment_months": criteria["nhis_payment_months"],
            "nhis_acquisition_loss_years": criteria["nhis_acquisition_loss_years"],
            #: 근로확인서류가 있는 사업에서만 근로유형을 묻는다.
            "asks_work_category": program.has_work_requirement,
            #: 지원 항목을 먼저 골라야 추가서류가 생기는 사업인가.
            "has_subsidy_items": program.has_subsidy_items,
        },
        "items": items,
        "upload_total": len(upload_items),
        "upload_done": len(done),
        "unassigned": [_document_dict(d) for d in unassigned],
        # 판정 컷라인은 TF 미확정 가정값이다. 화면에도 같은 라벨로 노출한다.
        "assumption_notes": list(THRESHOLD_NOTES),
    }


@router.get("/{application_id}/required-documents")
def required_documents(application_id: int) -> dict[str, Any]:
    """저장된 근로유형 기준의 맞춤 체크리스트 (R3.2)."""
    return _checklist_response(_load(application_id))


@router.put("/{application_id}/doc-context")
def set_doc_context(application_id: int, body: DocContextRequest) -> dict[str, Any]:
    """근로유형 등을 저장하고, 바뀐 체크리스트를 바로 돌려준다."""
    candidate = _load(application_id)
    if generic.is_generic(candidate.program_code):
        if candidate.status != "draft":
            raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
        return generic.checklist_response(candidate)
    if body.work_category:
        try:
            WorkCategory(body.work_category)
        except ValueError:
            raise HTTPException(400, f"알 수 없는 근로유형: {body.work_category}") from None

    with get_session() as s:
        app = s.get(Application, application_id)
        if app is None:
            raise HTTPException(404, "신청 건을 찾을 수 없습니다.")
        from ..models import STATUS_DRAFT
        if app.status != STATUS_DRAFT:
            raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
        criteria = read_criteria(for_application(app))
        for form_no, enabled in body.paper_forms.items():
            if form_no not in criteria["paper_forms"] or not isinstance(enabled, bool):
                raise HTTPException(400, "스캔본 제출 서식 설정이 올바르지 않습니다.")
            if enabled and not criteria["paper_forms"][form_no]:
                raise HTTPException(400, "이 서식은 스캔본 제출을 허용하지 않습니다.")
        old = app.doc_context_json or {}
        new_context = body.model_dump()
        if old.get("applicant_flow_version") == 1:
            new_context["applicant_flow_version"] = 1
        # Partial client updates preserve other independent choices.
        if not body.paper_forms:
            new_context["paper_forms"] = old.get("paper_forms", {})
        from engine_v2.pipeline.privacy import mask_data
        app.doc_context_json = mask_data(new_context)
        app.updated_at = datetime.now()
        s.add(app)
        s.commit()
        s.refresh(app)
        return _checklist_response(app)


def _safe_name(name: str) -> str:
    cleaned = _UNSAFE.sub("_", Path(name).name).strip()
    return cleaned or "upload"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, "발급일은 YYYY-MM-DD 형식으로 입력해 주세요.") from None


def _ocr_json(ocr: OcrResult) -> dict[str, Any]:
    return mask_data({
        "detected_doc_type": str(ocr.detected_doc_type) if ocr.detected_doc_type else None,
        "confidence": ocr.confidence,
        "image_quality": ocr.image_quality,
        "issue_date": ocr.issue_date.isoformat() if ocr.issue_date else None,
        "fields": dict(ocr.fields),
        "bboxes": ocr.bboxes_as_dict(),
        "is_encrypted": ocr.is_encrypted,
        "is_screen_capture": ocr.is_screen_capture,
        "page_count": ocr.page_count,
        "tier": ocr.tier,
        # 판독 엔진·대체 사유는 담당자 화면(officer.py)만 읽는다. 신청자 응답(document_dict)에는 없다.
        "engine": ocr.engine,
        "fallback_reason": ocr.fallback_reason,
        "quality_note": ocr.quality_note,
        "classification_evidence": ocr.classification_evidence,
        "classification_confidence": ocr.classification_confidence,
        "elapsed_ms": ocr.elapsed_ms,
    })


def _save_row(
    app: Application,
    req: DocRequirement | None,
    slot_key: str,
    path: Path,
    ocr: OcrResult,
    declared: date | None,
    findings: list[dict[str, str]],
    status: str,
    *,
    page_index: int | None = None,
    source_file_path: str | None = None,
    replace_existing: bool = False,
) -> Document:
    row = Document(
        application_id=app.id or 0,
        slot_key=slot_key,
        doc_type=str(ocr.detected_doc_type) if ocr.detected_doc_type else None,
        expected_doc_type=str(req.doc_type) if req else None,
        file_path=str(path.relative_to(STORAGE.parent)),
        file_format=path.suffix.lstrip(".").lower(),
        declared_issue_date=declared,
        ocr_json=_ocr_json(ocr),
        stage1_status=status,
        findings_json=mask_data(findings),
        page_index=page_index,
        source_file_path=source_file_path,
    )
    with get_session() as s:
        if generic.is_generic(app.program_code):
            current = s.get(Application, app.id)
            if current is None or current.status != "draft":
                raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
            if replace_existing:
                for previous in s.exec(select(Document).where(
                        Document.application_id == app.id, Document.slot_key == slot_key)).all():
                    s.delete(previous)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def _refresh_nhis_identity(application_id: int, app: Application, checklist: list[DocRequirement]) -> None:
    """건강보험 납부·자격확인서는 짝 서류가 도착할 때마다 함께 다시 대조한다."""
    all_rows = _list_documents(application_id)
    for row, result in assess_nhis_identity(identity_of(app.identity_json), checklist, all_rows):
        with get_session() as session:
            saved = session.get(Document, row.id)
            if saved is not None:
                saved.stage1_status = result.status
                saved.findings_json = mask_data([finding.as_dict() for finding in result.findings])
                session.add(saved)
                session.commit()


def _replace_existing(application_id: int, slot_key: str) -> None:
    """같은 슬롯에 다시 올리면 이전 것을 지운다. 재업로드가 기본 동선이다."""
    with get_session() as s:
        for old in s.exec(
            select(Document)
            .where(Document.application_id == application_id)
            .where(Document.slot_key == slot_key)
        ).all():
            s.delete(old)
        s.commit()


@router.post("/{application_id}/documents")
async def upload_document(
    application_id: int,
    file: UploadFile = File(...),
    slot_key: str = Form(""),
    declared_issue_date: str | None = Form(None),
) -> dict[str, Any]:
    """파일 1개를 받아 즉시 1단계 판정을 돌려준다 (R2.1).

    명시적인 업로드 슬롯이 필요하다. 검증되지 않은 병합 자동 분류는
    정식 OCR·품질 판정을 우회하므로 파일 처리 전에 거부한다.
    """
    if not slot_key or slot_key == AUTO_SLOT:
        raise HTTPException(
            400,
            "자동 서류 분류 업로드는 현재 지원하지 않습니다. "
            "서류 종류에 맞는 업로드 항목을 선택해 다시 제출해 주세요.",
        )
    app = _load(application_id)
    checklist = _checklist(app)
    req = find_slot(checklist, slot_key)
    # bank_account is displayed as fulfilled in the checklist, but has its own
    # validated attachment flow. No other non-upload slot is accepted.
    if req is None or (not req.upload and slot_key != "bank_account"):
        raise HTTPException(400, f"업로드 대상이 아닌 슬롯입니다: {slot_key}")
    if generic.is_generic(app.program_code):
        if app.status != "draft":
            raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
        data = await file.read(20 * 1024 * 1024 + 1)
        if not data or len(data) > 20 * 1024 * 1024:
            raise HTTPException(400, "서류는 내용이 있는 20MB 이하 파일로 올려 주세요.")
        await file.seek(0)

    suffix = Path(file.filename or "").suffix.lstrip(".").lower()
    if suffix not in ACCEPTED_FORMATS:
        raise HTTPException(
            400,
            f"pdf, jpg, png 파일만 올릴 수 있습니다. (올리신 형식: {suffix or '알 수 없음'})",
        )

    if slot_key == "bank_account":
        return await _upload_bankbook(app, file)

    declared = _parse_date(declared_issue_date)
    dest_dir = DOCUMENTS / app.application_no / req.slot_key
    if generic.is_generic(app.program_code):
        dest_dir = dest_dir / uuid4().hex
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / _safe_name(file.filename or "upload")
    path.write_bytes(await file.read())

    def receipt_amount_loader() -> int | None:
        parts = req.slot_key.split("_")
        try:
            item_type, index = parts[0], int(parts[1])
        except (IndexError, ValueError):
            item_type, index = "", 0
        with get_session() as session:
            item = session.exec(select(SubsidyItem)
                                .where(SubsidyItem.application_id == application_id)
                                .where(SubsidyItem.item_type == item_type)
                                .where(SubsidyItem.count_index == index)).first()
        return item.receipt_amount if item is not None else None

    ocr, result = assess_upload(
        path, req,
        identity=identity_of(app.identity_json),
        declared=declared,
        checklist=checklist,
        uploaded_loader=lambda: _list_documents(application_id),
        paper_admin_consent=bool(((app.doc_context_json or {}).get("paper_forms") or {}).get("서식5")),
        receipt_amount_loader=receipt_amount_loader,
        reader=read_document,
    )

    if not generic.is_generic(app.program_code):
        _replace_existing(application_id, req.slot_key)
    row = _save_row(
        app,
        req,
        req.slot_key,
        path,
        ocr,
        declared,
        [f.as_dict() for f in result.findings],
        result.status,
        replace_existing=generic.is_generic(app.program_code),
    )
    if req.doc_type in (DocType.NHIS_PAYMENT, DocType.NHIS_QUALIFICATION) or ocr.detected_doc_type in (
        DocType.NHIS_PAYMENT, DocType.NHIS_QUALIFICATION,
    ):
        _refresh_nhis_identity(application_id, app, checklist)
        row = next((d for d in _list_documents(application_id) if d.id == row.id), row)
    return _document_dict(row)


async def _upload_bankbook(app: Application, file: UploadFile) -> dict[str, Any]:
    """Bankbook copy uses the document store and inline viewer, without OCR claims."""
    from ..models import STATUS_DRAFT

    if app.status != STATUS_DRAFT:
        raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
    data = await file.read(20 * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(400, "파일 내용이 비어 있습니다. 통장 사본을 다시 선택해 주세요.")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(400, "통장 사본은 20MB 이하로 올려 주세요.")
    suffix = Path(file.filename or "").suffix.lstrip(".").lower()
    actual = ("pdf" if data.startswith(b"%PDF-") else "png" if data.startswith(b"\x89PNG\r\n\x1a\n")
              else "jpg" if data.startswith(b"\xff\xd8\xff") else None)
    if actual is None or (suffix if suffix != "jpeg" else "jpg") != actual:
        raise HTTPException(400, "통장 사본은 정상적인 PDF·JPG·PNG 파일만 올릴 수 있습니다.")
    try:
        with pymupdf.open(stream=data, filetype=actual) as document:
            if document.needs_pass:
                raise HTTPException(400, "암호가 걸린 PDF입니다. 암호를 해제한 통장 사본을 올려 주세요.")
            if document.page_count < 1:
                raise ValueError("empty")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "통장 사본 파일을 열 수 없습니다. 다시 저장한 파일을 올려 주세요.") from None
    dest_dir = DOCUMENTS / app.application_no / "bank_account" / uuid4().hex
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / _safe_name(file.filename or f"bankbook.{actual}")
    path.write_bytes(data)
    committed = False
    try:
        with get_session() as session:
            saved = session.get(Application, app.id)
            if saved is None:
                raise HTTPException(404, "신청 건을 찾을 수 없습니다.")
            if saved.status != STATUS_DRAFT:
                raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
            for previous in session.exec(select(Document).where(
                    Document.application_id == app.id, Document.slot_key == "bank_account")).all():
                session.delete(previous)
            row = Document(application_id=app.id or 0, slot_key="bank_account", doc_type="통장사본",
                           file_path=str(path.relative_to(STORAGE.parent)), file_format=suffix,
                           stage1_status="NEEDS_REVIEW", ocr_json={}, findings_json=[{
                               "code": "ACCOUNT_COPY_REVIEW", "severity": "NEEDS_REVIEW",
                               "message": "예금주와 계좌번호는 담당자가 통장 사본 원본으로 확인합니다.",
                               "how_to_fix": "예금주와 계좌번호가 보이는 본인 명의 통장 사본을 첨부해 주세요.",
                               "link": ""}])
            saved.form1_json = {**(saved.form1_json or {}), "bankbookFileName": path.name}
            saved.doc_context_json = {**(saved.doc_context_json or {}), "applicant_flow_version": 1}
            saved.updated_at = datetime.now()
            session.add(saved)
            session.add(row)
            session.commit()
            committed = True
            session.refresh(row)
            return _document_dict(row)
    except Exception:
        if not committed:
            path.unlink(missing_ok=True)
            dest_dir.rmdir()
        raise


async def _upload_merged(
    app: Application, checklist: list[DocRequirement], file: UploadFile
) -> dict[str, Any]:
    """병합 PDF를 페이지 단위로 쪼개 슬롯에 자동 배정한다 (R3.5).

    공고문은 "1개의 파일로 압축하여 올려야 함"을 요구한다. 기존 방식대로 합쳐
    올린 신청자도 그대로 받되, 페이지별 판별 결과로 슬롯을 채운다. 배정되지 않은
    페이지만 신청자에게 되묻는다.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "여러 서류를 한 파일로 올리는 기능은 pdf만 지원합니다.")

    base = DOCUMENTS / app.application_no / "_merged"
    if generic.is_generic(app.program_code):
        base = base / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    source = base / _safe_name(file.filename or "merged.pdf")
    source.write_bytes(await file.read())

    pages = split_pdf_pages(str(source), base, source.stem)
    if not pages:
        # 암호 PDF 등으로 쪼개지 못한 경우. 판독을 돌려 사유를 그대로 보여준다.
        ocr = read_document(str(source), None)
        placeholder = DocRequirement(
            slot_key=UNASSIGNED_SLOT,
            doc_type=DocType.RESIDENT_ABSTRACT,
            label="병합 업로드 파일",
            check_declared_date=False,
        )
        result = check_document(placeholder, ocr, None, "pdf")
        row = _save_row(
            app,
            None,
            UNASSIGNED_SLOT,
            source,
            ocr,
            None,
            [f.as_dict() for f in result.findings],
            result.status,
        )
        return {
            "mode": "merged",
            "source_file": source.name,
            "page_count": 0,
            "assigned": [],
            "unassigned": [_document_dict(row)],
        }

    taken = {d.slot_key for d in _list_documents(app.id or 0)}
    assigned: list[dict[str, Any]] = []
    unassigned: list[dict[str, Any]] = []
    rel_source = str(source.relative_to(STORAGE.parent))

    for index, page_path, ocr in pages:
        req = None
        if ocr.detected_doc_type is not None:
            for candidate in checklist:
                if (
                    candidate.upload
                    and candidate.accepts(ocr.detected_doc_type)
                    and candidate.slot_key not in taken
                ):
                    req = candidate
                    break

        if req is None:
            row = _save_row(
                app,
                None,
                UNASSIGNED_SLOT,
                page_path,
                ocr,
                None,
                [],
                "NEEDS_REVIEW",
                page_index=index,
                source_file_path=rel_source,
            )
            unassigned.append(_document_dict(row))
            continue

        taken.add(req.slot_key)
        if req.doc_type == DocType.UNKNOWN:
            result = CheckResult('NEEDS_REVIEW', [CheckFinding(
                code='MANUAL_DOCUMENT_REVIEW', message='담당자가 제출 서류의 원본과 사업 기준을 확인합니다.',
                severity='NEEDS_REVIEW')])
        else:
            result = check_document(req, ocr, None, "pdf", identity_of(app.identity_json))
        if not generic.is_generic(app.program_code):
            _replace_existing(app.id or 0, req.slot_key)
        row = _save_row(
            app,
            req,
            req.slot_key,
            page_path,
            ocr,
            None,
            [f.as_dict() for f in result.findings],
            result.status,
            page_index=index,
            source_file_path=rel_source,
            replace_existing=generic.is_generic(app.program_code),
        )
        assigned.append(_document_dict(row))

    if any(doc["slot_key"] in {"nhis_payment", "nhis_qualification"} for doc in assigned):
        _refresh_nhis_identity(app.id or 0, app, checklist)
        refreshed = {d.id: d for d in _list_documents(app.id or 0)}
        assigned = [
            _document_dict(refreshed[doc["document_id"]])
            if doc["document_id"] in refreshed else doc
            for doc in assigned
        ]

    return {
        "mode": "merged",
        "source_file": source.name,
        "page_count": len(pages),
        "assigned": assigned,
        "unassigned": unassigned,
    }


@router.get("/{application_id}/documents")
def list_documents(application_id: int) -> list[dict[str, Any]]:
    _load(application_id)
    return [_document_dict(d) for d in _list_documents(application_id)]


@router.delete("/{application_id}/documents/{document_id}")
def delete_document(application_id: int, document_id: int) -> dict[str, str]:
    """재업로드를 위한 삭제. 파일도 같이 지운다."""
    app = _load(application_id)
    if generic.is_generic(app.program_code) and app.status != "draft":
        raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
    checklist = _checklist(app)
    nhis_types = {str(DocType.NHIS_PAYMENT), str(DocType.NHIS_QUALIFICATION)}
    refresh_nhis = False
    with get_session() as s:
        row = s.get(Document, document_id)
        if row is None or row.application_id != application_id:
            raise HTTPException(404, "서류를 찾을 수 없습니다.")
        refresh_nhis = row.doc_type in nhis_types or row.expected_doc_type in nhis_types
        if row.slot_key == "bank_account":
            from ..models import STATUS_DRAFT

            saved = s.get(Application, application_id)
            if saved is None or saved.status != STATUS_DRAFT:
                raise HTTPException(409, "제출한 신청서는 수정할 수 없습니다.")
            values = dict(saved.form1_json or {})
            values.pop("bankbookFileName", None)
            saved.form1_json = values
            saved.doc_context_json = {**(saved.doc_context_json or {}), "applicant_flow_version": 1}
            saved.updated_at = datetime.now()
            s.add(saved)
        target = STORAGE.parent / row.file_path
        target.unlink(missing_ok=True)
        s.delete(row)
        s.commit()
    if refresh_nhis:
        _refresh_nhis_identity(application_id, app, checklist)
    return {"deleted": str(document_id)}
