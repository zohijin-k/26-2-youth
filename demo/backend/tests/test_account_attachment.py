"""Synthetic account attachments restore the complete job-package submission path."""
import base64
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from demo.backend.tests.security_support import authenticate_officer
from sqlmodel import create_engine, select

from demo.backend import models
from demo.backend.api import applications, common, documents, files, forms, postings
from demo.backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = create_engine(f"sqlite:///{tmp_path / 'FAKE-account.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(models, "engine", database)
    storage = tmp_path / "storage"
    for module in (applications, common, documents, files, forms, postings):
        monkeypatch.setattr(module, "STORAGE", storage)
    monkeypatch.setattr(applications, "SIGNATURES", storage / "signatures")
    monkeypatch.setattr(documents, "DOCUMENTS", storage / "documents")
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    try:
        with TestClient(app) as connection:
            authenticate_officer(connection, monkeypatch)
            yield connection
    finally:
        database.dispose()


def fake_pdf():
    with pymupdf.open() as document:
        document.new_page().insert_text((40, 60), "FAKE bank account attachment")
        return document.tobytes()


def identify(client):
    created = client.post("/api/applications", json={"program_code": "job_package"}).json()
    aid = created["id"]
    with pymupdf.open(stream=fake_pdf(), filetype="pdf") as document:
        signature = document[0].get_pixmap().tobytes("png")
    verified = client.post(f"/api/applications/{aid}/identity", json={
        "name": "김청년", "birth": "1999-04-10", "phone": "010-1111-2222", "pledge": True,
        "signature_data_url": "data:image/png;base64," + base64.b64encode(signature).decode(),
    })
    assert verified.status_code == 200, verified.text
    return aid


def upload_bankbook(client, aid, data=None, name="FAKE-bankbook.pdf"):
    return client.post(f"/api/applications/{aid}/documents", data={"slot_key": "bank_account"},
                       files={"file": (name, fake_pdf() if data is None else data, "application/pdf")})


def targets(client, aid):
    response = client.get(f"/api/applications/{aid}/final-check")
    assert response.status_code == 200, response.text
    return {item["target"]: item for item in response.json()["blockers"]}


def test_missing_account_fields_disappear_after_holder_and_real_attachment(client):
    aid = identify(client)
    assert {"accountHolder", "bankbookFileName"} <= targets(client, aid).keys()
    assert client.patch(f"/api/applications/{aid}", json={"form1": {"accountHolder": "김청년"}}).status_code == 200
    response = upload_bankbook(client, aid)
    assert response.status_code == 200, response.text
    uploaded = response.json()
    assert uploaded["slot_key"] == "bank_account"
    assert uploaded["status"] == "NEEDS_REVIEW"
    assert not ({"engine", "fallback_reason", "file_path"} & uploaded.keys())
    assert not ({"accountHolder", "bankbookFileName"} & targets(client, aid).keys())
    preview = client.get(uploaded["file_url"])
    assert preview.status_code == 200
    assert preview.headers["content-disposition"].startswith("inline")
    assert preview.content.startswith(b"%PDF-")
    # An older autosave finishing after upload cannot erase the attached filename.
    patched = client.patch(f"/api/applications/{aid}", json={"form1": {"accountHolder": "김청년"}})
    assert patched.json()["form1_json"]["bankbookFileName"] == "FAKE-bankbook.pdf"


def test_holder_mismatch_blocks_both_final_check_and_submit(client):
    aid = identify(client)
    assert client.patch(f"/api/applications/{aid}", json={"form1": {"accountHolder": "가상타인"}}).status_code == 200
    blocker = targets(client, aid)["accountHolder"]
    assert blocker["code"] == "ACCOUNT_HOLDER_MISMATCH"
    assert "지원금은 본인 명의 계좌로만 지급됩니다" in blocker["message"]
    submitted = client.post(f"/api/applications/{aid}/submit")
    assert submitted.status_code == 400
    assert blocker["message"] in submitted.json()["detail"]


@pytest.mark.parametrize("data,name", [(b"not a PDF", "FAKE.pdf"), (b"", "FAKE.pdf"),
                                        (b"%PDF- broken", "FAKE.pdf"), (b"x", "FAKE.exe"),
                                        (b"x" * (20 * 1024 * 1024 + 1), "FAKE.pdf")])
def test_invalid_bankbook_rejected_without_creating_document(client, data, name):
    aid = identify(client)
    response = upload_bankbook(client, aid, data, name)
    assert response.status_code == 400, response.text
    assert "bankbookFileName" in targets(client, aid)
    with models.get_session() as session:
        assert not session.exec(select(models.Document).where(models.Document.application_id == aid)).all()


def test_encrypted_bankbook_rejected(client):
    aid = identify(client)
    with pymupdf.open(stream=fake_pdf(), filetype="pdf") as document:
        encrypted = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="FAKE-owner", user_pw="FAKE-user")
    response = upload_bankbook(client, aid, encrypted)
    assert response.status_code == 400
    assert "암호" in response.json()["detail"]


def test_job_package_identity_forms_upload_submit_api_journey(client):
    aid = identify(client)
    form = {"address": "전북특별자치도 전주시 완산구 합성동 0", "gender": "여", "mobile": "010-1111-2222",
            "email": "fake@example.test", "bankName": "가상은행", "accountNo": "000-FAKE-000", "accountHolder": "김청년"}
    assert client.patch(f"/api/applications/{aid}", json={"form1": form}).status_code == 200
    assert client.post(f"/api/applications/{aid}/self-check", json={"answers": {"1": "예", "2": "예"}}).json()["eligible"]
    assert client.post(f"/api/applications/{aid}/consents", json={"consents": [
        {"consent_type": "privacy", "agreed": True}, {"consent_type": "third_party", "agreed": True}]}).status_code == 200
    assert upload_bankbook(client, aid).status_code == 200
    assert client.post(f"/api/applications/{aid}/subsidy-items", json={"items": [{"item_type": "interview", "count": 1, "receipts": []}]}).status_code == 200
    samples = Path(__file__).resolve().parents[2] / "fixtures" / "samples"
    for slot, name, declared in [("resident_abstract", "S10_주민등록초본_취업패키지.pdf", "2026-04-07"),
                                  ("interview_1_confirmation", "S10_면접확인서_1회차.pdf", "")]:
        response = client.post(f"/api/applications/{aid}/documents", data={"slot_key": slot, "declared_issue_date": declared},
                               files={"file": (name, (samples / name).read_bytes(), "application/pdf")})
        assert response.status_code == 200, response.text
    final = client.get(f"/api/applications/{aid}/final-check").json()
    assert final["can_submit"], final["blockers"]
    response = client.post(f"/api/applications/{aid}/submit")
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["application_no"].startswith("JP-2026-")
    assert receipt["status"] == "submitted"
    assert receipt["first_come"]["position"] == 1
    assert receipt["subsidy"]["total_granted"] == 50000
    with models.get_session() as session:
        saved = session.get(models.Application, aid)
        assert saved.written_forms_archive_path
        review = session.exec(select(models.Review).where(models.Review.application_id == aid)).one()
        assert review.final_status == "NEEDS_REVIEW"
        assert (forms.STORAGE.parent / saved.written_forms_archive_path).is_file()
    assert upload_bankbook(client, aid).status_code == 409
