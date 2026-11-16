"""Fake-only notice provider tests: no network or applicant payloads."""
from copy import deepcopy
import json

import pytest

from demo.backend.notice_llm import (
    JbaiNoticeProvider, NOTICE_SCHEMA, configured_notice_provider, enrich_notice, notice_payload,
)

KEY = 'synthetic-provider-credential'
PUBLIC = '합성 청년 사업 신청 안내\n공고일: 2026-11-15\n대상: 만18세 이상 39세 이하\n온라인으로 신청하세요.'
QUOTE = '대상: 만18세 이상 39세 이하'
VALUES = {'min_age': 18, 'max_age': 39, 'basis_date': '2026-11-15', 'birth_start': '1986-11-16', 'birth_end': '2008-11-15'}


def draft():
    return {'version': 1, 'source_pages': [{'page': 1, 'text': PUBLIC}],
            'guidance': {'id': 'guidance', 'value': '기존 규칙 안내', 'needs_review': True},
            'criteria': [{'id': 'age_synthetic', 'type': 'age', 'label': QUOTE,
                          'values': deepcopy(VALUES), 'page': 1, 'quote': QUOTE,
                          'engine_rule': 'demo.backend.rules.age_eligibility.assess_age',
                          'confidence': .7, 'needs_review': True}]}


def response(*, guidance=None, values=None, kind='age', quote=QUOTE, page=1):
    return json.dumps({'guidance': guidance, 'criteria': [{'type': kind,
        'values_json': json.dumps(VALUES if values is None else values), 'page': page, 'quote': quote}]})


class FakeProvider:
    name = 'fake'

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def generate(self, purpose, payload):
        self.calls.append((purpose, deepcopy(payload)))
        if self.error:
            raise self.error
        return self.reply


def env(**changes):
    return {'LLM_PROVIDER': 'jbai', 'JBAI_BASE_URL': 'https://text.example.invalid/open-api/v1',
            'JBAI_API_KEY': KEY, 'JBAI_TEXT_MODEL': 'synthetic-text-model', **changes}


def test_default_is_none_even_when_credentials_are_present_without_explicit_provider():
    values = env()
    del values['LLM_PROVIDER']
    assert configured_notice_provider(environ={}).name == 'none'
    assert configured_notice_provider(environ=values).name == 'none'
    assert configured_notice_provider(environ=env(LLM_PROVIDER='none')).name == 'none'


@pytest.mark.parametrize('changes', [
    {'JBAI_BASE_URL': ''}, {'JBAI_API_KEY': ''}, {'JBAI_TEXT_MODEL': ''},
    {'JBAI_BASE_URL': 'http://example.invalid'}, {'JBAI_BASE_URL': 'https://user:password@example.invalid'},
    {'JBAI_BASE_URL': 'https://example.invalid?secret=value'}, {'JBAI_BASE_URL': 'https://example.invalid/#secret'},
    {'JBAI_BASE_URL': 'https://[invalid'}, {'LLM_PROVIDER': 'unknown'},
])
def test_incomplete_or_unsafe_configuration_stays_disabled(changes):
    assert configured_notice_provider(environ=env(**changes)).name == 'none'


def test_public_payload_allowlist_removes_all_extra_fields_at_every_object_level():
    value = draft()
    value.update(identity_json={'name': 'PRIVATE SYNTHETIC PERSON'}, application_id=4,
                 document_fields={'birth': 'SYNTHETIC PRIVATE BIRTH'},
                 ocr_json={'name': 'PRIVATE SYNTHETIC PERSON'})
    value['source_pages'][0]['identity_json'] = {'account': 'SYNTHETIC PRIVATE ACCOUNT'}
    value['source_pages'].append({'page': 2, 'text': {'name': 'SYNTHETIC PRIVATE OBJECT'}})
    projected = notice_payload(value, '합성 공개 설명')
    assert projected == {'notice_pages': [{'page': 1, 'text': PUBLIC}], 'supplemental': '합성 공개 설명'}
    assert all(text not in json.dumps(projected) for text in ('PRIVATE', 'identity_json', 'application_id', 'ocr_json'))


def test_fake_provider_receives_only_notice_text_and_supplemental_not_candidates_or_applicant_fields():
    value = draft()
    value['identity_json'] = {'name': 'PRIVATE SYNTHETIC PERSON'}
    provider = FakeProvider(response())
    result = enrich_notice(value, '공개 설명', provider=provider)
    purpose, payload = provider.calls[0]
    assert purpose == 'notice_analysis'
    assert set(payload) == {'notice_pages', 'supplemental'}
    assert 'PRIVATE' not in json.dumps(provider.calls)
    assert 'criteria' not in payload and 'guidance' not in payload
    assert result['criteria'] == value['criteria']
    assert result['guidance'] == value['guidance']
    assert result['suggestions'][0]['target_id'] == 'age_synthetic'
    assert result['suggestions'][0]['needs_review']


