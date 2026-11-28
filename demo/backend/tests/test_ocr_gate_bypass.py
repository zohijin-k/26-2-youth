"""11-28 (youth): 자동 판독이 없는 칸의 업로드는 판독 차례(ocr_gate)를 기다리지 않는다 (가상 문서만).

결제영수증 원본은 수동 검토이고(receipt_review) 담당자 정의 서류(DocType.UNKNOWN)는 판독기가 없다. 둘 다 파일 확인만
하므로, 다른 신청자의 판독이 길어지거나 대기열이 가득해도 바로 저장되어야 한다. 판독이 필요한 칸은 그대로 차례를 탄다.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from demo.backend import ocr_gate, upload_assessment
from demo.backend.api import documents
from demo.backend.receipt_review import RECEIPT_REVIEW_CODE
from demo.backend.rules.doc_types import DocType
from demo.backend.rules.programs import JOB_PACKAGE, PROGRAMS
from demo.backend.rules.required_docs import ApplicantDocInput, DocRequirement, WorkCategory, build_checklist
from demo.backend.tests import run_p5_scenarios as job
from demo.backend.tests.test_generic_programs import pdf
from demo.backend.tests.test_ocr_gate import Reader, _pdf, _post, _rows, fresh_gate  # noqa: F401 - fixture
from demo.backend.tests.test_portal_uploads import client, new_app  # noqa: F401 - fixture
from demo.backend.tests.test_receipt_manual_review import attachment, new_job, receipt_document


def test_receipt_upload_does_not_wait_for_another_applicants_read_or_a_full_queue(client, monkeypatch):
    monkeypatch.setattr(ocr_gate, "MAX_WAITING_READS", 0)          # 판독 중이면 판독 업로드는 바로 503
    reader = Reader(hold=True)
    monkeypatch.setattr(documents, "read_document", reader)
    scanning = new_app(client)
    receipts = new_job(client, job.S10_SELECTION)
    with ThreadPoolExecutor(1) as pool:
        held = pool.submit(_post, client, scanning, _pdf("SYNTHETIC SCAN"))
        try:
            assert reader.entered.wait(5)
            started = time.monotonic()
            response = attachment(client, receipts, "suit_1_receipt")
            elapsed = time.monotonic() - started
            busy = _post(client, new_app(client), _pdf("SYNTHETIC OTHER"))
            still_reading = not held.done()
        finally:
            reader.release.set()
        assert held.result(timeout=10).status_code == 200
    assert response.status_code == 200, response.text
    assert still_reading and elapsed < 2                           # 남의 판독이 끝나기 전에 저장됐다
    assert busy.status_code == 503                                 # 판독이 필요한 업로드는 여전히 대기열 규칙을 따른다
    saved = receipt_document(receipts)
    assert saved.stage1_status == "NEEDS_REVIEW" and [f["code"] for f in saved.findings_json] == [RECEIPT_REVIEW_CODE]
    assert len(reader.calls) == 1                                  # 영수증은 판독기에 가지 않았다


def test_routing_matches_what_the_assessment_actually_reads(tmp_path):
    """`reads_document`가 False인 칸은 assess_upload가 판독기를 부르지 않고, True인 칸은 부른다(조건이 어긋나면 실패)."""
    path = tmp_path / "FAKE.pdf"
    path.write_bytes(pdf())
    checklist = build_checklist(PROGRAMS[JOB_PACKAGE], ApplicantDocInput(work_category=WorkCategory.EMPLOYEE))
    requirements = [r for r in checklist if r.upload] + [
        DocRequirement(slot_key="suit_1_receipt", doc_type=DocType.PAYMENT_RECEIPT, label="가상 영수증"),
        DocRequirement(slot_key="custom_1", doc_type=DocType.UNKNOWN, label="가상 담당자 정의 서류"),
    ]
    assert {upload_assessment.reads_document(r) for r in requirements} == {True, False}

    class Called(Exception):
        pass

    def reader(file_path, expected=None):
        raise Called()
    for requirement in requirements:
        if upload_assessment.reads_document(requirement):
            with pytest.raises(Called):
                upload_assessment.assess_upload(path, requirement, checklist=checklist, reader=reader)
        else:
            upload_assessment.assess_upload(path, requirement, checklist=checklist, reader=reader)   # 판독기 호출 없음


def test_a_reading_slot_can_never_take_the_bypass(client, monkeypatch):
    """우회 경로에 판독이 필요한 칸이 들어오면(조건이 어긋난 경우) 대기열 밖에서 읽지 않고 오류로 드러난다."""
    monkeypatch.setattr(documents, "reads_document", lambda req: False)
    reader = Reader()
    monkeypatch.setattr(documents, "read_document", reader)
    aid = new_app(client)
    with pytest.raises(RuntimeError, match="routed around the OCR gate"):
        _post(client, aid, _pdf("SYNTHETIC"))
    assert reader.calls == [] and _rows(aid) == []


def test_no_read_upload_is_never_run_inside_a_writer_reservation_even_for_inline_tools(client):
    """판독 없는 칸은 요청 스레드풀에서 확인한다: 쓰기 예약 연결을 다른 스레드로 넘기지 않도록 예약 안에서는 거절한다."""
    import asyncio
    import io

    from starlette.datastructures import UploadFile

    from demo.backend import models

    receipts = new_job(client, job.S10_SELECTION)
    with models.session_transaction():
        with ocr_gate.inline_reads():
            upload = UploadFile(io.BytesIO(pdf()), filename="SYNTHETIC-receipt.pdf")
            with pytest.raises(RuntimeError, match="writer reservation"):
                asyncio.run(documents.upload_document(receipts, upload, "suit_1_receipt", None))
    assert _rows(receipts) == []
