"""Synthetic-only acceptance for the program store (postings) API."""
from datetime import date, datetime, timedelta

import pymupdf
import pytest
from fastapi.testclient import TestClient
from demo.backend.tests.security_support import authenticate_officer
from sqlmodel import create_engine, select

from demo.backend import models
from demo.backend.api import applications, common, documents, files, postings
from demo.backend.main import app
from demo.backend.rules.programs import DOUBLE_SAVINGS, JOB_PACKAGE, get_program

PUBLIC_KEYS = {"id", "title", "apply_start", "apply_end", "phase", "phase_label",
               "builtin", "can_apply", "apply_path", "has_notice"}
DETAIL_KEYS = PUBLIC_KEYS | {"guidance_text", "notice_url"}
OFFICER_KEYS = DETAIL_KEYS | {"status", "has_forms", "forms_url", "notice_file_name",
                              "forms_file_name", "application_count", "needs_check_count",
                              "editable", "created_at", "updated_at", "published_at"}
TODAY = date(2026, 11, 14)
MISSING = object()


@pytest.fixture
def storage(tmp_path):
    return tmp_path / "storage"


@pytest.fixture
def client(tmp_path, storage, monkeypatch):
    isolated = create_engine(f"sqlite:///{tmp_path / 'fake.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(models, "engine", isolated)
    for module in (applications, common, documents, files, postings):
        monkeypatch.setattr(module, "STORAGE", storage)
    monkeypatch.setattr(applications, "SIGNATURES", storage / "signatures")
    monkeypatch.setattr(documents, "DOCUMENTS", storage / "documents")
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    monkeypatch.setattr(models, "posting_today", lambda: TODAY)
    try:
        with TestClient(app) as connected:
            authenticate_officer(connected, monkeypatch)
            yield connected
    finally:
        isolated.dispose()


def set_today(monkeypatch, day):
    monkeypatch.setattr(models, "posting_today", lambda: day)


def tiny_pdf(text="FAKE notice"):
    with pymupdf.open() as document:
        document.new_page(width=200, height=200).insert_text((20, 40), text)
        return document.tobytes()


NOTICE = tiny_pdf("FAKE notice")
FORMS = tiny_pdf("FAKE forms")


def create(client, *, title="FAKE 합성 사업", start="2026-11-10", end="2026-11-20",
           notice=NOTICE, forms=FORMS):
    data = {key: value for key, value in (("title", title), ("apply_start", start), ("apply_end", end))
            if value is not MISSING}
    uploads = {key: (name, value, "application/pdf")
               for key, name, value in (("notice_pdf", "FAKE-공고문.pdf", notice),
                                        ("forms_pdf", "FAKE-서식.pdf", forms))
               if value is not MISSING}
    return client.post("/api/officer/postings", data=data, files=uploads or None)


def created(client, **kwargs):
    response = create(client, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()


def published(client, **kwargs):
    row = created(client, **kwargs)
    response = client.post(f"/api/officer/postings/{row['id']}/publish")
    assert response.status_code == 200, response.text
    return response.json()


def stored_rows():
    with models.get_session() as session:
        return list(session.exec(select(models.ProgramPosting)).all())


def builtin_row():
    rows = [row for row in stored_rows() if row.rule_code == JOB_PACKAGE]
    assert len(rows) == 1
    return rows[0]


def officer_item(client, posting_id):
    response = client.get(f"/api/officer/postings/{posting_id}")
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- built-in row


def test_builtin_row_exists_once_and_is_never_duplicated_or_overwritten(client):
    program = get_program(JOB_PACKAGE)
    row = builtin_row()
    assert [item.rule_code for item in stored_rows()] == [JOB_PACKAGE]
    assert program.apply_period[1] < TODAY
    assert (row.title, row.apply_start, row.apply_end) == (
        program.name, program.apply_period[0], date(TODAY.year, 12, 31))
    assert row.status == models.POSTING_PUBLISHED and row.published_at is not None
    assert row.guidance_text == "" and row.template_json == {}
    assert row.notice_path is None and row.forms_path is None

    models.init_db()
    assert builtin_row().id == row.id

    with models.get_session() as session:
        stored = session.get(models.ProgramPosting, row.id)
        stored.title = "FAKE 고친 이름"
        stored.status = models.POSTING_CLOSED
        stored.guidance_text = "FAKE 안내"
        session.add(stored)
        session.commit()
    models.init_db()
    kept = builtin_row()
    assert (kept.id, kept.title, kept.status, kept.guidance_text) == (
        row.id, "FAKE 고친 이름", models.POSTING_CLOSED, "FAKE 안내")
    assert not any(item.rule_code == DOUBLE_SAVINGS for item in stored_rows())


def reseed_builtin(monkeypatch, day):
    with models.get_session() as session:
        session.delete(session.get(models.ProgramPosting, builtin_row().id))
        session.commit()
    set_today(monkeypatch, day)
    models.init_db()
    return builtin_row()


@pytest.mark.parametrize("offset", ["first-day", "middle", "last-day", "before"])
def test_seed_on_or_before_the_rule_period_end_keeps_the_rule_end_date(client, monkeypatch, offset):
    start, end = get_program(JOB_PACKAGE).apply_period
    day = {"first-day": start, "middle": start + timedelta(days=3), "last-day": end,
           "before": start - timedelta(days=30)}[offset]
    row = reseed_builtin(monkeypatch, day)
    assert (row.apply_start, row.apply_end) == (start, end)
    item = client.get(f"/api/postings/{row.id}").json()
    assert item["phase"] == ("upcoming" if offset == "before" else "open")
    assert item["can_apply"] is (offset != "before")


@pytest.mark.parametrize("day", [date(2026, 5, 2), date(2026, 11, 14), date(2026, 12, 31), date(2027, 3, 1)])
def test_seed_after_the_rule_period_extends_the_end_to_december_31_of_the_seed_year(client, monkeypatch, day):
    start, end = get_program(JOB_PACKAGE).apply_period
    assert day > end
    row = reseed_builtin(monkeypatch, day)
    assert (row.apply_start, row.apply_end) == (start, date(day.year, 12, 31))
    item = client.get(f"/api/postings/{row.id}").json()
    assert (item["phase"], item["phase_label"], item["builtin"]) == ("open", "접수 중", True)
    assert (item["can_apply"], item["apply_path"]) == (True, "/apply/identity")
    # A later start with a past period must not move the stored row.
    set_today(monkeypatch, date(day.year + 1, 6, 1))
    models.init_db()
    assert builtin_row().apply_end == date(day.year, 12, 31)
    assert client.get(f"/api/postings/{row.id}").json()["phase"] == "closed"


def test_builtin_row_is_listed_for_both_sides_with_zero_counts(client):
    program = get_program(JOB_PACKAGE)
    officer = client.get("/api/officer/postings").json()["items"]
    assert len(officer) == 1 and set(officer[0]) == OFFICER_KEYS
    item = officer[0]
    assert item["title"] == program.name
    assert (item["apply_start"], item["apply_end"]) == (program.apply_period[0].isoformat(), "2026-12-31")
    assert (item["phase"], item["can_apply"], item["apply_path"]) == ("open", True, "/apply/identity")
    assert (item["status"], item["builtin"], item["editable"]) == ("published", True, False)
    assert (item["application_count"], item["needs_check_count"]) == (0, 0)
    assert (item["has_notice"], item["has_forms"], item["notice_url"], item["forms_url"]) == (False, False, None, None)
    public = client.get("/api/postings").json()["items"]
    assert [row["id"] for row in public] == [item["id"]] and set(public[0]) == PUBLIC_KEYS
    assert client.get(f"/api/postings/{item['id']}/files/notice.pdf").status_code == 404


# ---------------------------------------------------------------- create


def test_create_draft_returns_officer_posting_and_stores_files_in_isolated_storage(client, storage):
    response = create(client, title="  FAKE 합성 사업  ")
    assert response.status_code == 201
    item = response.json()
    assert set(item) == OFFICER_KEYS
    assert item["title"] == "FAKE 합성 사업"
    assert (item["apply_start"], item["apply_end"]) == ("2026-11-10", "2026-11-20")
    assert (item["status"], item["phase"], item["phase_label"]) == ("draft", "draft", "작성 중")
    assert (item["builtin"], item["editable"], item["can_apply"], item["apply_path"]) == (False, True, False, None)
    assert (item["has_notice"], item["has_forms"]) == (True, True)
    assert item["notice_url"] == f"/api/officer/postings/{item['id']}/files/notice.pdf"
    assert item["forms_url"] == f"/api/officer/postings/{item['id']}/files/forms.pdf"
    assert (item["notice_file_name"], item["forms_file_name"]) == ("FAKE-공고문.pdf", "FAKE-서식.pdf")
    assert (item["application_count"], item["needs_check_count"]) == (0, 0)
    assert item["guidance_text"] == "" and item["published_at"] is None
    assert datetime.fromisoformat(item["created_at"]) and datetime.fromisoformat(item["updated_at"])

    row = next(row for row in stored_rows() if row.id == item["id"])
    assert (row.notice_path, row.forms_path) == (
        f"postings/{row.id}/notice.pdf", f"postings/{row.id}/forms.pdf")
    assert row.rule_code is None and row.template_json == {}
    assert (storage / row.notice_path).read_bytes() == NOTICE
    assert (storage / row.forms_path).read_bytes() == FORMS
    assert officer_item(client, item["id"]) == item


def test_title_of_exactly_one_hundred_characters_is_accepted(client):
    assert created(client, title="가" * 100)["title"] == "가" * 100


@pytest.mark.parametrize("case,overrides,labels", [
    ("empty-title", {"title": ""}, ["사업명"]),
    ("blank-title", {"title": "   "}, ["사업명"]),
    ("absent-title", {"title": MISSING}, ["사업명"]),
    ("long-title", {"title": "가" * 101}, ["사업명"]),
    ("slashed-start", {"start": "2026/11/10"}, ["접수 시작일"]),
    ("impossible-start", {"start": "2026-02-30"}, ["접수 시작일"]),
    ("absent-start", {"start": MISSING}, ["접수 시작일"]),
    ("worded-end", {"end": "내일"}, ["접수 종료일"]),
    ("absent-end", {"end": MISSING}, ["접수 종료일"]),
    ("start-after-end", {"start": "2026-11-21", "end": "2026-11-20"}, ["접수 시작일", "접수 종료일"]),
    ("absent-notice", {"notice": MISSING}, ["공고문 PDF"]),
    ("absent-forms", {"forms": MISSING}, ["서식 PDF"]),
    ("absent-both-files", {"notice": MISSING, "forms": MISSING}, ["공고문 PDF"]),
    ("text-notice", {"notice": b"FAKE plain text, not a PDF"}, ["공고문 PDF"]),
    ("text-forms", {"forms": b"FAKE plain text, not a PDF"}, ["서식 PDF"]),
    ("empty-forms", {"forms": b""}, ["서식 PDF"]),
])
def test_create_validation_failures_name_the_field_and_leave_nothing_behind(
        client, storage, case, overrides, labels):
    response = create(client, **overrides)
    assert response.status_code == 422, case
    detail = response.json()["detail"]
    assert isinstance(detail, str) and all(label in detail for label in labels)
    assert [row.rule_code for row in stored_rows()] == [JOB_PACKAGE]
    assert not (storage / "postings").exists()


@pytest.mark.parametrize("field,label", [("notice", "공고문 PDF"), ("forms", "서식 PDF")])
def test_file_over_the_size_limit_is_rejected(client, storage, monkeypatch, field, label):
    assert postings.MAX_PDF_BYTES == 20 * 1024 * 1024
    monkeypatch.setattr(postings, "MAX_PDF_BYTES", len(NOTICE) + len(FORMS))
    oversized = NOTICE + b"\n%FAKE" * (len(FORMS) // 6 + 1)
    assert len(oversized) > postings.MAX_PDF_BYTES
    response = create(client, **{field: oversized})
    assert response.status_code == 422
    assert label in response.json()["detail"] and "20MB" in response.json()["detail"]
    assert not (storage / "postings").exists()
    exact = NOTICE + b"\n" * len(FORMS)
    assert len(exact) == postings.MAX_PDF_BYTES
    assert create(client, **{field: exact}).status_code == 201


# ---------------------------------------------------------------- public visibility


def test_drafts_are_invisible_publicly_until_published(client):
    draft = created(client)
    builtin_id = builtin_row().id
    assert [row["id"] for row in client.get("/api/postings").json()["items"]] == [builtin_id]
    for path in (f"/api/postings/{draft['id']}", f"/api/postings/{draft['id']}/files/notice.pdf",
                 "/api/postings/999999", "/api/postings/999999/files/notice.pdf"):
        response = client.get(path)
        assert response.status_code == 404 and isinstance(response.json()["detail"], str)

    assert client.post(f"/api/officer/postings/{draft['id']}/publish").status_code == 200
    listed = client.get("/api/postings").json()["items"]
    assert [row["id"] for row in listed] == [draft["id"], builtin_id]
    assert all(set(row) == PUBLIC_KEYS for row in listed)
    detail = client.get(f"/api/postings/{draft['id']}").json()
    assert set(detail) == DETAIL_KEYS
    assert detail["notice_url"] == f"/api/postings/{draft['id']}/files/notice.pdf"
    assert (detail["phase"], detail["phase_label"], detail["has_notice"]) == ("open", "접수 중", True)
    assert {key: detail[key] for key in PUBLIC_KEYS} == listed[0]
    # The form bundle has no public address at all.
    assert client.get(f"/api/postings/{draft['id']}/files/forms.pdf").status_code == 404


# ---------------------------------------------------------------- publish / close


def test_publish_and_close_state_rules(client):
    draft = created(client)
    base = f"/api/officer/postings/{draft['id']}"
    refused = client.post(f"{base}/close")
    assert refused.status_code == 409 and isinstance(refused.json()["detail"], str)

    first = client.post(f"{base}/publish")
    assert first.status_code == 200 and set(first.json()) == OFFICER_KEYS
    assert (first.json()["status"], first.json()["phase"]) == ("published", "open")
    first_published_at = first.json()["published_at"]
    assert first_published_at is not None
    assert client.post(f"{base}/publish").status_code == 409

    closed = client.post(f"{base}/close")
    assert closed.status_code == 200 and set(closed.json()) == OFFICER_KEYS
    assert (closed.json()["status"], closed.json()["phase"], closed.json()["phase_label"]) == ("closed", "closed", "마감")
    assert client.post(f"{base}/close").status_code == 409
    public = client.get(f"/api/postings/{draft['id']}").json()
    assert (public["phase"], public["phase_label"], public["can_apply"]) == ("closed", "마감", False)
    assert client.get(public["notice_url"]).status_code == 200

    with models.get_session() as session:
        row = session.get(models.ProgramPosting, draft["id"])
        row.published_at = datetime(2026, 11, 1, 9, 0, 0)
        session.add(row)
        session.commit()
    again = client.post(f"{base}/publish")
    assert again.status_code == 200
    assert (again.json()["status"], again.json()["published_at"]) == ("published", "2026-11-01T09:00:00")

    for action in ("publish", "close"):
        assert client.post(f"/api/officer/postings/999999/{action}").status_code == 404


@pytest.mark.parametrize("kind,label", [("notice", "공고문 PDF"), ("forms", "서식 PDF")])
def test_publish_is_refused_when_a_pdf_is_gone(client, storage, kind, label):
    draft = created(client)
    (storage / "postings" / str(draft["id"]) / f"{kind}.pdf").unlink()
    item = officer_item(client, draft["id"])
    assert item[f"has_{kind}"] is False and item[f"{kind}_url"] is None
    response = client.post(f"/api/officer/postings/{draft['id']}/publish")
    assert response.status_code == 409 and label in response.json()["detail"]
    assert officer_item(client, draft["id"])["status"] == "draft"


def test_publish_is_refused_for_a_row_that_never_had_files(client):
    with models.get_session() as session:
        row = models.ProgramPosting(title="FAKE 파일 없는 사업", apply_start=TODAY, apply_end=TODAY)
        session.add(row)
        session.commit()
        session.refresh(row)
    assert client.post(f"/api/officer/postings/{row.id}/publish").status_code == 409


def test_builtin_row_closes_and_republishes_without_files(client):
    base = f"/api/officer/postings/{builtin_row().id}"
    before = builtin_row().published_at
    assert client.post(f"{base}/publish").status_code == 409
    assert client.post(f"{base}/close").json()["status"] == "closed"
    assert client.post(f"{base}/publish").json()["status"] == "published"
    assert builtin_row().published_at == before


# ---------------------------------------------------------------- delete


def test_delete_rules(client, storage):
    draft = created(client)
    folder = storage / "postings" / str(draft["id"])
    assert folder.is_dir()
    response = client.delete(f"/api/officer/postings/{draft['id']}")
    assert response.status_code == 204 and response.content == b""
    assert not folder.exists()
    assert client.get(f"/api/officer/postings/{draft['id']}").status_code == 404
    assert client.delete(f"/api/officer/postings/{draft['id']}").status_code == 404

    # A program published by mistake can be removed while nobody has applied.
    live = published(client)
    live_folder = storage / "postings" / str(live["id"])
    assert client.delete(f"/api/officer/postings/{live['id']}").status_code == 204
    assert not live_folder.exists()
    assert client.get(f"/api/postings/{live['id']}").status_code == 404
    closed = published(client)
    assert client.post(f"/api/officer/postings/{closed['id']}/close").status_code == 200
    assert client.delete(f"/api/officer/postings/{closed['id']}").status_code == 204

    builtin_id = builtin_row().id
    assert client.delete(f"/api/officer/postings/{builtin_id}").status_code == 409
    with models.get_session() as session:
        row = session.get(models.ProgramPosting, builtin_id)
        row.status = models.POSTING_DRAFT
        session.add(row)
        session.commit()
    refused = client.delete(f"/api/officer/postings/{builtin_id}")
    assert refused.status_code == 409 and isinstance(refused.json()["detail"], str)
    assert builtin_row().id == builtin_id


@pytest.mark.parametrize("status", [models.STATUS_DRAFT, models.STATUS_SUBMITTED])
def test_program_with_any_application_cannot_be_deleted(client, storage, status):
    live = published(client)
    folder = storage / "postings" / str(live["id"])
    add_application(1, program=f"posting_{live['id']}", status=status)
    refused = client.delete(f"/api/officer/postings/{live['id']}")
    assert refused.status_code == 409 and "마감" in refused.json()["detail"]
    assert live["id"] in {row.id for row in stored_rows()}
    assert sorted(path.name for path in folder.iterdir()) == ["forms.pdf", "notice.pdf"]


# ---------------------------------------------------------------- patch


def test_patch_changes_only_the_fields_sent(client):
    draft = created(client)
    path = f"/api/officer/postings/{draft['id']}"
    response = client.patch(path, json={"title": "  FAKE 새 이름  "})
    assert response.status_code == 200 and set(response.json()) == OFFICER_KEYS
    assert response.json() == {**draft, "title": "FAKE 새 이름", "updated_at": response.json()["updated_at"]}
    assert response.json()["updated_at"] >= draft["updated_at"]

    response = client.patch(path, json={"apply_end": "2026-12-31", "guidance_text": "FAKE 안내 문구"})
    assert response.status_code == 200
    item = response.json()
    assert (item["title"], item["apply_start"], item["apply_end"], item["guidance_text"]) == (
        "FAKE 새 이름", "2026-11-10", "2026-12-31", "FAKE 안내 문구")
    assert client.patch(path, json={"apply_start": "2026-12-31"}).json()["apply_start"] == "2026-12-31"
    assert client.patch(path, json={}).status_code == 200
    assert client.patch("/api/officer/postings/999999", json={"title": "FAKE"}).status_code == 404

    live = published(client)
    assert client.patch(f"/api/officer/postings/{live['id']}", json={"guidance_text": "FAKE 게시 후 안내"}).status_code == 200
    assert client.get(f"/api/postings/{live['id']}").json()["guidance_text"] == "FAKE 게시 후 안내"


@pytest.mark.parametrize("body,labels", [
    ({"title": ""}, ["사업명"]),
    ({"title": "   "}, ["사업명"]),
    ({"title": "가" * 101}, ["사업명"]),
    ({"apply_start": "2026-13-01"}, ["접수 시작일"]),
    ({"apply_end": "20261120"}, ["접수 종료일"]),
    ({"apply_start": "2026-11-21"}, ["접수 시작일", "접수 종료일"]),
    ({"apply_end": "2026-11-09"}, ["접수 시작일", "접수 종료일"]),
    ({"title": "FAKE 바꿀 이름", "guidance_text": "FAKE 안내", "apply_end": "2026-11-09"}, ["접수 종료일"]),
])
def test_patch_validation_failures_change_nothing(client, body, labels):
    draft = created(client)
    response = client.patch(f"/api/officer/postings/{draft['id']}", json=body)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str) and all(label in detail for label in labels)
    assert officer_item(client, draft["id"]) == draft


def test_builtin_row_title_cannot_be_changed(client):
    row = builtin_row()
    path = f"/api/officer/postings/{row.id}"
    for body in ({"title": "FAKE 이름"}, {"title": row.title},
                 {"guidance_text": "FAKE 안내", "title": "FAKE 이름"},
                 {"apply_start": "2026-11-01", "apply_end": "2026-11-30", "title": "FAKE 이름"}):
        response = client.patch(path, json=body)
        assert response.status_code == 409 and isinstance(response.json()["detail"], str)
    kept = builtin_row()
    assert (kept.title, kept.apply_start, kept.apply_end, kept.guidance_text) == (
        row.title, row.apply_start, row.apply_end, "")

    response = client.patch(path, json={"guidance_text": "FAKE 기본 사업 안내"})
    assert response.status_code == 200 and response.json()["guidance_text"] == "FAKE 기본 사업 안내"
    assert client.get(f"/api/postings/{row.id}").json()["guidance_text"] == "FAKE 기본 사업 안내"


def test_builtin_row_period_can_be_changed_and_moves_the_phase(client):
    row = builtin_row()
    path = f"/api/officer/postings/{row.id}"
    public = f"/api/postings/{row.id}"
    assert client.get(public).json()["phase"] == "open"

    ended = client.patch(path, json={"apply_end": "2026-11-13"})
    assert ended.status_code == 200 and set(ended.json()) == OFFICER_KEYS
    assert (ended.json()["apply_end"], ended.json()["phase"], ended.json()["phase_label"]) == ("2026-11-13", "closed", "마감")
    assert (ended.json()["builtin"], ended.json()["editable"], ended.json()["title"]) == (True, False, row.title)
    item = client.get(public).json()
    assert (item["phase"], item["can_apply"], item["apply_path"]) == ("closed", False, None)

    later = client.patch(path, json={"apply_start": "2026-11-15", "apply_end": "2026-12-31"})
    assert later.status_code == 200
    item = client.get(public).json()
    assert (item["phase"], item["phase_label"], item["can_apply"], item["apply_path"]) == ("upcoming", "접수 예정", False, None)

    assert client.patch(path, json={"apply_start": "2026-11-14"}).status_code == 200
    item = client.get(public).json()
    assert (item["apply_start"], item["apply_end"]) == ("2026-11-14", "2026-12-31")
    assert (item["phase"], item["can_apply"], item["apply_path"]) == ("open", True, "/apply/identity")

    for body, labels in (({"apply_start": "2027-01-01"}, ["접수 시작일", "접수 종료일"]),
                         ({"apply_end": "2026/12/31"}, ["접수 종료일"]),
                         ({"apply_start": ""}, ["접수 시작일"])):
        response = client.patch(path, json=body)
        assert response.status_code == 422
        assert all(label in response.json()["detail"] for label in labels)
    kept = builtin_row()
    assert (kept.apply_start, kept.apply_end) == (date(2026, 11, 14), date(2026, 12, 31))
    # The officer's period survives a restart.
    models.init_db()
    assert (builtin_row().apply_start, builtin_row().apply_end) == (date(2026, 11, 14), date(2026, 12, 31))


# ---------------------------------------------------------------- phase


@pytest.mark.parametrize("day,phase,label", [
    (date(2026, 11, 9), "upcoming", "접수 예정"),
    (date(2026, 11, 10), "open", "접수 중"),
    (date(2026, 11, 20), "open", "접수 중"),
    (date(2026, 11, 21), "closed", "마감"),
])
def test_phase_follows_the_date_for_published_rows(client, monkeypatch, day, phase, label):
    live = published(client, start="2026-11-10", end="2026-11-20")
    draft = created(client, start="2026-11-10", end="2026-11-20")
    set_today(monkeypatch, day)
    for item in (client.get(f"/api/postings/{live['id']}").json(), officer_item(client, live["id"])):
        assert (item["phase"], item["phase_label"]) == (phase, label)
        # Applying to a program without a rule set is not built until step 4.
        assert (item["can_apply"], item["apply_path"]) == (False, None)
    assert officer_item(client, live["id"])["status"] == "published"
    untouched = officer_item(client, draft["id"])
    assert (untouched["phase"], untouched["phase_label"]) == ("draft", "작성 중")

    assert client.post(f"/api/officer/postings/{live['id']}/close").status_code == 200
    closed = client.get(f"/api/postings/{live['id']}").json()
    assert (closed["phase"], closed["phase_label"]) == ("closed", "마감")


def test_builtin_row_can_apply_only_while_open(client, monkeypatch):
    row = builtin_row()
    path = f"/api/postings/{row.id}"
    for day, phase, can_apply in ((row.apply_start - timedelta(days=1), "upcoming", False),
                                  (row.apply_start, "open", True),
                                  (row.apply_end, "open", True),
                                  (row.apply_end + timedelta(days=1), "closed", False)):
        set_today(monkeypatch, day)
        item = client.get(path).json()
        assert (item["phase"], item["builtin"], item["can_apply"]) == (phase, True, can_apply)
        assert item["apply_path"] == ("/apply/identity" if can_apply else None)
        assert client.get("/api/postings").json()["items"][0] == {key: item[key] for key in PUBLIC_KEYS}

    set_today(monkeypatch, row.apply_start)
    assert client.post(f"/api/officer/postings/{row.id}/close").status_code == 200
    closed = client.get(path).json()
    assert (closed["phase"], closed["can_apply"], closed["apply_path"]) == ("closed", False, None)


def test_list_order_open_upcoming_closed_then_newest_start_with_drafts_first_for_officers(client):
    published(client, title="FAKE 접수중 먼저 시작", start="2026-11-10", end="2026-11-20")
    published(client, title="FAKE 접수중 나중 시작", start="2026-11-12", end="2026-11-30")
    published(client, title="FAKE 접수 예정", start="2026-12-01", end="2026-12-10")
    published(client, title="FAKE 기간 지남", start="2026-10-01", end="2026-10-10")
    ended = published(client, title="FAKE 담당자 마감", start="2026-11-01", end="2026-11-30")
    assert client.post(f"/api/officer/postings/{ended['id']}/close").status_code == 200
    created(client, title="FAKE 작성중 먼저 시작", start="2026-11-13", end="2026-11-15")
    created(client, title="FAKE 작성중 나중 시작", start="2026-12-05", end="2026-12-06")
    builtin = get_program(JOB_PACKAGE).name
    assert builtin_row().apply_start < date(2026, 11, 10) and builtin_row().apply_end >= TODAY

    expected = ["FAKE 접수중 나중 시작", "FAKE 접수중 먼저 시작", builtin, "FAKE 접수 예정",
                "FAKE 담당자 마감", "FAKE 기간 지남"]
    public = client.get("/api/postings").json()["items"]
    assert [row["title"] for row in public] == expected
    assert [row["phase"] for row in public] == ["open", "open", "open", "upcoming", "closed", "closed"]
    officer = client.get("/api/officer/postings").json()["items"]
    assert [row["title"] for row in officer] == ["FAKE 작성중 나중 시작", "FAKE 작성중 먼저 시작", *expected]
    assert all(set(row) == OFFICER_KEYS for row in officer)


# ---------------------------------------------------------------- counts


def add_application(number, *, program=JOB_PACKAGE, status=models.STATUS_SUBMITTED, ai=None, decision=None):
    with models.get_session() as session:
        application = models.Application(
            application_no=f"FAKE-POSTING-{number:03}", program_code=program, status=status,
            criteria_version=1,
            form1_json={"name": "가상신청", "address": "전북특별자치도 전주시 가상동 0"},
            submitted_at=None if status == models.STATUS_DRAFT else datetime(2026, 11, 1, 9, number))
        session.add(application)
        session.commit()
        session.refresh(application)
        if ai is not None:
            session.add(models.Review(application_id=application.id, final_status=ai,
                                      officer_decision=decision,
                                      officer_role="province" if decision else None))
            session.commit()
        return application.id


def test_counts_for_the_builtin_row_follow_the_officer_list(client):
    other = created(client)
    add_application(1, status=models.STATUS_DRAFT)
    add_application(2)                                                    # not reviewed
    add_application(3, ai="PASS")
    add_application(4, ai="NEEDS_REVIEW")
    add_application(5, ai="FAIL")
    add_application(6, ai="FAIL", decision="reject", status=models.STATUS_DECIDED)
    add_application(7, ai="NEEDS_REVIEW", decision="hold", status=models.STATUS_REVIEWING)
    add_application(8, ai="PASS", decision="approve", status=models.STATUS_DECIDED)
    add_application(9, program=DOUBLE_SAVINGS, ai="NEEDS_REVIEW")
    add_application(10, program=DOUBLE_SAVINGS)

    builtin_id = builtin_row().id
    item = officer_item(client, builtin_id)
    assert (item["application_count"], item["needs_check_count"]) == (7, 3)
    listed = {row["id"]: row for row in client.get("/api/officer/postings").json()["items"]}
    assert (listed[builtin_id]["application_count"], listed[builtin_id]["needs_check_count"]) == (7, 3)
    assert (listed[other["id"]]["application_count"], listed[other["id"]]["needs_check_count"]) == (0, 0)
    assert officer_item(client, other["id"])["application_count"] == 0

    # The same numbers must be readable from the existing application list.
    everything = client.get("/api/officer/applications",
                            params={"role": "province", "program": JOB_PACKAGE, "page_size": 200}).json()
    assert everything["total"] == item["application_count"]
    waiting = client.get("/api/officer/applications",
                         params={"role": "province", "program": JOB_PACKAGE,
                                 "status": "pending", "page_size": 200}).json()
    assert sum(row["ai_status"] != "PASS" for row in waiting["rows"]) == item["needs_check_count"]

    # A decision removes the case from the needs-check number, not from the total.
    with models.get_session() as session:
        review = session.exec(select(models.Review).where(models.Review.final_status == "FAIL",
                                                          models.Review.officer_decision.is_(None))).one()
        review.officer_decision = "reject"
        session.add(review)
        session.commit()
    item = officer_item(client, builtin_id)
    assert (item["application_count"], item["needs_check_count"]) == (7, 2)


# ---------------------------------------------------------------- files


def assert_inline_pdf(response, body):
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["cache-control"] == "no-store"
    assert response.content == body and response.content.startswith(b"%PDF-")


def test_notice_and_forms_files_are_served_inline_as_pdf(client):
    draft = created(client)
    assert_inline_pdf(client.get(draft["notice_url"]), NOTICE)
    assert_inline_pdf(client.get(draft["forms_url"]), FORMS)
    assert client.get(f"/api/postings/{draft['id']}/files/notice.pdf").status_code == 404
    for path in (f"/api/officer/postings/{draft['id']}/files/other.pdf",
                 "/api/officer/postings/999999/files/notice.pdf",
                 f"/api/officer/postings/{builtin_row().id}/files/forms.pdf"):
        response = client.get(path)
        assert response.status_code == 404 and isinstance(response.json()["detail"], str)

    assert client.post(f"/api/officer/postings/{draft['id']}/publish").status_code == 200
    public = client.get(f"/api/postings/{draft['id']}").json()
    assert_inline_pdf(client.get(public["notice_url"]), NOTICE)
    assert_inline_pdf(client.get(officer_item(client, draft["id"])["notice_url"]), NOTICE)


# ---------------------------------------------------------------- review fixes


@pytest.mark.parametrize("posting_id", [0, 2**63, 99999999999999999999])
def test_out_of_range_ids_are_not_found_on_both_sides(client, posting_id):
    for path in (f"/api/postings/{posting_id}", f"/api/officer/postings/{posting_id}"):
        response = client.get(path)
        assert response.status_code == 404 and isinstance(response.json()["detail"], str)
    assert client.post(f"/api/officer/postings/{posting_id}/publish").status_code == 404
    assert client.delete(f"/api/officer/postings/{posting_id}").status_code == 404


def test_deleted_draft_ids_are_not_reused(client):
    first = created(client)
    assert client.delete(f"/api/officer/postings/{first['id']}").status_code == 204
    second = created(client)
    assert second["id"] > first["id"]


def test_title_whitespace_is_collapsed_and_control_characters_are_refused(client):
    draft = created(client, title="  FAKE\t합성\n 사업  ")
    assert draft["title"] == "FAKE 합성 사업"
    path = f"/api/officer/postings/{draft['id']}"
    refused = client.patch(path, json={"title": "FAKE\u0000이름"})
    assert refused.status_code == 422 and "사업명" in refused.json()["detail"]
    assert officer_item(client, draft["id"])["title"] == "FAKE 합성 사업"


def test_guidance_text_has_a_length_limit(client):
    draft = created(client)
    path = f"/api/officer/postings/{draft['id']}"
    assert client.patch(path, json={"guidance_text": "가" * 20_000}).status_code == 200
    refused = client.patch(path, json={"guidance_text": "가" * 20_001})
    assert refused.status_code == 422 and isinstance(refused.json()["detail"], str)
    assert len(officer_item(client, draft["id"])["guidance_text"]) == 20_000
