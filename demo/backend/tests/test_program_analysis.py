"""Synthetic notice-to-publication API and strict review-boundary coverage."""
from copy import deepcopy
from datetime import date
import json

import pytest

from demo.backend import models
from demo.backend.api import documents
from demo.backend.api.program_analysis import analysis_blockers, legacy_analysis, validate_analysis
from demo.backend.notice_analysis import analyze_notice
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_generic_programs import client, fill, pdf, start, TODAY
from demo.backend.tests.test_notice_analysis import public_pdf


@pytest.fixture(autouse=True)
def offline_notice_provider(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')


def notice():
    return public_pdf(['합성 청년 지원사업 모집', '공고일: 2026.11.01',
        '신청 기간: 2026.11.01 ~ 2026.12.15', '지원 대상: 1987.1.1 ~ 2008.12.31 출생자',
        '제출 서류: 면접용 사진사본', '신청 방법: 온라인 신청', '문의: 합성센터'])


def checked(analysis):
    result = deepcopy(analysis)
    # Ambiguous neighboring birth-date ranges intentionally leave the period
    # unfilled. The officer supplies the visible printed application range.
    if not all(result['period']['value'].values()):
        result['period']['value'] = {'apply_start': '2026-11-01', 'apply_end': '2026-12-15'}
    for name in ('title', 'period', 'guidance'):
        result[name]['needs_review'] = False
    for name in ('required_docs', 'criteria'):
        for item in result[name]:
            item['needs_review'] = False
    return result


def upload(client):
    result = client.post('/api/officer/programs/analyze', data={'supplemental': '합성 공개 부가 설명'},
        files=[('notice_pdf', ('public-notice.pdf', notice(), 'application/pdf')),
               ('forms_pdfs', ('public-form.pdf', pdf(True), 'application/pdf'))])
    assert result.status_code == 201, result.text
    return result.json()


def test_upload_uses_fake_notice_provider_with_only_public_text_and_unconfirmed_suggestions(client, monkeypatch):
    from demo.backend import notice_llm
    captured = []
    class FakeProvider:
        name = 'fake'
        def generate(self, purpose, payload):
            captured.append((purpose, payload))
            return json.dumps({'guidance': {'text': '신청 방법: 온라인 신청', 'page': 1,
                'quote': '신청 방법: 온라인 신청'}, 'criteria': []})
    monkeypatch.setattr(notice_llm, 'configured_notice_provider', lambda: FakeProvider())
    data = upload(client)
    assert len(captured) == 1 and captured[0][0] == 'notice_analysis'
    assert set(captured[0][1]) == {'notice_pages', 'supplemental'}
    assert all(set(page) == {'page', 'text'} for page in captured[0][1]['notice_pages'])
    original = analyze_notice(notice(), '합성 공개 부가 설명')
    assert data['analysis']['guidance'] == original['guidance']
    suggestion = data['analysis']['suggestions'][0]
    assert suggestion['needs_review'] is True and suggestion['confidence'] == 0
    assert suggestion['quote'] == '신청 방법: 온라인 신청'


def confirm_forms(client, workspace):
    posting_id = workspace['posting']['id']
    for form in workspace['forms']:
        layout = deepcopy(form['layout'])
        assert layout['fields']
        for field in layout['fields'].values():
            field['needs_review'] = False
        path = f'/api/officer/postings/{posting_id}/workspace/forms/{form["id"]}'
        saved = client.put(path + '/layout', json={'layout': layout})
        assert saved.status_code == 200, saved.text
        assert client.post(path + '/confirm').status_code == 200


def test_validator_accepts_actual_provenance_and_manual_items_without_invented_quotes():
    original = analyze_notice(notice())
    edited = checked(original)
    edited['criteria'].append({'id': 'manual_commitment', 'type': 'checklist', 'label': '확약서 확인',
        'values': {'text': '담당자 확인'}, 'engine_rule': None, 'page': None, 'quote': '',
        'confidence': 0, 'needs_review': False})
    result = validate_analysis(edited, original)
    assert result['criteria'][-1]['source'] == 'manual' and result['criteria'][-1]['quote'] == ''
    assert result['criteria'][-1]['type'] == 'checklist' and result['criteria'][-1]['engine_rule'] is None


@pytest.mark.parametrize('defect', ['source-rewrite', 'invented-quote', 'unknown-page', 'engine-injection', 'duplicate-id',
                                  'unknown-kind', 'age-extra-value', 'bool-confirmation', 'unknown-slot', 'new-nonmanual-id'])
def test_validator_rejects_forged_sources_identifiers_types_values_and_rules(defect):
    original = analyze_notice(notice())
    edited = checked(original)
    if defect == 'source-rewrite':
        edited['source_pages'][0]['text'] = '공격자가 바꾼 인용'
    elif defect == 'invented-quote':
        edited['title']['quote'] = '실제 공고문에 없는 문장'
    elif defect == 'unknown-page':
        edited['title']['page'] = 99
    elif defect == 'engine-injection':
        edited['criteria'][0]['engine_rule'] = 'arbitrary.module.execute'
    elif defect == 'duplicate-id':
        edited['criteria'].append(deepcopy(edited['criteria'][0]))
    elif defect == 'unknown-kind':
        edited['criteria'][0]['type'] = 'invented_rule'
    elif defect == 'age-extra-value':
        edited['criteria'][0]['values']['arbitrary_internal_key'] = 1
    elif defect == 'bool-confirmation':
        edited['title']['needs_review'] = 0
    elif defect == 'unknown-slot':
        edited['required_docs'][0]['slot_key'] = 'invented_slot'
    else:
        edited['criteria'][0]['id'] = 'made_up_existing_identifier'
    with pytest.raises(Exception) as caught:
        validate_analysis(edited, original)
    assert getattr(caught.value, 'status_code', None) == 422


def test_old_managed_draft_can_opt_into_manual_four_section_editor_without_fake_source():
    posting = models.ProgramPosting(id=17, title='저장된 합성 사업', apply_start=TODAY,
        apply_end=date(2026, 12, 31), guidance_text='저장된 합성 안내',
        template_json={'workflow_version': 1, 'required_docs': ['resident_abstract']})
    draft = legacy_analysis(posting)
    assert draft['source_pages'] == [] and all(draft[name]['needs_review'] for name in ('title', 'period', 'guidance'))
    assert draft['required_docs'][0]['slot_key'] == 'resident_abstract'
    clean = validate_analysis(draft, draft)
    assert clean['title']['value'] == posting.title


def test_secondary_basis_evidence_survives_validation_and_confirmation():
    original = analyze_notice(public_pdf(['합성 청년 지원사업', '공고일: 2026.11.15',
                                         '대상: 만 18세 이상 39세 이하']))
    age = next(item for item in original['criteria'] if item['type'] == 'age')
    assert age['basis_evidence']['quote'] == '공고일: 2026.11.15'
    clean = validate_analysis(checked(original), original)
    saved = next(item for item in clean['criteria'] if item['type'] == 'age')
    assert saved['basis_evidence']['quote'] == age['basis_evidence']['quote']
    assert saved['basis_evidence']['page'] == 1 and not saved['basis_evidence']['needs_review']
    forged = checked(original)
    next(item for item in forged['criteria'] if item['type'] == 'age')['basis_evidence']['quote'] = '없는 인용'
    with pytest.raises(Exception) as caught:
        validate_analysis(forged, original)
    assert getattr(caught.value, 'status_code', None) == 422


def test_one_shot_analyze_review_publish_submit_officer_detail_and_public_allowlists(client, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'none')
    data = upload(client)
    posting_id = data['posting']['id']
    assert data['authoring_version'] == 2
    assert data['analysis']['title']['needs_review']
    base = f'/api/officer/postings/{posting_id}'
    confirm_forms(client, data)
    assert client.post(base + '/publish').status_code == 409
    analysis = checked(data['analysis'])
    analysis['title']['value'] = '담당자가 수정한 합성 사업'
    analysis['criteria'].append({'id': 'manual_pledge', 'type': 'checklist', 'label': '확약사항 원본 확인',
        'values': {'text': '확약 여부'}, 'engine_rule': None, 'page': None, 'quote': '',
        'confidence': 0, 'needs_review': False})
    result = client.put(base + '/analysis', json={'analysis': analysis})
    assert result.status_code == 200, result.text
    published = client.post(base + '/publish')
    assert published.status_code == 200, published.text
    row, _form, layout = start(client, published.json())
    fill(client, row, layout)
    monkeypatch.setattr(documents, 'read_document', lambda path, expected: OcrResult(
        detected_doc_type=DocType.ID_PHOTO_COPY, confidence=.99, image_quality=1,
        issue_date=TODAY, fields={'성명': '가상신청', '생년월일': '2000-05-15', '양식판독상태': '완전'}, tier='synthetic', engine='synthetic'))
    response = client.post(f'/api/applications/{row["id"]}/documents', data={'slot_key': 'photo_1_photo'},
        files={'file': ('content-is-synthetic.pdf', pdf(), 'application/pdf')})
    assert response.status_code == 200, response.text
    response = client.post(f'/api/applications/{row["id"]}/submit')
    assert response.status_code == 200, response.text
    listing = client.get('/api/officer/applications', params={'program': f'posting_{posting_id}', 'queue': 'needs_check'})
    assert listing.status_code == 200 and listing.json()['total'] == 1
    detail = client.get(f'/api/officer/programs/{posting_id}/applications/{row["id"]}')
    assert detail.status_code == 200, detail.text
    criteria = detail.json()['criteria']
    assert next(item for item in criteria if item['type'] == 'age')['result'] == 'PASS'
    assert next(item for item in criteria if item['type'] == 'checklist')['requires_check']
    forbidden = {'quote', 'confidence', 'checklist', 'criteria', 'criteria_results', 'engine_rule'}
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(child) for child in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(child) for child in value))
        return set()
    for url in (f'/api/postings/{posting_id}', f'/api/applications/{row["id"]}',
                f'/api/applications/{row["id"]}/program', f'/api/applications/{row["id"]}/required-documents',
                f'/api/applications/{row["id"]}/final-check', f'/api/applications/{row["id"]}/status'):
        public = client.get(url)
        assert public.status_code == 200, public.text
        assert not keys(public.json()) & forbidden, (url, keys(public.json()) & forbidden)


