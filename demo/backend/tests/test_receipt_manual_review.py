"""Synthetic receipt originals, explicit slots, submission and existing CAS audit."""
from contextlib import closing
from copy import deepcopy
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pymupdf
import pytest
from sqlmodel import select

from demo.backend import models, upload_assessment
from demo.backend.api import common, documents, forms, review
from demo.backend.main import app
from demo.backend.ocr.base import OcrResult
from demo.backend.receipt_review import RECEIPT_REVIEW_CODE, RECEIPT_REVIEW_TIER
from demo.backend.rules.doc_check import CheckResult
from demo.backend.rules.doc_types import DocType
from demo.backend.rules.required_docs import DocRequirement
from demo.backend.tests import run_p5_scenarios as job
from demo.backend.tests.test_generic_programs import pdf
from demo.backend.tests.test_portal_uploads import client
from demo.backend.tests.test_submitted_document_immutability import snapshot


def forbidden(*args, **kwargs):
    raise AssertionError("A manual receipt reached automatic assessment")


def image_bytes(kind="png"):
    data = io.BytesIO()
    Image.new("RGB", (320, 240), "white").save(data, format="JPEG" if kind == "jpg" else "PNG")
    return data.getvalue()


def attachment(client, aid, slot, content=None, filename="SYNTHETIC-receipt.pdf"):
    return client.post(f"/api/applications/{aid}/documents", data={"slot_key": slot},
                       files={"file": (filename, pdf() if content is None else content,
                                       "application/octet-stream")})


def new_job(client, selections=None):
    response = client.post("/api/applications", json={"program_code": "job_package"})
    assert response.status_code == 200, response.text
    aid = response.json()["id"]
    if selections is not None:
        response = client.post(f"/api/applications/{aid}/subsidy-items", json={"items": selections})
        assert response.status_code == 200, response.text
    return aid


def receipt_document(aid, slot="suit_1_receipt"):
    with models.get_session() as session:
        return session.exec(select(models.Document).where(
            models.Document.application_id == aid, models.Document.slot_key == slot)).one()


def prepare_submission(client, monkeypatch, tmp_path):
    """Authored fixture evidence, real API flow and real automatic review pipeline."""
    samples = tmp_path / "authored-samples"
    samples.mkdir(exist_ok=True)
    for filename in job.S10_UPLOADS.values():
        (samples / filename).write_bytes(pdf())
    monkeypatch.setattr(job, "SAMPLES", samples)
    monkeypatch.setattr(forms, "STORAGE", common.STORAGE)
    return job.create_job_application(client, selections=job.S10_SELECTION, uploads=job.S10_UPLOADS)


def review_state(aid):
    with models.get_session() as session:
        saved = session.exec(select(models.Review).where(models.Review.application_id == aid)).one()
        application = session.get(models.Application, aid)
        return saved.model_dump(), application.model_dump()


@pytest.mark.parametrize("kind", ["pdf", "png", "jpg"])
@pytest.mark.parametrize("slot", ["suit_1_receipt", "photo_1_receipt", "certificate_2_receipt", "arbitrary"])
def test_canonical_receipt_bypasses_every_automatic_callback(kind, slot, tmp_path, monkeypatch):
    path = tmp_path / f"misleading-resident-document.{kind}"
    content = pdf() if kind == "pdf" else image_bytes(kind)
    path.write_bytes(content)
    monkeypatch.setattr(upload_assessment, "check_document", forbidden)
    original, result = upload_assessment.assess_upload(
        path, DocRequirement(slot, DocType.PAYMENT_RECEIPT, "합성 영수증"),
        reader=forbidden, identity_from_ocr=forbidden, uploaded_loader=forbidden,
        receipt_amount_loader=forbidden, receipt_amount=999999,
    )
    assert result.status == "NEEDS_REVIEW"
    assert result.codes == [RECEIPT_REVIEW_CODE]
    assert all(finding.severity == "NEEDS_REVIEW" for finding in result.findings)
    assert original.tier == RECEIPT_REVIEW_TIER
    assert original.detected_doc_type is None and original.fields == {} and original.bboxes == {}
    assert path.read_bytes() == content


def test_nonreceipt_with_receipt_suffix_still_uses_existing_reader(tmp_path, monkeypatch):
    path = tmp_path / "receipt.pdf"
    path.write_bytes(pdf())
    calls = []
    read = OcrResult(DocType.INTERVIEW_CONFIRMATION, .99, tier="synthetic")
    def reader(filename, expected):
        calls.append((filename, expected))
        return read
    monkeypatch.setattr(upload_assessment, "check_document", lambda *args, **kwargs: CheckResult("PASS", []))
    result, _ = upload_assessment.assess_upload(path, DocRequirement(
        "interview_1_receipt", DocType.INTERVIEW_CONFIRMATION, "합성 면접확인서"), reader=reader)
    assert result is read
    assert calls == [(str(path), DocType.INTERVIEW_CONFIRMATION)]


