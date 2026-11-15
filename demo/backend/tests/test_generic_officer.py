"""Synthetic per-program review, stale-evidence and decision boundary checks."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from demo.backend import models
from demo.backend.api import documents
from demo.backend.main import app
from demo.backend.ocr.base import OcrResult
from demo.backend.tests.test_generic_programs import client, fill, pdf, publish, start


def submitted(client, monkeypatch):
    posting = publish(client, ['photo_1_photo'])
    application, _, layout = start(client, posting)
    fill(client, application, layout)
    monkeypatch.setattr(documents, 'read_document', lambda path, expected: OcrResult(tier='none'))
    upload = client.post(f'/api/applications/{application["id"]}/documents',
        data={'slot_key': 'photo_1_photo'}, files={'file': ('synthetic.pdf', pdf(), 'application/pdf')})
    assert upload.status_code == 200, upload.text
    response = client.post(f'/api/applications/{application["id"]}/submit')
    assert response.status_code == 200, response.text
    return posting, application, upload.json()


def review_path(posting, application):
    return f'/api/officer/programs/{posting["id"]}/applications/{application["id"]}'


def check_all(client, path):
    detail = client.get(path).json()
    checks = detail['checks']
    return client.put(path + '/checks', json={'document_ids': checks['required_document_ids'],
        'checklist_ids': checks['required_checklist_ids'], 'fingerprint': checks['fingerprint']})


def stored_review(application_id):
    with models.get_session() as session:
        return session.exec(select(models.Review).where(models.Review.application_id == application_id)).one()


def test_generic_detail_requires_session_and_has_inline_originals_without_score_sheet(client, monkeypatch):
    posting, application, document = submitted(client, monkeypatch)
    path = review_path(posting, application)
    outsider = TestClient(app)
    assert outsider.get(path).status_code == 401
    result = client.get(path)
    assert result.status_code == 200, result.text
    detail = result.json()
    assert detail['posting_id'] == posting['id'] and detail['application_id'] == application['id']
    assert 'score_sheet' not in detail and 'score' not in detail
    assert detail['criteria'][0]['id'] == 'program_manual'
    assert detail['criteria'][0]['requires_check']
    assert detail['checks']['required_document_ids'] == [str(document['document_id']), 'written']
    assert not detail['can_approve']
    originals = detail['documents']
    assert originals[-1]['document_id'] == -application['id']
    assert originals[-1]['check_id'] == 'written'
    officer_only = TestClient(app)
    officer_only.cookies.update({key: value for key, value in client.cookies.items() if key == 'officer_session'})
    for original in originals:
        response = officer_only.get(original['file_url'])
        assert response.status_code == 200, response.text
        assert response.headers['content-disposition'].startswith('inline')


@pytest.mark.parametrize('method,suffix', [('GET', ''), ('PUT', '/checks'), ('POST', '/decision')])
def test_another_program_cannot_open_or_mutate_application(client, monkeypatch, method, suffix):
    posting, application, _ = submitted(client, monkeypatch)
    other = publish(client)
    own_path = review_path(posting, application)
    checks = client.get(own_path).json()['checks']
    body = {'fingerprint': checks['fingerprint'], 'document_ids': [], 'checklist_ids': []} if method == 'PUT' else {'decision': 'hold', 'memo': '합성 확인 사유'}
    response = client.request(method, review_path(other, application) + suffix, json=body)
    assert response.status_code == 404
    assert stored_review(application['id']).officer_decision is None


@pytest.mark.parametrize('legacy', [False, True])
def test_unconfirmed_review_cannot_be_approved_through_either_entry(client, monkeypatch, legacy):
    posting, application, _ = submitted(client, monkeypatch)
    path = f'/api/officer/applications/{application["id"]}' if legacy else review_path(posting, application)
    response = client.post(path + '/decision', json={'decision': 'approve', 'role': 'province'})
    assert response.status_code == 409, response.text
    assert stored_review(application['id']).officer_decision is None


def test_all_checks_allow_final_approval_and_final_state_is_closed(client, monkeypatch):
    posting, application, _ = submitted(client, monkeypatch)
    path = review_path(posting, application)
    response = check_all(client, path)
    assert response.status_code == 200, response.text
    assert response.json()['can_approve']
    result = client.post(path + '/decision', json={'decision': 'approve', 'role': 'province', 'memo': '합성 원본과 기준 확인'})
    assert result.status_code == 200 and result.json()['decision']['label'] == '최종 선정', result.text
    assert client.get(path).json()['status'] == 'decided'
    assert client.post(path + '/decision', json={'decision': 'hold', 'memo': '재검토'}).status_code == 409
    assert check_all(client, path).status_code == 409


@pytest.mark.parametrize('decision,expected_status', [('hold', 'reviewing'), ('reject', 'decided')])
def test_hold_and_reject_require_reason_and_transition_state(client, monkeypatch, decision, expected_status):
    posting, application, _ = submitted(client, monkeypatch)
    path = review_path(posting, application)
    assert client.post(path + '/decision', json={'decision': decision, 'memo': '   '}).status_code == 422
    result = client.post(path + '/decision', json={'decision': decision, 'memo': '합성 확인 사유'})
    assert result.status_code == 200, result.text
    detail = client.get(path).json()
    assert detail['status'] == expected_status
    assert detail['decision']['memo'] == '합성 확인 사유'
    if decision == 'hold':
        assert client.post(path + '/decision', json={'decision': 'approve'}).status_code == 409
        assert check_all(client, path).status_code == 200
        assert client.post(path + '/decision', json={'decision': 'approve'}).status_code == 200


def test_changed_evidence_invalidates_checks_and_rejects_stale_confirmation(client, monkeypatch):
    posting, application, document = submitted(client, monkeypatch)
    path = review_path(posting, application)
    old_checks = check_all(client, path).json()['checks']
    with models.get_session() as session:
        row = session.get(models.Document, document['document_id'])
        row.findings_json = [{'code': 'SYNTHETIC_CHANGED', 'message': '합성 자료 변경', 'severity': 'NEEDS_REVIEW'}]
        session.add(row)
        session.commit()
    detail = client.get(path).json()
    assert not detail['checks']['current'] and detail['checks']['document_ids'] == []
    assert detail['checks']['fingerprint'] != old_checks['fingerprint']
    response = client.put(path + '/checks', json={'fingerprint': old_checks['fingerprint'],
        'document_ids': old_checks['document_ids'], 'checklist_ids': old_checks['checklist_ids']})
    assert response.status_code == 409
    assert client.post(path + '/decision', json={'decision': 'approve'}).status_code == 409
    assert check_all(client, path).status_code == 200


@pytest.mark.parametrize('key,value', [('document_ids', ['999999']), ('checklist_ids', ['other_program_rule'])])
def test_check_ids_cannot_be_forged(client, monkeypatch, key, value):
    posting, application, _ = submitted(client, monkeypatch)
    path = review_path(posting, application)
    checks = client.get(path).json()['checks']
    body = {'fingerprint': checks['fingerprint'], 'document_ids': [], 'checklist_ids': [], key: value}
    assert client.put(path + '/checks', json=body).status_code == 422
    assert not client.get(path).json()['checks']['current']


def test_frozen_criteria_show_recorded_rule_results_and_source_documents(client, monkeypatch):
    posting, application, document = submitted(client, monkeypatch)
    with models.get_session() as session:
        snapshot = session.get(models.ProgramApplicationSnapshot, application['id'])
        snapshot.snapshot_json = {**snapshot.snapshot_json, 'criteria': [
            {'id': 'age', 'type': 'age', 'label': '생년월일 범위', 'values': {'birth_min': '1990-01-01'}},
            {'id': 'manual', 'type': 'checklist', 'label': '중복 참여 확인', 'values': {}}]}
        review = session.exec(select(models.Review).where(models.Review.application_id == application['id'])).one()
        review.review_payload_json = {**review.review_payload_json, 'criteria_results': [
            {'id': 'age', 'status': 'PASS', 'basis': '합성 규칙 결과', 'source_document_ids': [document['document_id']]}]}
        session.add(snapshot)
        session.add(review)
        session.commit()
    detail = client.get(review_path(posting, application)).json()
    assert detail['criteria'][0]['result'] == 'PASS'
    assert detail['criteria'][0]['source_document_ids'] == [document['document_id']]
    assert not detail['criteria'][0]['requires_check']
    assert detail['checks']['required_checklist_ids'] == ['manual']


def test_held_needs_review_cannot_bypass_bulk_approval_after_checks(client, monkeypatch):
    posting, application, _ = submitted(client, monkeypatch)
    path = review_path(posting, application)
    assert client.post(path + '/decision', json={'decision': 'hold', 'memo': '합성 추가 확인'}).status_code == 200
    assert check_all(client, path).status_code == 200
    result = client.post('/api/officer/applications/decisions', json={'decision': 'approve',
        'role': 'province', 'application_ids': [application['id']]})
    assert result.status_code == 409, result.text
    assert stored_review(application['id']).officer_decision == 'hold'


def test_duplicate_generic_bulk_targets_are_rejected_before_a_decision(client, monkeypatch):
    posting, application, _ = submitted(client, monkeypatch)
    result = client.post('/api/officer/applications/decisions', json={'decision': 'hold',
        'memo': '합성 확인', 'role': 'province', 'application_ids': [application['id'], application['id']]})
    assert result.status_code == 422, result.text
    assert stored_review(application['id']).officer_decision is None


def test_missing_written_original_blocks_approval_even_with_checks(client, monkeypatch):
    posting, application, _ = submitted(client, monkeypatch)
    path = review_path(posting, application)
    with models.get_session() as session:
        row = session.get(models.Application, application['id'])
        row.written_forms_archive_path = None
        session.add(row)
        session.commit()
    response = check_all(client, path)
    assert response.status_code == 200
    assert not response.json()['can_approve']
    assert client.get(path + '/written.pdf').status_code == 404
    assert client.post(path + '/decision', json={'decision': 'approve'}).status_code == 409