def test_transport_boundary_reprojects_again_and_sends_json_object_and_model():
    calls = []

    def fake_transport(url, headers, body, timeout):
        calls.append((url, headers, body, timeout))
        return {'choices': [{'message': {'content': response()}}]}

    provider = configured_notice_provider(environ=env(), transport=fake_transport)
    assert provider.generate('notice_analysis', {'notice_pages': [{'page': 1, 'text': PUBLIC,
        'identity_json': {'name': 'PRIVATE'}}], 'supplemental': '공개 설명', 'name': 'PRIVATE'}) == response()
    url, headers, body, timeout = calls[0]
    assert url == 'https://text.example.invalid/open-api/v1/chat/completions'
    assert timeout == 30 and headers['Authorization'] == 'Bearer ' + KEY
    assert body['model'] == 'synthetic-text-model'
    assert body['response_format'] == {'type': 'json_object'}
    assert 'PRIVATE' not in json.dumps(body) and KEY not in json.dumps(body)
    assert KEY not in repr(provider)


def test_only_verified_matching_values_are_added_and_original_draft_is_not_mutated():
    value = draft()
    saved = deepcopy(value)
    result = enrich_notice(value, provider=FakeProvider(response()))
    assert value == saved
    assert result['criteria'] == saved['criteria'] and result['guidance'] == saved['guidance']
    assert result['suggestions'] == [{'target_id': 'age_synthetic', 'type': 'age', 'values': VALUES,
        'page': 1, 'quote': QUOTE, 'source': 'fake', 'confidence': 0.0, 'needs_review': True}]


@pytest.mark.parametrize('reply', [
    'not JSON', '[]', '{}', '```json\n{}\n```',
    json.dumps({'guidance': None, 'criteria': [], 'unapproved_extra': 'x'}),
    json.dumps({'guidance': None, 'criteria': [{'type': 'new_rule', 'values_json': '{}', 'page': 1, 'quote': QUOTE}]}),
    json.dumps({'guidance': None, 'criteria': [{'type': 'age', 'values_json': {}, 'page': 1, 'quote': QUOTE}]}),
])
def test_invalid_json_or_schema_returns_unchanged_rule_draft(reply):
    value = draft()
    assert enrich_notice(value, provider=FakeProvider(reply)) == value


@pytest.mark.parametrize('proposal', [
    {'quote': '인용이 없는 문장'}, {'page': 99}, {'page': True},
    {'values': {**VALUES, 'min_age': 17}}, {'values': {**VALUES, 'unsupported': True}},
    {'kind': 'residence'}, {'quote': '공고일: 2026-11-15'},
])
def test_conflicting_values_unrelated_citation_and_nonexistent_page_cannot_add_suggestions(proposal):
    value = draft()
    assert enrich_notice(value, provider=FakeProvider(response(**proposal))) == value


def test_checklist_candidate_never_becomes_automatic_due_to_provider_confirmation():
    value = draft()
    value['criteria'][0].update(type='checklist', engine_rule=None)
    assert enrich_notice(value, provider=FakeProvider(response())) == value


def test_provider_written_guidance_fills_the_guidance_field_but_stays_unconfirmed():
    value = draft()
    saved = deepcopy(value)
    text = '합성 청년 사업 신청 안내입니다.\n대상은 만 18세 이상 39세 이하입니다.\n\n\n\n온라인으로 신청하세요.'
    guide = {'text': text, 'page': 1, 'quote': QUOTE}
    result = enrich_notice(value, provider=FakeProvider(response(guidance=guide)))
    assert value == saved
    assert result['guidance'] == {'id': 'guidance', 'value': '합성 청년 사업 신청 안내입니다.\n대상은 만 18세 이상 39세 이하입니다.\n\n온라인으로 신청하세요.',
                                  'page': 1, 'quote': QUOTE, 'source': 'fake', 'confidence': 0.6,
                                  'needs_review': True, 'ai_drafted': True}
    assert result['criteria'] == saved['criteria']
    assert all(row['target_id'] != 'guidance' for row in result['suggestions'])