@pytest.mark.parametrize("item,count,slots", [
    ("suit", 2, ["suit_1_receipt", "suit_2_receipt"]),
    ("photo", 1, ["photo_1_receipt"]),
    ("certificate", 2, ["certificate_1_receipt", "certificate_2_receipt"]),
])
def test_actual_selected_receipt_slots_keep_originals_without_ocr(client, monkeypatch, item, count, slots):
    aid = new_job(client, [{"item_type": item, "count": count, "receipts": [10000] * count}])
    monkeypatch.setattr(documents, "read_document", forbidden)
    with models.get_session() as session:
        application = session.get(models.Application, aid)
        requirements = common.checklist_for(application)
    assert [req.slot_key for req in requirements if req.doc_type == DocType.PAYMENT_RECEIPT] == slots
    for index, slot in enumerate(slots):
        kind = "pdf" if index == 0 else "png"
        content = pdf() if kind == "pdf" else image_bytes()
        response = attachment(client, aid, slot, content, f"arbitrary-name.{kind}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "NEEDS_REVIEW" and body["detected_doc_type"] is None
        assert body["extracted"] == {} and [f["code"] for f in body["findings"]] == [RECEIPT_REVIEW_CODE]
        row = receipt_document(aid, slot)
        assert row.ocr_json == {"tier": RECEIPT_REVIEW_TIER, "fields": {}, "bboxes": {}}
        assert client.get(body["file_url"]).content == content
        assert (common.STORAGE.parent / row.file_path).read_bytes() == content
    check = client.get(f"/api/applications/{aid}/final-check").json()
    assert not any(blocker["target"] in slots for blocker in check["blockers"])


def test_interview_selection_has_no_receipt_slot(client):
    aid = new_job(client, [{"item_type": "interview", "count": 2, "receipts": []}])
    with models.get_session() as session:
        application = session.get(models.Application, aid)
        assert not any(req.doc_type == DocType.PAYMENT_RECEIPT for req in common.checklist_for(application))
    assert attachment(client, aid, "interview_1_receipt").status_code == 400


@pytest.mark.parametrize("kind", ["pdf", "png", "jpg"])
def test_owner_and_officer_can_stream_receipt_original_pdf_and_images(client, monkeypatch, kind):
    aid = new_job(client, [{"item_type": "photo", "count": 1, "receipts": [10000]}])
    monkeypatch.setattr(documents, "read_document", forbidden)
    content = pdf() if kind == "pdf" else image_bytes(kind)
    uploaded = attachment(client, aid, "photo_1_receipt", content, f"original.{kind}")
    assert uploaded.status_code == 200, uploaded.text
    url = uploaded.json()["file_url"]
    for allowed_cookie in (f"applicant_access_{aid}", "officer_session"):
        with closing(TestClient(app)) as allowed:
            for cookie in client.cookies.jar:
                if cookie.name == allowed_cookie:
                    allowed.cookies.set(cookie.name, cookie.value, path=cookie.path)
            streamed = allowed.get(url)
            assert streamed.status_code == 200 and streamed.content == content
            assert streamed.headers["content-disposition"].startswith("inline")
            assert streamed.headers["content-type"].startswith({
                "pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg"}[kind])


@pytest.mark.parametrize("kind", ["empty", "malformed", "extension-mismatch", "encrypted", "unsupported"])
def test_invalid_receipt_request_preserves_previous_row_bytes_and_entire_database(client, monkeypatch, kind):
    aid = new_job(client, [{"item_type": "photo", "count": 1, "receipts": [10000]}])
    assert attachment(client, aid, "photo_1_receipt").status_code == 200
    before = snapshot()
    filename = "replacement.pdf"
    content = {"empty": b"", "malformed": b"%PDF-garbage", "extension-mismatch": image_bytes(),
               "unsupported": b"not an attachment"}.get(kind, b"")
    if kind == "unsupported":
        filename = "replacement.txt"
    if kind == "encrypted":
        with pymupdf.open(stream=pdf(), filetype="pdf") as source:
            content = source.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="synthetic-password")
    monkeypatch.setattr(documents, "read_document", forbidden)
    response = attachment(client, aid, "photo_1_receipt", content, filename)
    assert response.status_code == 400, response.text
    assert snapshot() == before


