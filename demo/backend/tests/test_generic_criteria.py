"""Existing rule bindings reject untrusted evidence and never judge checklists."""
from copy import deepcopy
from datetime import date

import pytest

from demo.backend.generic_criteria import applicant_blockers, evaluate
from demo.backend.models import Application
from demo.backend.notice_analysis import SUPPORTED_RULES
from demo.backend.rules.doc_types import DocType


def application(birth='2000-05-15'):
    return Application(id=1, application_no='SYNTHETIC-CRITERIA', program_code='posting_10',
        identity_json={'name': '가상신청', 'birth': birth}, form1_json={'opaque_field': '무관한 입력'})


def candidate(kind, values, **changes):
    return {'id': 'synthetic_' + kind, 'type': kind, 'values': values, 'needs_review': False,
            'engine_rule': SUPPORTED_RULES.get(kind), 'quote': '합성 공개 근거', 'confidence': .7, **changes}


def document(**changes):
    return {'document_id': 31, 'doc_type': str(DocType.RESIDENT_ABSTRACT),
            'expected_doc_type': str(DocType.RESIDENT_ABSTRACT), 'status': 'PASS',
            'confidence': .99, 'image_quality': 1, 'file_format': 'pdf',
            'issue_date': date(2026, 11, 15),
            'fields': {'성명': '가상신청', '생년월일': '2000-05-15', '양식판독상태': '완전',
                       '현주소시도': '전북', '전입일': '2020-01-01'}, **changes}


def test_confirmed_age_reuses_verified_birth_and_existing_inclusive_rule():
    rule = candidate('age', {'birth_start': '1987-01-01', 'birth_end': '2008-12-31'})
    assert evaluate(application(), [rule], [])[0]['status'] == 'PASS'
    boundary = evaluate(application('2008-12-31'), [rule], [])[0]
    assert boundary['status'] == 'PASS'
    failed = evaluate(application('2009-01-01'), [rule], [])[0]
    assert failed['status'] == 'FAIL' and failed['submission_blocking']
    assert applicant_blockers([failed])[0]['target'] == 'identity'


@pytest.mark.parametrize('defect', ['unconfirmed', 'foreign-engine', 'no-identity', 'unknown-type'])
def test_unconfirmed_unknown_or_missing_identity_never_produces_automatic_pass(defect):
    app = application()
    rule = candidate('age', {'birth_start': '1987-01-01', 'birth_end': '2008-12-31'})
    if defect == 'unconfirmed':
        rule['needs_review'] = True
    elif defect == 'foreign-engine':
        rule['engine_rule'] = 'arbitrary.module.call'
    elif defect == 'no-identity':
        app.identity_json = {}
    else:
        rule['type'] = 'invented'
    assert evaluate(app, [rule], [])[0]['status'] == 'NEEDS_REVIEW'


def test_province_uses_existing_current_sido_rule_with_continuity_and_basis_evidence():
    rule = candidate('residence', {'province': '전북특별자치도', 'city': '', 'basis_date': '2026-11-01'})
    result = evaluate(application(), [rule], [document()])[0]
    assert result['status'] == 'PASS' and result['source_document_ids'] == [31]


@pytest.mark.parametrize('defect', ['low-confidence', 'review', 'failed', 'mismatch', 'missing-birth',
                                  'incomplete', 'corrupt', 'low-quality', 'validation-failure'])
def test_untrusted_document_cannot_establish_residence_or_issue_date(defect):
    doc = document()
    if defect == 'low-confidence': doc['confidence'] = .2
    elif defect == 'review': doc['status'] = 'NEEDS_REVIEW'
    elif defect == 'failed': doc['status'] = 'FAIL'
    elif defect == 'mismatch': doc['fields']['성명'] = '다른가상인'
    elif defect == 'missing-birth': del doc['fields']['생년월일']
    elif defect == 'incomplete': doc['fields']['양식판독상태'] = '불완전'
    elif defect == 'corrupt': doc['is_encrypted'] = True
    elif defect == 'low-quality': doc['image_quality'] = .1
    else: doc['fields']['판독검증실패'] = '합성 불완전 구조'
    rules = [candidate('residence', {'province': '전북특별자치도', 'city': '', 'basis_date': '2026-11-01'}),
             candidate('issue_date', {'mode': 'after_date', 'date': '2026-11-01'})]
    assert all(row['status'] == 'NEEDS_REVIEW' for row in evaluate(application(), rules, [doc]))


def test_city_and_later_move_do_not_silently_inherit_province_eligibility():
    rule = candidate('residence', {'province': '전북특별자치도', 'city': '전주시', 'basis_date': '2026-11-01'})
    assert evaluate(application(), [rule], [document()])[0]['status'] == 'NEEDS_REVIEW'
    rule['values']['city'] = ''
    doc = document()
    doc['fields']['전입일'] = '2026-11-10'
    assert evaluate(application(), [rule], [doc])[0]['status'] == 'NEEDS_REVIEW'


