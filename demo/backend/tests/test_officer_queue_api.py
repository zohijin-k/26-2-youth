"""Synthetic-only acceptance for the officer list queues, search and the reasons endpoint."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from demo.backend.tests.security_support import authenticate_officer
from sqlmodel import create_engine, select

from demo.backend import models
from demo.backend.api import applications, common, documents, files, officer, postings
from demo.backend.main import app
from demo.backend.rules.programs import DOUBLE_SAVINGS, JOB_PACKAGE

LIST = "/api/officer/applications"
#: Top-level keys the list returned before this step. They must all still be there.
OLD_LIST_KEYS = {"role", "scope", "filters", "columns", "quota", "first_come",
                 "total", "page", "page_size", "page_count", "rows"}
OLD_APPLIED_KEYS = {"program", "status", "ai_status", "submitted_from", "submitted_to", "sort"}
REASON_KEYS = {"application_id", "ai_status", "ai_status_label", "source", "documents", "missing"}
DOCUMENT_KEYS = {"slot_key", "label", "status", "status_label", "findings"}
FINDING_KEYS = {"code", "message", "severity"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    isolated = create_engine(f"sqlite:///{tmp_path / 'fake.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(models, "engine", isolated)
    for module in (applications, common, documents, files, postings):
        monkeypatch.setattr(module, "STORAGE", storage)
    monkeypatch.setattr(applications, "SIGNATURES", storage / "signatures")
    monkeypatch.setattr(documents, "DOCUMENTS", storage / "documents")
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    try:
        with TestClient(app) as connected:
            authenticate_officer(connected, monkeypatch)
            yield connected
    finally:
        isolated.dispose()


def add_application(number, *, name="가상신청", place="전주시 가상동", program=JOB_PACKAGE,
                    status=models.STATUS_SUBMITTED, ai=None, decision=None, day=1):
    """One stored application. `ai=None` leaves it without a review row (not reviewed)."""
    with models.get_session() as session:
        application = models.Application(
            application_no=f"FAKE-QUEUE-{number:03}", program_code=program, status=status,
            criteria_version=1,
            form1_json={"name": name, "address": f"전북특별자치도 {place} 0"},
            submitted_at=None if status == models.STATUS_DRAFT else datetime(2026, 11, day, 9, number))
        session.add(application)
        session.commit()
        session.refresh(application)
        if ai is not None:
            session.add(models.Review(application_id=application.id, final_status=ai,
                                      officer_decision=decision,
                                      officer_role="province" if decision else None))
            session.commit()
        return application.id


def seed_queues():
    """Three undecided non-PASS, two undecided PASS, three decided, one draft."""
    return {
        "draft": add_application(1, status=models.STATUS_DRAFT),
        "unreviewed": add_application(2),
        "needs_review": add_application(3, ai="NEEDS_REVIEW"),
        "fail": add_application(4, ai="FAIL"),
        "pass_a": add_application(5, ai="PASS"),
        "pass_b": add_application(6, ai="PASS"),
        "approved": add_application(7, ai="PASS", decision="approve", status=models.STATUS_DECIDED),
        "held": add_application(8, ai="NEEDS_REVIEW", decision="hold", status=models.STATUS_REVIEWING),
        "rejected": add_application(9, ai="FAIL", decision="reject", status=models.STATUS_DECIDED),
    }


def listing(client, **params):
    response = client.get(LIST, params={"role": "province", "program": JOB_PACKAGE, "page_size": 200, **params})
    assert response.status_code == 200, response.text
    return response.json()


def ids(body):
    return [row["application_id"] for row in body["rows"]]


# ---------------------------------------------------------------- queue filter


def test_each_queue_returns_its_own_rows_and_the_three_never_overlap(client):
    made = seed_queues()
    needs = listing(client, queue="needs_check")
    passed = listing(client, queue="pass")
    done = listing(client, queue="done")
    assert ids(needs) == [made["unreviewed"], made["needs_review"], made["fail"]]
    assert ids(passed) == [made["pass_a"], made["pass_b"]]
    assert ids(done) == [made["approved"], made["held"], made["rejected"]]
    assert (needs["total"], passed["total"], done["total"]) == (3, 2, 3)

    everything = listing(client)
    assert sorted(ids(everything)) == sorted(ids(needs) + ids(passed) + ids(done))
    assert made["draft"] not in ids(everything)
    assert all(not row["decision"] and row["ai_status"] != "PASS" for row in needs["rows"])
    assert all(not row["decision"] and row["ai_status"] == "PASS" for row in passed["rows"])
    assert [row["decision"] for row in done["rows"]] == ["approve", "hold", "reject"]
    # A held case is decided even though the application itself is still under review.
    assert done["rows"][1]["status"] == models.STATUS_REVIEWING


def test_queue_counts_are_the_same_whichever_queue_is_asked_for(client):
    seed_queues()
    expected = {"needs_check": 3, "pass": 2, "done": 3}
    for params in ({}, {"queue": "needs_check"}, {"queue": "pass"}, {"queue": "done"},
                   {"status": "pending"}, {"status": "reject"}, {"ai_status": "FAIL"},
                   {"queue": "done", "status": "hold", "ai_status": "NEEDS_REVIEW"},
                   {"page": 2, "page_size": 2}, {"sort": "score"}):
        body = listing(client, **params)
        assert body["queues"] == expected, params
        assert list(body["queues"]) == ["needs_check", "pass", "done"]
    assert sum(expected.values()) == listing(client)["total"]


def test_unknown_queue_is_refused_and_an_empty_one_means_no_filter(client):
    seed_queues()
    for value in ("all", "NEEDS_CHECK", "needs-check", "pending"):
        response = client.get(LIST, params={"queue": value})
        assert response.status_code == 400, value
        assert isinstance(response.json()["detail"], str) and value in response.json()["detail"]
    blank = listing(client, queue="")
    assert blank["total"] == 8 and blank["filters"]["applied"]["queue"] is None


def test_queue_combines_with_the_existing_status_and_ai_filters(client):
    made = seed_queues()
    assert ids(listing(client, queue="needs_check", ai_status="FAIL")) == [made["fail"]]
    assert ids(listing(client, queue="needs_check", status="pending")) == [
        made["unreviewed"], made["needs_review"], made["fail"]]
    assert ids(listing(client, queue="done", status="hold")) == [made["held"]]
    assert ids(listing(client, queue="done", ai_status="PASS")) == [made["approved"]]
    # Contradicting filters all apply, so nothing is left.
    assert ids(listing(client, queue="needs_check", ai_status="PASS")) == []
    assert ids(listing(client, queue="pass", status="approve")) == []
    assert ids(listing(client, queue="done", status="pending")) == []


def test_existing_parameters_and_response_keys_keep_working(client):
    made = seed_queues()
    body = listing(client)
    assert OLD_LIST_KEYS <= set(body) and set(body) - OLD_LIST_KEYS == {"queues"}
    applied = body["filters"]["applied"]
    assert OLD_APPLIED_KEYS <= set(applied) and set(applied) - OLD_APPLIED_KEYS == {"queue", "q"}
    assert (applied["queue"], applied["q"], applied["sort"]) == (None, None, "submitted")
    assert ids(listing(client, status="pending")) == [
        made["unreviewed"], made["needs_review"], made["fail"], made["pass_a"], made["pass_b"]]
    assert ids(listing(client, status="approve")) == [made["approved"]]
    assert ids(listing(client, ai_status="NEEDS_REVIEW")) == [made["needs_review"], made["held"]]
    assert ids(listing(client, submitted_from="2026-11-02")) == []
    assert ids(listing(client, page=2, page_size=3)) == [made["pass_a"], made["pass_b"], made["approved"]]
    for params in ({"status": "done"}, {"sort": "name"}, {"submitted_from": "2026/11/01"}, {"role": "mayor"}):
        assert client.get(LIST, params={"program": JOB_PACKAGE, **params}).status_code == 400, params
    # The old error for an unknown status still comes before the new checks.
    both = client.get(LIST, params={"status": "done", "queue": "all"})
    assert both.status_code == 400 and "done" in both.json()["detail"]


# ---------------------------------------------------------------- search


def test_search_matches_the_application_number_or_the_name(client):
    first = add_application(11, name="가상하나", ai="NEEDS_REVIEW")
    second = add_application(12, name="합성둘", ai="PASS")
    third = add_application(21, name="합성셋", ai="FAIL", decision="reject", status=models.STATUS_DECIDED)
    assert ids(listing(client, q="FAKE-QUEUE-011")) == [first]
    assert ids(listing(client, q="fake-queue-01")) == [first, second]
    assert ids(listing(client, q="  QUEUE-02  ")) == [third]
    assert ids(listing(client, q="합성")) == [second, third]
    assert ids(listing(client, q="하나")) == [first]
    assert ids(listing(client, q="FAKE")) == [first, second, third]
    nothing = listing(client, q="없는이름")
    assert (nothing["total"], nothing["rows"], nothing["page_count"]) == (0, [], 1)
    assert nothing["queues"] == {"needs_check": 0, "pass": 0, "done": 0}
    assert listing(client, q="  QUEUE-02  ")["filters"]["applied"]["q"] == "QUEUE-02"


def test_search_does_not_look_at_other_columns(client):
    add_application(1, name="가상신청", place="전주시 가상동", ai="NEEDS_REVIEW")
    for text in ("전주시", "가상동", "NEEDS_REVIEW", "확인필요", JOB_PACKAGE, "2026-11"):
        assert listing(client, q=text)["total"] == 0, text


def test_blank_search_is_no_search_and_the_length_limit_is_fifty(client):
    seed_queues()
    for text in ("", "   ", "\t"):
        body = listing(client, q=text)
        assert body["total"] == 8 and body["filters"]["applied"]["q"] is None
    assert listing(client, q="가" * 50)["total"] == 0
    # Surrounding blanks do not count towards the limit.
    assert listing(client, q="  " + "가" * 50 + "  ")["total"] == 0
    refused = client.get(LIST, params={"q": "가" * 51})
    assert refused.status_code == 400 and "50" in refused.json()["detail"]


# ---------------------------------------------------------------- counts under filters


def test_queue_counts_follow_search_period_program_and_role_scope(client):
    add_application(1, name="가상하나", place="전주시 가상동", ai="NEEDS_REVIEW", day=1)
    add_application(2, name="가상둘", place="전주시 가상동", ai="PASS", day=2)
    add_application(3, name="합성셋", place="전주시 합성동", ai="FAIL", day=3)
    add_application(4, name="합성넷", place="전주시 합성동", ai="PASS", decision="approve",
                    status=models.STATUS_DECIDED, day=4)
    add_application(5, name="가상다섯", place="군산시 합성읍", day=5)
    add_application(6, name="가상여섯", place="군산시 합성읍", ai="NEEDS_REVIEW", decision="hold",
                    status=models.STATUS_REVIEWING, day=6)
    add_application(7, name="가상일곱", place="전주시 가상동", program=DOUBLE_SAVINGS, ai="NEEDS_REVIEW", day=7)

    def counts(**params):
        body = listing(client, **params)
        base = {key: value for key, value in params.items() if key not in ("queue", "status", "ai_status")}
        assert sum(body["queues"].values()) == listing(client, **base)["total"]
        return tuple(body["queues"].values())

    assert counts() == (3, 1, 2)
    assert counts(q="가상") == (2, 1, 1)
    assert counts(q="합성") == (1, 0, 1)
    assert counts(submitted_from="2026-11-03") == (2, 0, 2)
    assert counts(submitted_to="2026-11-03") == (2, 1, 0)
    assert counts(submitted_from="2026-11-02", submitted_to="2026-11-05") == (2, 1, 1)
    assert counts(q="가상", submitted_from="2026-11-05") == (1, 0, 1)
    # The queue itself and the old status / AI filters never change the counts.
    assert counts(q="가상", queue="done", status="hold", ai_status="NEEDS_REVIEW") == (2, 1, 1)

    assert counts(role="city", region="전주시") == (2, 1, 1)
    assert counts(role="city", region="군산시") == (1, 0, 1)
    assert counts(role="city", region="군산시", q="여섯") == (0, 0, 1)
    assert counts(role="town", region="전주시", town="합성동") == (1, 0, 1)
    assert counts(role="town", region="전주시", town="가상동", submitted_to="2026-11-01") == (1, 0, 0)
    # Without a program the other program's case is counted too.
    everything = client.get(LIST, params={"role": "province", "page_size": 200}).json()
    assert everything["queues"] == {"needs_check": 4, "pass": 1, "done": 2}
    assert listing(client, program=DOUBLE_SAVINGS)["queues"] == {"needs_check": 1, "pass": 0, "done": 0}


def test_needs_check_count_equals_the_program_card_number(client):
    seed_queues()
    add_application(20, program=DOUBLE_SAVINGS, ai="NEEDS_REVIEW")
    card = next(item for item in client.get("/api/officer/postings").json()["items"] if item["builtin"])
    body = listing(client, queue="needs_check")
    assert card["needs_check_count"] == body["queues"]["needs_check"] == body["total"] == 3
    assert card["application_count"] == sum(body["queues"].values()) == 8
    # One predicate decides both numbers.
    assert postings.queue_of is officer.queue_of


def test_a_decision_moves_the_case_to_done_in_both_places(client):
    made = seed_queues()
    assert listing(client)["queues"] == {"needs_check": 3, "pass": 2, "done": 3}
    decided = client.post(f"/api/officer/applications/{made['fail']}/decision",
                          json={"role": "province", "decision": "hold", "memo": "FAKE 보류"})
    assert decided.status_code == 200, decided.text
    bulk = client.post("/api/officer/applications/decisions",
                       json={"role": "province", "decision": "approve", "memo": "FAKE 일괄",
                             "application_ids": [made["pass_a"], made["pass_b"]]})
    assert bulk.status_code == 200 and bulk.json()["processed"] == 2
    after = listing(client, queue="done")
    assert after["queues"] == {"needs_check": 2, "pass": 0, "done": 6}
    assert {made["fail"], made["pass_a"], made["pass_b"]} <= set(ids(after))
    assert ids(listing(client, queue="needs_check")) == [made["unreviewed"], made["needs_review"]]
    assert ids(listing(client, queue="pass")) == []
    card = next(item for item in client.get("/api/officer/postings").json()["items"] if item["builtin"])
    assert card["needs_check_count"] == 2


# ---------------------------------------------------------------- bulk approve guard


def bulk_decide(client, decision, application_ids, role="province"):
    return client.post("/api/officer/applications/decisions",
                       json={"role": role, "decision": decision, "memo": "FAKE 일괄",
                             "application_ids": application_ids})


@pytest.mark.parametrize("case", ["needs_review", "fail", "unreviewed"])
@pytest.mark.parametrize("role", ["province", "city"])
def test_bulk_approve_is_refused_for_needs_check_cases(client, case, role):
    made = seed_queues()
    before = listing(client)["queues"]
    response = bulk_decide(client, "approve", [made[case]], role=role)
    assert response.status_code == 409, response.text
    assert "확인 필요" in response.json()["detail"]
    assert "FAKE-QUEUE-" in response.json()["detail"]
    assert listing(client)["queues"] == before


def test_bulk_approve_with_one_needs_check_case_processes_nothing(client):
    made = seed_queues()
    response = bulk_decide(client, "approve", [made["pass_a"], made["needs_review"], made["pass_b"]])
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "FAKE-QUEUE-003" in detail and "FAKE-QUEUE-005" not in detail
    assert listing(client)["queues"] == {"needs_check": 3, "pass": 2, "done": 3}
    assert ids(listing(client, queue="pass")) == [made["pass_a"], made["pass_b"]]


@pytest.mark.parametrize("decision", ["hold", "reject"])
def test_bulk_hold_and_reject_are_allowed_for_needs_check_cases(client, decision):
    made = seed_queues()
    response = bulk_decide(client, decision, [made["needs_review"], made["fail"]])
    assert response.status_code == 200, response.text
    assert response.json()["processed"] == 2
    done = listing(client, queue="done")
    assert {made["needs_review"], made["fail"]} <= set(ids(done))
    assert listing(client)["queues"] == {"needs_check": 1, "pass": 2, "done": 5}


def test_bulk_approve_is_still_allowed_for_pass_and_decided_cases(client):
    made = seed_queues()
    response = bulk_decide(client, "approve", [made["pass_a"], made["held"], made["rejected"]])
    assert response.status_code == 200, response.text
    assert response.json()["processed"] == 3


def test_single_approve_from_the_review_screen_is_not_affected(client):
    made = seed_queues()
    response = client.post(f"/api/officer/applications/{made['needs_review']}/decision",
                           json={"role": "province", "decision": "approve", "memo": "FAKE 건별"})
    assert response.status_code == 200, response.text
    assert made["needs_review"] in ids(listing(client, queue="done"))


# ---------------------------------------------------------------- reasons


def add_subsidy_items(application_id):
    """면접비 1회 + 정장비 1회 → 초본, 면접확인서, 결제영수증 세 칸."""
    with models.get_session() as session:
        session.add(models.SubsidyItem(application_id=application_id, item_type="interview", count_index=1))
        session.add(models.SubsidyItem(application_id=application_id, item_type="suit", count_index=1,
                                       receipt_amount=50_000, linked_interview_index=1))
        session.commit()


def add_document(application_id, slot_key, status, findings=()):
    with models.get_session() as session:
        document = models.Document(
            application_id=application_id, slot_key=slot_key, file_path=f"documents/FAKE-{slot_key}.pdf",
            file_format="pdf", stage1_status=status, findings_json=list(findings),
            ocr_json={"fields": {"성명": "가상신청"}})
        session.add(document)
        session.commit()
        return document.id


def reasons(client, application_id, **params):
    response = client.get(f"/api/officer/applications/{application_id}/reasons", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_reasons_list_documents_that_are_not_pass_in_checklist_order(client):
    application_id = add_application(1, ai="FAIL")
    add_subsidy_items(application_id)
    slots = [row.slot_key for row in common.checklist_for(common.load_application(application_id)) if row.upload]
    assert slots == ["resident_abstract", "interview_1_confirmation", "suit_1_receipt"]
    # Stored out of checklist order on purpose.
    add_document(application_id, "suit_1_receipt", "NEEDS_REVIEW", [
        {"code": "RECEIPT_AMOUNT_MISMATCH", "message": "FAKE 입력 금액과 영수증 금액이 다릅니다.",
         "how_to_fix": "FAKE 고치는 방법", "link": "https://example.invalid/", "severity": "NEEDS_REVIEW",
         "evidence": {"raw": "FAKE 원문"}}])
    add_document(application_id, models.UNASSIGNED_SLOT, "NEEDS_REVIEW", [
        {"code": "FAKE_UNASSIGNED", "message": "FAKE 배정되지 않은 페이지입니다."}])
    add_document(application_id, "resident_abstract", "FAIL", [
        {"code": "FAKE_OLD_ISSUE", "message": "FAKE 발급일이 기준일보다 빠릅니다.", "severity": "FAIL"},
        {"code": "FAKE_SECOND", "message": "FAKE 두 번째 확인 사항입니다.", "severity": "NEEDS_REVIEW"},
        "FAKE 글자만 있는 항목"])
    add_document(application_id, "interview_1_confirmation", "PASS", [
        {"code": "FAKE_NOTE", "message": "FAKE 적합 서류의 참고 사항", "severity": "NEEDS_REVIEW"}])

    body = reasons(client, application_id)
    assert set(body) == REASON_KEYS
    assert (body["application_id"], body["ai_status"], body["ai_status_label"], body["source"]) == (
        application_id, "FAIL", "부적합", "rules")
    assert all(set(document) == DOCUMENT_KEYS for document in body["documents"])
    assert [(document["slot_key"], document["label"], document["status"], document["status_label"])
            for document in body["documents"]] == [
        ("resident_abstract", "주민등록초본", "FAIL", "부적합"),
        ("suit_1_receipt", "결제영수증 — 면접정장비 1회차", "NEEDS_REVIEW", "확인필요"),
        (models.UNASSIGNED_SLOT, "미배정 페이지", "NEEDS_REVIEW", "확인필요")]
    abstract, receipt, loose = body["documents"]
    assert abstract["findings"] == [
        {"code": "FAKE_OLD_ISSUE", "message": "FAKE 발급일이 기준일보다 빠릅니다.", "severity": "FAIL"},
        {"code": "FAKE_SECOND", "message": "FAKE 두 번째 확인 사항입니다.", "severity": "NEEDS_REVIEW"}]
    assert receipt["findings"] == [
        {"code": "RECEIPT_AMOUNT_MISMATCH", "message": "FAKE 입력 금액과 영수증 금액이 다릅니다.",
         "severity": "NEEDS_REVIEW"}]
    # A finding stored without a severity takes the document's status.
    assert loose["findings"] == [
        {"code": "FAKE_UNASSIGNED", "message": "FAKE 배정되지 않은 페이지입니다.", "severity": "NEEDS_REVIEW"}]
    assert all(set(finding) == FINDING_KEYS for document in body["documents"] for finding in document["findings"])
    assert body["missing"] == []
    text = client.get(f"/api/officer/applications/{application_id}/reasons").text
    for hidden in ("FAKE 고치는 방법", "example.invalid", "FAKE 원문", "FAKE 적합 서류의 참고 사항", "documents/FAKE"):
        assert hidden not in text


def test_reasons_list_required_slots_without_an_upload(client):
    application_id = add_application(1, ai="NEEDS_REVIEW")
    add_subsidy_items(application_id)
    body = reasons(client, application_id)
    assert body["documents"] == []
    assert body["missing"] == [
        {"slot_key": "resident_abstract", "label": "주민등록초본"},
        {"slot_key": "interview_1_confirmation", "label": "면접확인서 — 면접비 1회차"},
        {"slot_key": "suit_1_receipt", "label": "결제영수증 — 면접정장비 1회차"}]

    add_document(application_id, "interview_1_confirmation", "PASS")
    add_document(application_id, "suit_1_receipt", None)
    body = reasons(client, application_id)
    assert body["missing"] == [{"slot_key": "resident_abstract", "label": "주민등록초본"}]
    # An uploaded document that was never checked is listed, not counted as missing.
    assert body["documents"] == [
        {"slot_key": "suit_1_receipt", "label": "결제영수증 — 면접정장비 1회차",
         "status": None, "status_label": "미심사", "findings": []}]
    # Slots that are not uploaded on this screen (신청서, 통장 사본) are never reported missing.
    assert not {"application_form", "bank_account"} & {row["slot_key"] for row in body["missing"]}


def test_reasons_mask_resident_numbers_like_the_review_detail(client):
    application_id = add_application(1, ai="NEEDS_REVIEW")
    number = "900101-1234567"
    add_document(application_id, "resident_abstract", "NEEDS_REVIEW", [
        {"code": "FAKE_IDENTITY", "message": f"FAKE 판독된 번호 {number} 확인이 필요합니다.",
         "severity": "NEEDS_REVIEW"}])
    response = client.get(f"/api/officer/applications/{application_id}/reasons")
    assert response.status_code == 200 and number not in response.text
    message = response.json()["documents"][0]["findings"][0]["message"]
    assert message == "FAKE 판독된 번호 900101-1****** 확인이 필요합니다."
    detail = client.get(f"/api/officer/applications/{application_id}").json()
    assert detail["documents"][0]["findings"][0]["message"] == message


def test_reasons_for_cases_that_are_not_reviewed_or_already_fine(client):
    unreviewed = add_application(1)
    body = reasons(client, unreviewed)
    assert (body["ai_status"], body["ai_status_label"], body["documents"]) == (None, "미심사", [])
    assert body["missing"] == [{"slot_key": "resident_abstract", "label": "주민등록초본"}]

    fine = add_application(2, ai="PASS", decision="approve", status=models.STATUS_DECIDED)
    add_document(fine, "resident_abstract", "PASS")
    body = reasons(client, fine)
    assert (body["ai_status"], body["ai_status_label"]) == ("PASS", "적합")
    assert (body["documents"], body["missing"]) == ([], [])


def test_reasons_follow_the_review_detail_for_roles_and_missing_cases(client):
    application_id = add_application(1, ai="NEEDS_REVIEW", place="군산시 합성읍")
    draft = add_application(2, status=models.STATUS_DRAFT)
    for role in ("town", "city", "province"):
        assert reasons(client, application_id, role=role) == reasons(client, application_id)
        assert client.get(f"/api/officer/applications/{application_id}", params={"role": role}).status_code == 200
    for target, params in ((application_id, {"role": "mayor"}),):
        mine = client.get(f"/api/officer/applications/{target}/reasons", params=params)
        detail = client.get(f"/api/officer/applications/{target}", params=params)
        assert mine.status_code == detail.status_code == 400
        assert mine.json()["detail"] == detail.json()["detail"]
    for target in (draft, 999_999):
        mine = client.get(f"/api/officer/applications/{target}/reasons")
        detail = client.get(f"/api/officer/applications/{target}")
        assert mine.status_code == detail.status_code == 404
        assert mine.json()["detail"] == detail.json()["detail"]
    for target in (0, -1, 2**63, 99999999999999999999):
        response = client.get(f"/api/officer/applications/{target}/reasons")
        assert response.status_code == 404 and isinstance(response.json()["detail"], str)
    assert client.get("/api/officer/applications/abc/reasons").status_code == 422


def test_reasons_read_stored_results_only(client, monkeypatch):
    """The endpoint must not re-read files, re-run the review or write anything."""
    application_id = add_application(1, ai="NEEDS_REVIEW")
    add_document(application_id, "resident_abstract", "NEEDS_REVIEW", [
        {"code": "FAKE_CHECK", "message": "FAKE 확인이 필요합니다.", "severity": "NEEDS_REVIEW"}])

    def stored():
        with models.get_session() as session:
            return ([row.model_dump() for row in session.exec(select(models.Application)).all()],
                    [row.model_dump() for row in session.exec(select(models.Document)).all()],
                    [row.model_dump() for row in session.exec(select(models.Review)).all()])

    before = stored()
    first = reasons(client, application_id)
    assert reasons(client, application_id) == first
    assert stored() == before
    assert first["documents"][0]["findings"][0]["code"] == "FAKE_CHECK"