def test_failed_manual_receipt_replacement_preserves_previous_evidence(client, monkeypatch):
    aid = new_job(client, [{"item_type": "photo", "count": 1, "receipts": [10000]}])
    assert attachment(client, aid, "photo_1_receipt").status_code == 200
    before = snapshot()
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic persistence failure")
    monkeypatch.setattr(documents, "_save_row", fail)
    with closing(TestClient(app, raise_server_exceptions=False)) as requester:
        requester.cookies.update(client.cookies)
        assert attachment(requester, aid, "photo_1_receipt", pdf(True)).status_code == 500
    assert snapshot() == before


@pytest.mark.parametrize("slot", ["auto", "", "unassigned", "suit_99_receipt", "unknown_receipt"])
def test_invalid_or_automatic_slot_is_rejected_before_processing(client, monkeypatch, slot):
    aid = new_job(client, [{"item_type": "suit", "count": 1, "receipts": [10000]}])
    before = snapshot()
    monkeypatch.setattr(documents, "assess_upload", forbidden)
    assert attachment(client, aid, slot).status_code == 400
    assert snapshot() == before


def test_mixed_pdf_receipt_slot_does_not_fill_other_slot_and_other_slot_still_uses_ocr(client, monkeypatch):
    aid = new_job(client, [{"item_type": "suit", "count": 1, "receipts": [10000]}])
    with pymupdf.open(stream=pdf(), filetype="pdf") as mixed:
        page = mixed.new_page()
        page.insert_text((40, 40), "SYNTHETIC INTERVIEW CONFIRMATION WITH RECEIPT")
        content = mixed.tobytes()
    monkeypatch.setattr(documents, "read_document", forbidden)
    receipt = attachment(client, aid, "suit_1_receipt", content)
    assert receipt.status_code == 200, receipt.text
    check = client.get(f"/api/applications/{aid}/final-check").json()
    missing = {blocker["target"] for blocker in check["blockers"]}
    assert "interview_1_confirmation" in missing and "suit_1_receipt" not in missing
    calls = []
    def reader(filename, expected):
        calls.append((Path(filename).read_bytes(), expected))
        return OcrResult(DocType.INTERVIEW_CONFIRMATION, .4, tier="synthetic", fields={})
    monkeypatch.setattr(documents, "read_document", reader)
    other = attachment(client, aid, "interview_1_confirmation", content)
    assert other.status_code == 200, other.text
    assert calls == [(content, DocType.INTERVIEW_CONFIRMATION)]
    assert other.json()["document_id"] != receipt.json()["document_id"]


def test_required_receipt_absence_and_dangling_original_block_submission(client, monkeypatch, tmp_path):
    aid = prepare_submission(client, monkeypatch, tmp_path)
    row = receipt_document(aid)
    path = common.STORAGE.parent / row.file_path
    path.unlink()
    assert client.get(f"/api/files/{row.id}").status_code == 404
    check = client.get(f"/api/applications/{aid}/final-check").json()
    assert not check["can_submit"] and any(x["target"] == row.slot_key for x in check["blockers"])
    assert client.post(f"/api/applications/{aid}/submit").status_code == 400
    with models.get_session() as session:
        assert session.exec(select(models.Review).where(models.Review.application_id == aid)).first() is None
    path.write_bytes(pdf())
    assert client.delete(f"/api/applications/{aid}/documents/{row.id}").status_code == 200
    check = client.get(f"/api/applications/{aid}/final-check").json()
    assert any(x["target"] == row.slot_key for x in check["blockers"])
    assert client.post(f"/api/applications/{aid}/submit").status_code == 400