def test_legacy_patch_cannot_bypass_confirmed_analysis_publish_gate(client):
    data = upload(client)
    posting_id = data['posting']['id']
    confirm_forms(client, data)
    base = f'/api/officer/postings/{posting_id}'
    assert client.put(base + '/analysis', json={'analysis': checked(data['analysis'])}).status_code == 200
    assert client.patch(base, json={'guidance_text': '다른 경로로 바꾼 안내'}).status_code in {200, 409}
    assert client.post(base + '/publish').status_code == 409


def test_manual_unknown_document_is_review_only_and_required_flag_is_preserved(client, monkeypatch):
    data = upload(client)
    posting_id = data['posting']['id']
    confirm_forms(client, data)
    analysis = checked(data['analysis'])
    analysis['required_docs'] = [{'id': 'manual_recommendation', 'type': 'document', 'slot_key': None,
        'label': '기타 서류', 'original_label': '합성 추천서', 'required': True,
        'page': None, 'quote': '', 'confidence': 0, 'needs_review': False}]
    base = f'/api/officer/postings/{posting_id}'
    saved = client.put(base + '/analysis', json={'analysis': analysis})
    assert saved.status_code == 200, saved.text
    result = client.post(base + '/publish')
    assert result.status_code == 200, result.text
    row, _form, layout = start(client, result.json())
    fill(client, row, layout)
    before = client.get(f'/api/applications/{row["id"]}/final-check').json()
    assert not before['can_submit']
    items = client.get(f'/api/applications/{row["id"]}/required-documents').json()['items']
    req = next(item for item in items if item['slot_key'].startswith('other_'))
    reader_calls = []
    def reader(path, expected):
        reader_calls.append((path, expected))
        return OcrResult(detected_doc_type=DocType.ID_PHOTO_COPY, confidence=1, image_quality=1)
    monkeypatch.setattr(documents, 'read_document', reader)
    uploaded = client.post(f'/api/applications/{row["id"]}/documents', data={'slot_key': req['slot_key']},
        files={'file': ('any-name.pdf', pdf(), 'application/pdf')})
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()['status'] == 'NEEDS_REVIEW'
    assert reader_calls == []
    assert client.post(f'/api/applications/{row["id"]}/submit').status_code == 200