def test_existing_issue_rule_keeps_inclusive_cutoff_and_only_trusted_failure_blocks():
    rule = candidate('issue_date', {'mode': 'after_date', 'date': '2026-11-15'})
    result = evaluate(application(), [rule], [document()])[0]
    assert result['status'] == 'PASS'
    failed = evaluate(application(), [rule], [document(issue_date=date(2026, 11, 14))])[0]
    assert failed['status'] == 'FAIL' and failed['submission_blocking']
    assert applicant_blockers([failed])[0]['target'] == 'upload'
    assert evaluate(application(), [rule], [document(), document(document_id=32, confidence=.1)])[0]['status'] == 'NEEDS_REVIEW'


def test_document_specific_issue_rule_cannot_reject_other_documents_as_global_cutoff():
    rule = candidate('issue_date', {'mode': 'after_date', 'date': '2026-11-15'},
                     quote='주민등록초본은 2026-11-15 이후 발급분만 인정')
    receipt = document(doc_type=str(DocType.PAYMENT_RECEIPT), issue_date=date(2026, 10, 1))
    result = evaluate(application(), [rule], [receipt])[0]
    assert result['status'] == 'NEEDS_REVIEW' and not result['submission_blocking']


def test_conflicting_residence_documents_need_review():
    rule = candidate('residence', {'province': '전북특별자치도', 'city': '', 'basis_date': '2026-11-01'})
    second = document(document_id=32)
    second['fields']['현주소시도'] = '전남'
    assert evaluate(application(), [rule], [document(), second])[0]['status'] == 'NEEDS_REVIEW'


def test_unsupported_income_and_work_without_evidence_remain_for_officer():
    rules = [candidate('income', {'percent': 120, 'operator': '이하', 'household_table': {}}),
             candidate('work_continuity', {'months': 5, 'basis_date': '2026-11-01'})]
    assert all(row['status'] == 'NEEDS_REVIEW' for row in evaluate(application(), rules, []))


def test_checklist_is_never_a_decision_or_an_applicant_payload():
    checklist = candidate('checklist', {'text': '합성 담당자 확인'}, quote='OFFICER ONLY QUOTE', confidence=.8)
    result = evaluate(application(), [checklist], [document()])[0]
    assert result['status'] == 'NEEDS_REVIEW' and not result['submission_blocking']
    assert applicant_blockers([result]) == []
    failed = {'type': 'age', 'status': 'FAIL', 'submission_blocking': True,
              'quote': 'OFFICER ONLY QUOTE', 'confidence': .8, 'engine_rule': 'internal_rule'}
    public = applicant_blockers([failed])
    assert all(key not in str(public) for key in ('OFFICER ONLY QUOTE', 'confidence', 'engine_rule', 'checklist'))


def test_original_documents_and_criteria_are_not_mutated_or_classified_by_filename():
    rule = candidate('residence', {'province': '전북특별자치도', 'city': '', 'basis_date': '2026-11-01'})
    doc = document(file_name='arbitrary-FAIL-name.pdf')
    before = deepcopy((rule, doc))
    assert evaluate(application(), [rule], [doc])[0]['status'] == 'PASS'
    assert (rule, doc) == before



@pytest.mark.parametrize('field', ['confidence', 'image_quality'])
@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), float('-inf'), True, False, None, '0.99', -.1, 1.1])
def test_invalid_raw_confidence_or_quality_is_rejected_before_any_rule_binding(field, invalid):
    from demo.backend.generic_criteria import _trusted
    from demo.backend.rules.identity import identity_of
    from demo.backend.rules.scoring import MEDIAN_INCOME_140
    app = application()
    doc = document(**{field: invalid})
    assert _trusted([doc], identity_of(app.identity_json)) == []
    rules = [candidate('residence', {'province': '전북특별자치도', 'city': '', 'basis_date': '2026-11-01'}),
             candidate('issue_date', {'mode': 'after_date', 'date': '2026-11-01'}),
             candidate('work_continuity', {'months': 5, 'basis_date': '2026-11-01'}),
             candidate('income', {'percent': 140, 'operator': '이하', 'household_table': MEDIAN_INCOME_140,
                                  'premium_months': ['2026-08', '2026-09', '2026-10']})]
    assert all(row['status'] == 'NEEDS_REVIEW' for row in evaluate(app, rules, [doc]))


def test_converted_nonfinite_confidence_is_rejected_again_at_rule_boundary(monkeypatch):
    from types import SimpleNamespace
    from demo.backend import generic_criteria
    monkeypatch.setattr(generic_criteria, 'to_engine_documents', lambda rows: [SimpleNamespace(
        ocr_confidence=float('nan'), image_quality_score=1, is_encrypted_or_corrupted=False)])
    rule = candidate('residence', {'province': '전북특별자치도', 'city': '', 'basis_date': '2026-11-01'})
    assert evaluate(application(), [rule], [document()])[0]['status'] == 'NEEDS_REVIEW'