def test_receipt_lifecycle_preserves_auth_originals_and_existing_cas_decision_audit(client, monkeypatch, tmp_path):
    aid = prepare_submission(client, monkeypatch, tmp_path)
    receipt = receipt_document(aid)
    original_path = common.STORAGE.parent / receipt.file_path
    original = original_path.read_bytes()
    seen = []
    real_pipeline = review.run_pipeline
    def pipeline(applicant, inputs, requirements):
        assert not any(req.doc_type == DocType.PAYMENT_RECEIPT for req in requirements)
        assert not any(doc.doc_type == str(DocType.PAYMENT_RECEIPT) for doc in inputs)
        seen.append([req.slot_key for req in requirements])
        return real_pipeline(applicant, inputs, requirements)
    monkeypatch.setattr(review, "run_pipeline", pipeline)
    final_check = client.get(f"/api/applications/{aid}/final-check").json()
    assert final_check["can_submit"]
    assert any("결제영수증" in warning and "담당자 확인 대상" in warning
               for warning in final_check["warnings"])
    assert not any("더 선명한 파일" in warning for warning in final_check["warnings"])
    response = client.post(f"/api/applications/{aid}/submit")
    assert response.status_code == 200, response.text
    assert seen
    saved, _ = review_state(aid)
    assert saved["final_status"] == saved["stage1_status"] == "NEEDS_REVIEW"
    assert saved["supplement_deadline"] is None  # Routine manual review is not a deficiency.
    payload = saved["review_payload_json"]
    manual = next(row for row in payload["documents"] if row["document_id"] == receipt.id)
    assert manual["status"] == "NEEDS_REVIEW" and manual["ocr_confidence"] is None
    assert manual["file_ref"] == f"/api/files/{receipt.id}"
    assert any(reason["code"] == RECEIPT_REVIEW_CODE for reason in payload["reasons"])
    with closing(TestClient(app)) as outsider:
        assert outsider.get(f"/api/files/{receipt.id}").status_code == 403
        assert attachment(outsider, aid, "suit_1_receipt").status_code == 403
        assert outsider.get(f"/api/officer/applications/{aid}").status_code == 401
        wrong_aid = new_job(outsider)
        assert wrong_aid != aid
        assert outsider.get(f"/api/files/{receipt.id}").status_code == 403
    with closing(TestClient(app)) as officer:
        for cookie in client.cookies.jar:
            if cookie.name == "officer_session":
                officer.cookies.set(cookie.name, cookie.value, path=cookie.path)
        detail = officer.get(f"/api/officer/applications/{aid}")
        assert detail.status_code == 200, detail.text
        document = next(d for d in detail.json()["documents"] if d["document_id"] == receipt.id)
        assert document["ocr_tier"] == RECEIPT_REVIEW_TIER and document["ocr_confidence"] is None
        assert document["extracted"] == {} and document["status"] == "NEEDS_REVIEW"
        stream = officer.get(document["file_url"])
        assert stream.status_code == 200 and stream.content == original
        assert stream.headers["content-disposition"].startswith("inline")
        assert stream.headers["cache-control"] == "no-store"
        before = snapshot()
        endpoint = f"/api/officer/applications/{aid}/decision"
        body = {"role": "province", "decision": "hold", "memo": "합성 영수증 원본 확인 기록"}
        assert officer.post(endpoint, json=body).status_code == 428
        assert snapshot() == before
        revision = detail.json()["revision"]
        assert officer.post(endpoint, json={**body, "expected_revision": True}).status_code == 422
        assert snapshot() == before
        result = officer.post(endpoint, json={**body, "expected_revision": revision})
        assert result.status_code == 200, result.text
        assert result.json()["revision"] == revision + 1
        changed, _ = review_state(aid)
        assert changed["officer_memo"] == body["memo"] and changed["officer_decision"] == "hold"
        assert changed["review_payload_json"] == payload
        after = snapshot()
        assert officer.post(endpoint, json={**body, "expected_revision": revision}).status_code == 409
        assert snapshot() == after
    before = snapshot()
    assert attachment(client, aid, "suit_1_receipt").status_code == 409
    assert client.delete(f"/api/applications/{aid}/documents/{receipt.id}").status_code == 409
    assert snapshot() == before and original_path.read_bytes() == original


def test_other_document_fail_is_not_downgraded_by_manual_receipts(client, monkeypatch, tmp_path):
    aid = prepare_submission(client, monkeypatch, tmp_path)
    with models.get_session() as session:
        other = session.exec(select(models.Document).where(
            models.Document.application_id == aid, models.Document.slot_key == "resident_abstract")).one()
        raw = deepcopy(other.ocr_json)
        raw["image_quality"] = .1
        other.ocr_json = raw
        other.stage1_status = "FAIL"
        session.add(other)
        session.commit()
        application = session.get(models.Application, aid)
    current = review._run_review(application)
    assert current.final_status == current.stage1_status == "FAIL"
    assert current.supplement_deadline is not None
    assert any(reason["code"] == RECEIPT_REVIEW_CODE for reason in current.review_payload_json["reasons"])


def test_new_receipt_processing_does_not_rewrite_historical_review_or_document(client, monkeypatch, tmp_path):
    aid = prepare_submission(client, monkeypatch, tmp_path)
    assert client.post(f"/api/applications/{aid}/submit").status_code == 200
    original = review_state(aid)
    historical = receipt_document(aid).model_dump()
    other = new_job(client, [{"item_type": "photo", "count": 1, "receipts": [10000]}])
    assert attachment(client, other, "photo_1_receipt").status_code == 200
    assert review_state(aid) == original
    assert receipt_document(aid).model_dump() == historical