def test_one_shot_upload_enforces_forms_and_supplemental_limits(client):
    missing = client.post('/api/officer/programs/analyze', files={'notice_pdf': ('notice.pdf', notice(), 'application/pdf')})
    assert missing.status_code == 422
    excessive = client.post('/api/officer/programs/analyze', data={'supplemental': 'x' * 4001},
        files=[('notice_pdf', ('notice.pdf', notice(), 'application/pdf')),
               ('forms_pdfs', ('form.pdf', pdf(True), 'application/pdf'))])
    assert excessive.status_code == 422


def test_pending_incomplete_criterion_can_save_draft_but_cannot_publish_or_confirm(client):
    data = upload(client)
    posting_id = data['posting']['id']
    confirm_forms(client, data)
    analysis = checked(data['analysis'])
    rule = next(item for item in analysis['criteria'] if item['type'] == 'age')
    rule.update(values={}, needs_review=True, engine_rule=None)
    path = f'/api/officer/postings/{posting_id}'
    saved = client.put(path + '/analysis', json={'analysis': analysis})
    assert saved.status_code == 200, saved.text
    pending = next(item for item in saved.json()['analysis']['criteria'] if item['id'] == rule['id'])
    assert pending['type'] == 'age' and pending['engine_rule'] is None and pending['needs_review']
    assert client.post(path + '/publish').status_code == 409
    rule['needs_review'] = False
    rejected = client.put(path + '/analysis', json={'analysis': analysis})
    assert rejected.status_code == 422



def test_legacy_patch_cannot_change_published_v2_title_guidance_or_dates(client):
    data = upload(client)
    posting_id = data['posting']['id']
    confirm_forms(client, data)
    base = f'/api/officer/postings/{posting_id}'
    saved = client.put(base + '/analysis', json={'analysis': checked(data['analysis'])})
    assert saved.status_code == 200, saved.text
    assert client.post(base + '/publish').status_code == 200
    public_url = f'/api/postings/{posting_id}'
    before = client.get(public_url).json()
    for patch in ({'title': '게시 후 미확정 이름'}, {'guidance_text': '게시 후 미확정 안내'},
                  {'apply_start': '2026-11-16'}, {'apply_end': '2026-12-31'}):
        response = client.patch(base, json=patch)
        assert response.status_code == 409, response.text
        assert client.get(public_url).json() == before