@pytest.mark.parametrize('guide', [
    # A number that is not in the public notice (invented age range or amount).
    {'text': '만 19세 이상 45세 이하 청년이 신청할 수 있습니다.', 'page': 1, 'quote': QUOTE},
    {'text': '월 300,000원을 지원합니다.', 'page': 1, 'quote': QUOTE},
    # The citation must be verbatim on its page.
    {'text': '온라인으로 신청하세요.', 'page': 1, 'quote': '인용이 없는 문장'},
    {'text': '온라인으로 신청하세요.', 'page': 2, 'quote': QUOTE},
    {'text': '```온라인```', 'page': 1, 'quote': QUOTE},
    {'text': '짧음', 'page': 1, 'quote': QUOTE},
])
def test_guidance_with_invented_numbers_or_bad_citation_keeps_local_guidance(guide):
    value = draft()
    reply = json.dumps({'guidance': guide, 'criteria': []})
    assert enrich_notice(value, provider=FakeProvider(reply)) == value


@pytest.mark.parametrize('error', [TimeoutError('SYNTHETIC SECRET'), ValueError('SYNTHETIC SECRET')])
def test_provider_exceptions_silently_return_original_and_never_leak_error_values(error, caplog, capsys):
    value = draft()
    result = enrich_notice(value, provider=FakeProvider(error=error))
    assert result == value
    assert 'SYNTHETIC SECRET' not in caplog.text + capsys.readouterr().out + repr(result)


def test_transport_timeout_returns_rules_without_logging_request_or_key(caplog, capsys):
    def timeout(*args):
        raise TimeoutError(KEY)
    provider = configured_notice_provider(environ=env(), transport=timeout)
    value = draft()
    assert enrich_notice(value, provider=provider) == value
    assert KEY not in caplog.text + capsys.readouterr().out


def test_none_provider_and_no_text_never_make_network_calls():
    provider = FakeProvider(response())
    value = draft()
    value['source_pages'] = [{'page': 1, 'text': ''}]
    assert enrich_notice(value, '공개 설명만 있음', provider=provider) == value
    assert provider.calls == []
    assert enrich_notice(draft(), provider=configured_notice_provider(environ={})) == draft()


def test_payload_size_limits_and_invalid_object_values_are_bounded():
    value = notice_payload({'source_pages': [{'page': 1, 'text': 'a' * 250_000}]}, 'x' * 5000)
    assert len(value['notice_pages'][0]['text']) == 200_000 and len(value['supplemental']) == 4000
    assert notice_payload({'source_pages': [{'page': True, 'text': 'bad'}, {'page': 0, 'text': 'bad'}]}, {'private': 'value'}) == {'notice_pages': [], 'supplemental': ''}
    provider = FakeProvider(response())
    assert enrich_notice(draft(), 'a' * 4001, provider=provider) == draft() and provider.calls == []


def test_direct_provider_rejects_other_purpose_or_missing_text_without_transport():
    calls = []
    provider = JbaiNoticeProvider('https://example.invalid', env(), lambda *args: calls.append(args))
    assert provider.generate('review', {'name': 'PRIVATE'}) is None
    assert provider.generate('notice_analysis', {'name': 'PRIVATE'}) is None
    assert calls == []


def test_supplemental_evidence_can_suggest_only_preexisting_supported_candidate():
    value = draft()
    value['criteria'][0].update(page=None, source='supplemental')
    proposal = response(page=None)
    result = enrich_notice(value, QUOTE, provider=FakeProvider(proposal))
    assert result['suggestions'][0]['page'] is None
    assert enrich_notice(value, '다른 공개 설명', provider=FakeProvider(proposal)) == value


@pytest.mark.parametrize('text', ['신청하면 자동 선정됩니다.', '누구나 지원받을 수 있습니다.', '신청자 전원 지원합니다.'])
def test_guidance_promising_selection_the_notice_does_not_promise_is_discarded(text):
    value = draft()
    reply = json.dumps({'guidance': {'text': text, 'page': 1, 'quote': QUOTE}, 'criteria': []})
    assert enrich_notice(value, provider=FakeProvider(reply)) == value


def test_guidance_may_repeat_wording_the_notice_itself_uses():
    value = draft()
    value['source_pages'][0]['text'] += '\n누구나 신청할 수 있습니다.'
    reply = json.dumps({'guidance': {'text': '누구나 온라인으로 신청할 수 있습니다.', 'page': 1, 'quote': QUOTE}, 'criteria': []})
    assert enrich_notice(value, provider=FakeProvider(reply))['guidance']['ai_drafted'] is True
