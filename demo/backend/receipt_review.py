"""Youth payment receipts are evidence for an officer, not OCR inputs."""
from pathlib import Path

from fastapi import HTTPException
import pymupdf

from .rules.doc_types import DocType

RECEIPT_REVIEW_CODE = "RECEIPT_MANUAL_REVIEW"
RECEIPT_REVIEW_MESSAGE = "결제영수증은 담당자 확인 대상입니다. 담당자가 원본과 신청 금액을 직접 확인합니다."
RECEIPT_REVIEW_TIER = "manual_receipt"


def is_receipt(requirement) -> bool:
    """Use the checklist's canonical type, never the filename or slot suffix."""
    return requirement.doc_type == DocType.PAYMENT_RECEIPT


def validate_original(path: Path) -> None:
    """Check only the file envelope so an officer can open the original.

    No text/OCR, document classification, image-quality or confidence evaluation.
    Invalid files are HTTP errors, never automatic document FAIL results.
    """
    kind = path.suffix.lstrip('.').lower()
    try:
        with path.open('rb') as source:
            prefix = source.read(8)
        actual = ('pdf' if prefix.startswith(b'%PDF-') else
                  'png' if prefix.startswith(b'\x89PNG\r\n\x1a\n') else
                  'jpg' if prefix.startswith(b'\xff\xd8\xff') else None)
        if actual is None or actual != ('jpg' if kind == 'jpeg' else kind):
            raise ValueError('wrong file envelope')
        with pymupdf.open(path) as original:
            if original.needs_pass or original.page_count < 1 or (actual == 'pdf') != original.is_pdf:
                raise ValueError('unviewable file')
            for page in original:
                if page.rect.is_empty or page.rect.is_infinite:
                    raise ValueError('unviewable page')
    except Exception as error:
        raise HTTPException(400, "영수증 원본은 암호가 없는 정상적인 PDF·JPG·PNG 파일로 올려 주세요.") from error


def assessment():
    from .ocr.base import OcrResult
    from .rules.doc_check import CheckFinding, CheckResult

    return OcrResult(tier=RECEIPT_REVIEW_TIER), CheckResult("NEEDS_REVIEW", [CheckFinding(
        code=RECEIPT_REVIEW_CODE, message=RECEIPT_REVIEW_MESSAGE,
        severity="NEEDS_REVIEW",
    )])
