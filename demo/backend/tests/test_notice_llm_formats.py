"""JBAI_RESPONSE_FORMAT modes and the single fallback: fake transport only."""
from copy import deepcopy
from email.message import Message
import json
from urllib.error import HTTPError

import pytest

from demo.backend.notice_llm import (
    JSON_ONLY, NOTICE_SCHEMA, RESPONSE_FORMATS, configured_notice_provider, enrich_notice, response_format,
)
from demo.backend.tests.test_notice_llm import KEY, PUBLIC, QUOTE, VALUES, draft, env, response


def reply(content):
    return {'choices': [{'message': {'content': content}}]}


class Transport:
    """Answers by response mode: a value, an exception, or a callable."""

    def __init__(self, **answers):
        self.answers, self.calls = answers, []

    def __call__(self, url, headers, body, timeout):
        mode = mode_of(body)
        self.calls.append((mode, deepcopy(body), timeout))
        answer = self.answers.get(mode, reply(response()))
        if isinstance(answer, Exception):
            raise answer
        return answer


def mode_of(body):
    kind = body.get('response_format', {}).get('type')
    return kind if kind in ('json_schema', 'json_object') else 'prompt'


def provider(transport, mode=None):
    changes = {} if mode is None else {'JBAI_RESPONSE_FORMAT': mode}
    return configured_notice_provider(environ=env(**changes), transport=transport)


@pytest.mark.parametrize(('value', 'expected'), [
    (None, 'json_schema'), ('', 'json_schema'), ('json_schema', 'json_schema'), ('JSON_OBJECT', 'json_object'),
    (' prompt ', 'prompt'), ('xml', 'json_schema'),
])
def test_response_format_setting_defaults_to_strict_json_schema(value, expected):
    values = env() if value is None else env(JBAI_RESPONSE_FORMAT=value)
    assert response_format(values) == expected


def test_default_still_sends_strict_schema_first_and_provider_default_stays_none():
    transport = Transport()
    assert enrich_notice(draft(), provider=provider(transport))['suggestions']
    assert [mode for mode, _, _ in transport.calls] == ['json_schema']
    assert transport.calls[0][1]['response_format'] == {'type': 'json_schema', 'json_schema': NOTICE_SCHEMA}
    values = env()
    del values['LLM_PROVIDER']
    assert configured_notice_provider(environ={**values, 'JBAI_RESPONSE_FORMAT': 'json_object'}).name == 'none'


@pytest.mark.parametrize('mode', RESPONSE_FORMATS)
def test_each_mode_builds_its_request_with_the_same_public_payload(mode):
    transport = Transport()
    enrich_notice(draft(), '합성 공개 설명', provider=provider(transport, mode))
    (sent, body, timeout), = transport.calls
    assert sent == mode and timeout == 10.0
    assert (JSON_ONLY in body['messages'][0]['content']) is (mode != 'json_schema')
    assert ('response_format' in body) is (mode != 'prompt')
    assert json.loads(body['messages'][1]['content']) == {'notice_pages': [{'page': 1, 'text': PUBLIC}],
                                                          'supplemental': '합성 공개 설명'}


@pytest.mark.parametrize(('primary', 'second', 'failure'), [
    ('json_schema', 'json_object', TimeoutError('synthetic')),
    ('json_schema', 'json_object', HTTPError('https://example.invalid', 400, 'bad', Message(), None)),
    ('json_schema', 'json_object', reply('```json\n{}\n```')),
    ('json_object', 'prompt', reply('not JSON')),
    ('json_object', 'prompt', TimeoutError('synthetic')),
])
def test_failed_or_ignored_format_falls_back_exactly_once(primary, second, failure):
    transport = Transport(**{primary: failure})
    result = enrich_notice(draft(), provider=provider(transport, primary))
    assert [mode for mode, _, _ in transport.calls] == [primary, second]
    assert result['suggestions'][0]['target_id'] == 'age_synthetic'
    assert result['suggestions'][0]['needs_review'] is True


def test_fallback_happens_only_once_and_then_rules_are_kept(caplog, capsys):
    transport = Transport(json_schema=TimeoutError(KEY), json_object=TimeoutError(KEY), prompt=reply(response()))
    value = draft()
    assert enrich_notice(value, provider=provider(transport)) == value
    assert [mode for mode, _, _ in transport.calls] == ['json_schema', 'json_object']
    transport = Transport(prompt=TimeoutError(KEY))
    assert enrich_notice(value, provider=provider(transport, 'prompt')) == value
    assert [mode for mode, _, _ in transport.calls] == ['prompt']
    assert KEY not in caplog.text + capsys.readouterr().out
    assert KEY not in repr(provider(transport))


def test_working_primary_mode_makes_no_extra_call():
    transport = Transport()
    enrich_notice(draft(), provider=provider(transport, 'json_object'))
    assert [mode for mode, _, _ in transport.calls] == ['json_object']


@pytest.mark.parametrize('mode', RESPONSE_FORMATS)
@pytest.mark.parametrize('proposal', [
    {'quote': '인용이 없는 문장'}, {'page': 99}, {'values': {**VALUES, 'min_age': 17}},
    {'values': {'min_age': 18, 'max_age': 39}}, {'kind': 'residence'},
])
def test_each_mode_discards_bad_quote_value_or_type_and_keeps_the_rule_draft(mode, proposal):
    transport = Transport(**{name: reply(response(**proposal)) for name in RESPONSE_FORMATS})
    value = draft()
    assert enrich_notice(value, provider=provider(transport, mode)) == value


@pytest.mark.parametrize('mode', RESPONSE_FORMATS)
def test_each_mode_rejects_out_of_kind_type_and_unapproved_fields(mode):
    for content in (json.dumps({'guidance': None, 'criteria': [
                        {'type': 'new_rule', 'values_json': json.dumps(VALUES), 'page': 1, 'quote': QUOTE}]}),
                    json.dumps({'guidance': None, 'criteria': [], 'extra': 'x'})):
        transport = Transport(**{name: reply(content) for name in RESPONSE_FORMATS})
        value = draft()
        assert enrich_notice(value, provider=provider(transport, mode)) == value


@pytest.mark.parametrize('mode', RESPONSE_FORMATS)
def test_each_mode_accepts_only_the_same_verified_suggestion(mode):
    transport = Transport(**{name: reply(response()) for name in RESPONSE_FORMATS})
    result = enrich_notice(draft(), provider=provider(transport, mode))
    assert result['suggestions'] == [{'target_id': 'age_synthetic', 'type': 'age', 'values': VALUES,
        'page': 1, 'quote': QUOTE, 'source': 'jbai', 'confidence': 0.0, 'needs_review': True}]
    assert result['criteria'] == draft()['criteria']
