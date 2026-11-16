"""Provider stability: outcome records, time budget, tolerant reading, stated-value matching.

Fake transports and a fake clock only: no network, no real credentials.
"""
from email.message import Message
import json
import logging
from urllib.error import HTTPError, URLError

import pytest

from demo.backend import llm_drafts
from demo.backend.llm_drafts import OUTCOMES, failure_outcome, log_call
from demo.backend.notice_llm import (
    BUDGET, MIN_SECOND_CALL, SEND_MAX_TEXT, STATED_KEYS, SYSTEM_PROMPT, TIMEOUT, JbaiNoticeProvider,
    budget_seconds, enrich_notice, guidance_check, notice_payload, send_limit, values_match,
)
from demo.backend.notice_analysis import analyze_notice
from demo.backend.tests.test_notice_llm import KEY, PUBLIC, QUOTE, VALUES, FakeProvider, draft, env, response
from demo.backend.tools import probe_jbai_notice as probe

BASE = 'https://text.example.invalid/open-api/v1'
SECRET = 'SYNTHETIC-EXCEPTION-TEXT'
BODY_MARK = 'SYNTHETIC-BODY-MARK'
LOGGER = 'demo.backend.llm'


def reply(content, **choice):
    return {'choices': [{'message': {'content': content}, **choice}]}


def lines(caplog):
    return [record.getMessage() for record in caplog.records if record.name == LOGGER]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def timed(clock, *steps):
    """A transport whose n-th call costs steps[n][0] seconds and then returns or raises steps[n][1]."""
    calls = []

    def transport(url, headers, body, timeout):
        cost, answer = steps[len(calls)]
        calls.append({'mode': body.get('response_format', {}).get('type', 'prompt'), 'timeout': timeout})
        clock.now += cost
        if isinstance(answer, Exception):
            raise answer
        return answer
    return transport, calls


def provider(transport, clock=None, **changes):
    extra = {} if clock is None else {'clock': clock}
    return JbaiNoticeProvider(BASE, env(**changes), transport, **extra)


# ── outcome vocabulary ───────────────────────────────────────────────────────

@pytest.mark.parametrize(('error', 'expected'), [
    (HTTPError(BASE, 400, SECRET, Message(), None), 'http_4xx'),
    (HTTPError(BASE, 404, SECRET, Message(), None), 'http_4xx'),
    (HTTPError(BASE, 429, SECRET, Message(), None), 'http_429'),
    (HTTPError(BASE, 500, SECRET, Message(), None), 'http_5xx'),
    (HTTPError(BASE, 503, SECRET, Message(), None), 'http_5xx'),
    (HTTPError(BASE, 302, SECRET, Message(), None), 'bad_transport'),
    (TimeoutError(SECRET), 'timeout'),
    (URLError(TimeoutError(SECRET)), 'timeout'),
    (URLError(SECRET), 'network'),
    (ConnectionResetError(SECRET), 'network'),
    (ValueError(SECRET), 'bad_transport'),
    (json.JSONDecodeError(SECRET, 'x', 0), 'bad_transport'),
    (KeyError(SECRET), 'no_content'),
    (RuntimeError(SECRET), 'bad_transport'),
])
def test_failures_are_named_by_type_and_status_only(error, expected):
    assert failure_outcome(error) == expected and expected in OUTCOMES


def test_log_line_carries_only_fixed_words_and_numbers(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    log_call('notice_analysis', 'json_object', 1, 'ok', 3.21)
    log_call(SECRET, SECRET, SECRET, SECRET, SECRET)
    assert lines(caplog) == [
        'llm_call purpose=notice_analysis mode=json_object attempt=1 outcome=ok seconds=3.2',
        'llm_call purpose=other mode=other attempt=0 outcome=bad_transport seconds=0.0']
    assert [record.levelno for record in caplog.records] == [logging.INFO, logging.WARNING]
    assert SECRET not in caplog.text


@pytest.mark.parametrize(('answer', 'outcome'), [
    (TimeoutError(SECRET), 'timeout'),
    (HTTPError(BASE, 500, SECRET, Message(), None), 'http_5xx'),
    ({'unexpected': BODY_MARK}, 'no_content'),
    (reply(''), 'no_content'),
    (reply(None), 'no_content'),
    (reply('x' * 32_001), 'too_large'),
    (reply(BODY_MARK + ' 설명만 있고 JSON 은 없음'), 'bad_shape'),
    (reply('{"guidance": null, "criteria": [{"type": "age", "values_js', finish_reason='length'), 'truncated'),
])
def test_each_failure_is_recorded_and_then_the_single_fallback_answers(answer, outcome, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    clock = Clock()
    transport, calls = timed(clock, (0.5, answer), (0.5, reply(response())))
    result = enrich_notice(draft(), provider=provider(transport, clock))
    assert [call['mode'] for call in calls] == ['json_object', 'prompt']
    assert result['suggestions'][0]['target_id'] == 'age_synthetic'
    assert lines(caplog) == [
        f'llm_call purpose=notice_analysis mode=json_object attempt=1 outcome={outcome} seconds=0.5',
        'llm_call purpose=notice_analysis mode=prompt attempt=2 outcome=ok seconds=0.5',
        'llm_result purpose=notice_analysis guidance=none criteria_received=1 criteria_accepted=1']
    text = caplog.text
    assert all(word not in text for word in (SECRET, BODY_MARK, KEY, 'example.invalid', 'synthetic-text-model', PUBLIC))


def test_a_valid_answer_cut_at_the_token_limit_is_still_read():
    clock = Clock()
    transport, calls = timed(clock, (1.0, reply(response(), finish_reason='length')))
    assert enrich_notice(draft(), provider=provider(transport, clock))['suggestions']
    assert len(calls) == 1


@pytest.mark.parametrize(('guide', 'state'), [
    ({'text': '합성 청년 사업 신청 안내입니다. 온라인으로 신청하세요.', 'page': 1, 'quote': QUOTE}, 'accepted'),
    ({'text': '월 300,000원을 지원합니다.', 'page': 1, 'quote': QUOTE}, 'number'),
    ({'text': '신청하면 자동 선정됩니다.', 'page': 1, 'quote': QUOTE}, 'promise'),
    ({'text': '온라인으로 신청하세요.', 'page': 1, 'quote': '인용이 없는 문장'}, 'quote'),
    ({'text': '짧음', 'page': 1, 'quote': QUOTE}, 'length'),
    ('안내문이 객체가 아님', 'shape'),
    (None, 'none'),
])
def test_validation_summary_names_why_a_guidance_was_dropped(guide, state, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    content = json.dumps({'guidance': guide, 'criteria': []}, ensure_ascii=False)
    result = enrich_notice(draft(), provider=FakeProvider(content))
    assert lines(caplog) == [f'llm_result purpose=notice_analysis guidance={state} criteria_received=0 criteria_accepted=0']
    assert result['guidance'].get('ai_drafted', False) is (state == 'accepted')
    if isinstance(guide, dict):
        assert guidance_check(guide, notice_payload(draft()))[1] == state


def test_disabled_or_failed_provider_writes_no_validation_summary(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    assert enrich_notice(draft(), provider=FakeProvider(None)) == draft()
    assert enrich_notice(draft(), provider=llm_drafts.NoneProvider()) == draft()
    assert lines(caplog) == []


def test_text_draft_provider_records_its_outcome_without_changing_its_result(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    values = {'PROGRAM_LLM_PROVIDER': 'jbai', 'PROGRAM_LLM_ENABLED': 'true', 'JBAI_BASE_URL': BASE, 'JBAI_API_KEY': KEY}
    answers = iter([reply(' 합성 안내 초안 '), TimeoutError(SECRET), reply('   ')])

    def transport(url, headers, body, timeout):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer
    selected = llm_drafts.configured_provider(environ=values, transport=transport)
    assert selected.generate('guidance', {'title': '합성 사업'}) == '합성 안내 초안'
    assert selected.generate('guidance', {'title': '합성 사업'}) is None
    assert selected.generate('review', {'rules': [{'code': 'MISSING_DOCUMENT'}]}) is None
    assert [line.rsplit(' seconds=', 1)[0] for line in lines(caplog)] == [
        'llm_call purpose=guidance mode=text attempt=1 outcome=ok',
        'llm_call purpose=guidance mode=text attempt=1 outcome=timeout',
        'llm_call purpose=review mode=text attempt=1 outcome=no_content']
    assert SECRET not in caplog.text and KEY not in caplog.text


# ── time budget ──────────────────────────────────────────────────────────────

def test_worst_case_is_bounded_by_the_budget():
    clock = Clock()
    transport, calls = timed(clock, (30.0, TimeoutError(SECRET)), (10.0, TimeoutError(SECRET)))
    started = clock.now
    assert enrich_notice(draft(), provider=provider(transport, clock)) == draft()
    assert [call['timeout'] for call in calls] == [TIMEOUT, BUDGET - TIMEOUT]
    assert clock.now - started <= BUDGET


def test_second_call_is_skipped_when_too_little_budget_remains(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    clock = Clock()
    slow = BUDGET - MIN_SECOND_CALL + 1.0
    transport, calls = timed(clock, (slow, HTTPError(BASE, 503, SECRET, Message(), None)), (0.1, reply(response())))
    assert enrich_notice(draft(), provider=provider(transport, clock)) == draft()
    assert len(calls) == 1
    assert lines(caplog)[-1] == 'llm_call purpose=notice_analysis mode=prompt attempt=2 outcome=budget_exhausted seconds=0.0'


def test_fast_failure_leaves_the_full_timeout_for_the_fallback():
    clock = Clock()
    transport, calls = timed(clock, (0.2, HTTPError(BASE, 500, SECRET, Message(), None)), (3.0, reply(response())))
    assert enrich_notice(draft(), provider=provider(transport, clock))['suggestions']
    assert [call['timeout'] for call in calls] == [TIMEOUT, TIMEOUT]


@pytest.mark.parametrize(('value', 'expected', 'first_timeout'), [
    ('20', 20.0, 20.0), (' 25.5 ', 25.5, 25.5), ('120', 120.0, TIMEOUT),
    ('', BUDGET, TIMEOUT), ('abc', BUDGET, TIMEOUT), ('0', BUDGET, TIMEOUT), ('4.9', BUDGET, TIMEOUT),
    ('999', BUDGET, TIMEOUT), ('nan', BUDGET, TIMEOUT), ('-30', BUDGET, TIMEOUT),
])
def test_budget_setting_is_bounded_and_falls_back_to_the_default(value, expected, first_timeout):
    assert budget_seconds({'JBAI_LLM_BUDGET_SEC': value}) == expected
    clock = Clock()
    transport, calls = timed(clock, (1.0, reply(response())))
    enrich_notice(draft(), provider=provider(transport, clock, JBAI_LLM_BUDGET_SEC=value))
    assert calls[0]['timeout'] == first_timeout


# ── tolerant reading, unchanged content checks ───────────────────────────────

@pytest.mark.parametrize('wrap', [
    lambda body: '```json\n' + body + '\n```',
    lambda body: '```\n' + body + '\n```',
    lambda body: '다음은 결과입니다.\n' + body + '\n이상입니다.',
    lambda body: '<think>합성 추론 과정 { 중괄호 포함 }</think>\n' + body,
    lambda body: '﻿  ' + body + '  ',
    lambda body: '[' + body + ']',
])
def test_wrapped_answers_are_read(wrap):
    result = enrich_notice(draft(), provider=FakeProvider(wrap(response())))
    assert [row['target_id'] for row in result['suggestions']] == ['age_synthetic']


def item(**changes):
    return {'type': 'age', 'values_json': json.dumps(VALUES), 'page': 1, 'quote': QUOTE, **changes}


@pytest.mark.parametrize('body', [
    {'guidance': None, 'criteria': [item()], 'note': 'extra top-level key'},
    {'guidance': None, 'criteria': [item(reason='extra item key')]},
    {'guidance': None, 'criteria': [item(values_json=VALUES)]},
    {'guidance': None, 'criteria': ['not an object', item(type='new_rule'), item(values_json=7), item(quote=None), item()]},
    {'guidance': '안내문이 객체가 아님', 'criteria': [item()]},
    {'guidance': {'text': 7, 'page': 1, 'quote': QUOTE}, 'criteria': [item()]},
])
def test_extra_keys_and_single_bad_parts_do_not_discard_the_rest(body):
    value = draft()
    result = enrich_notice(value, provider=FakeProvider(json.dumps(body, ensure_ascii=False)))
    assert [row['target_id'] for row in result['suggestions']] == ['age_synthetic']
    assert result['guidance'] == value['guidance'] and result['criteria'] == value['criteria']


@pytest.mark.parametrize('content', [
    '{}', '```json\n{}\n```', '{"guidance": null}', '{"criteria": []}', '{"guidance": null, "criteria": {}}',
    '[]', '설명 { 닫히지 않음', '{"guidance": null, "criteria": [NaN]}',
])
def test_answers_without_the_two_top_level_keys_stay_unusable(content):
    clock = Clock()
    transport, calls = timed(clock, (0.1, reply(content)), (0.1, reply(content)))
    assert enrich_notice(draft(), provider=provider(transport, clock)) == draft()
    assert len(calls) == 2  # unusable, so the single fallback was tried


def test_only_the_first_fifty_criteria_are_considered():
    filler = [item(quote='인용이 없는 문장')] * 50
    assert 'suggestions' not in enrich_notice(draft(), provider=FakeProvider(json.dumps({'guidance': None, 'criteria': filler + [item()]})))
    assert enrich_notice(draft(), provider=FakeProvider(json.dumps({'guidance': None, 'criteria': [item()] + filler})))['suggestions']


# ── stated-value matching ────────────────────────────────────────────────────

AGE = {'type': 'age', 'values': dict(VALUES)}
BIRTH = {'type': 'age', 'values': {'birth_start': '1987-01-01', 'birth_end': '2008-12-31', 'basis_date': '2026-11-01'}}
HOME = {'type': 'residence', 'values': {'province': '전북특별자치도', 'city': '', 'basis_date': '2026-11-15'}}
ISSUE = {'type': 'issue_date', 'values': {'mode': 'after_date', 'date': '2026-11-15', 'basis_date': '2026-11-15'}}
INCOME = {'type': 'income', 'values': {'percent': 140.0, 'operator': '이하', 'household_table': {'1': {'직장': 1}}}}
WORK = {'type': 'work_continuity', 'values': {'months': 5, 'basis_date': '2026-11-15'}}


@pytest.mark.parametrize(('candidate', 'values'), [
    (AGE, dict(VALUES)), (AGE, {'min_age': 18, 'max_age': 39}), (AGE, {'min_age': '18', 'max_age': ' 39 '}),
    (AGE, {'min_age': 18.0, 'max_age': 39.0}), (AGE, {'min_age': 18, 'max_age': 39, 'basis_date': '2026. 11. 15.'}),
    (BIRTH, {'birth_start': '1987-01-01', 'birth_end': '2008-12-31'}),
    (BIRTH, {'birth_start': '1987.1.1', 'birth_end': '2008년 12월 31일'}),
    (HOME, {'province': '전북특별자치도'}), (HOME, {'province': '전북'}), (HOME, {'province': ' 전라북도 '}),
    (HOME, {'province': '전북', 'city': ''}),
    (ISSUE, {'date': '2026-11-15'}), (ISSUE, {'date': '2026. 11. 15.'}), (ISSUE, {'date': '2026-11-15', 'mode': 'after_date'}),
    (INCOME, {'percent': 140}), (INCOME, {'percent': '140'}), (INCOME, {'percent': 140.0, 'operator': '이하'}),
    (WORK, {'months': 5}), (WORK, {'months': '5'}),
])
def test_directly_stated_values_match(candidate, values):
    assert values_match(candidate, values) is True


@pytest.mark.parametrize(('candidate', 'values'), [
    (AGE, {'min_age': 17, 'max_age': 39}), (AGE, {**VALUES, 'max_age': 45}), (AGE, {'min_age': 18}),
    (AGE, {'basis_date': '2026-11-15'}), (AGE, {'min_age': 18, 'max_age': 39, 'unsupported': True}),
    (AGE, {'min_age': True, 'max_age': 39}), (AGE, {'min_age': 18.5, 'max_age': 39}),
    (AGE, {'min_age': 18, 'max_age': 39, 'basis_date': '2026-11-16'}), (AGE, {}), (AGE, None), (AGE, [18, 39]),
    (AGE, {'birth_start': '1986-11-16', 'birth_end': '2008-11-14'}),
    (BIRTH, {'birth_start': '1987-01-01'}), (BIRTH, {'birth_start': '1987-01-02', 'birth_end': '2008-12-31'}),
    (BIRTH, {'min_age': 18, 'max_age': 39}),
    (HOME, {'province': '전라남도'}), (HOME, {'province': '전북', 'city': '전주시'}), (HOME, {'city': ''}),
    (ISSUE, {'date': '2026-11-16'}), (ISSUE, {'mode': 'after_date'}), (ISSUE, {'date': None}),
    (INCOME, {'percent': 150}), (INCOME, {'percent': 140, 'operator': '미만'}), (INCOME, {'operator': '이하'}),
    (WORK, {'months': 6}), (WORK, {'months': 5, 'basis_date': None}), (WORK, {'basis_date': '2026-11-15'}),
    ({'type': 'checklist', 'values': {}}, {}), ({'type': 'age', 'values': None}, {'min_age': 18, 'max_age': 39}),
    ({'type': 'age', 'values': {'min_age': 18, 'max_age': 39, 'birth_start': '', 'birth_end': ''}},
     {'birth_start': '', 'birth_end': ''}),
])
def test_conflicting_unknown_or_incomplete_values_do_not_match(candidate, values):
    assert values_match(candidate, values) is False


def test_every_rule_type_has_a_stated_group_and_the_prompt_names_its_keys():
    assert set(STATED_KEYS) == {'age', 'residence', 'issue_date', 'income', 'work_continuity'}
    for groups in STATED_KEYS.values():
        assert all(key in SYSTEM_PROMPT for group in groups for key in group)


# What a provider reads directly from each synthetic notice sentence (no derived values).
STATED = {
    'A': [('age', {'min_age': 18, 'max_age': 39}, 1, '지원 대상: 만 18세 이상 39세 이하 청년'),
          ('residence', {'province': '전북특별자치도'}, 1, '거주 요건: 전북특별자치도 거주자'),
          ('issue_date', {'date': '2026-11-15'}, 1, '서류는 2026. 11. 15. 이후 발급분만 인정'),
          ('work_continuity', {'months': 5}, 1, '계속 근로 요건: 5개월 이상 연속 근로')],
    'B': [('age', {'min_age': 18, 'max_age': 39}, 2, '자격: 만 18세 ~ 39세'),
          ('residence', {'province': '전북'}, 2, '거주지: 전북 거주')],
    'C': [('age', {'birth_start': '1987-01-01', 'birth_end': '2008-12-31'}, 1, '지원 대상: 1987.1.1 ~ 2008.12.31 출생자')],
}


@pytest.mark.parametrize('name', sorted(STATED))
def test_stated_values_reach_every_automatic_candidate_of_the_measurement_notices(name):
    pages, supplemental = probe.NOTICES[name]
    source = analyze_notice(probe.public_pdf(pages), supplemental)
    automatic = {row['id'] for row in source['criteria'] if row.get('engine_rule')}
    content = json.dumps({'guidance': None, 'criteria': [
        {'type': kind, 'values_json': json.dumps(values, ensure_ascii=False), 'page': page, 'quote': quote}
        for kind, values, page, quote in STATED[name]]}, ensure_ascii=False)
    result = enrich_notice(source, supplemental, provider=FakeProvider(content))
    assert len(automatic) == len(STATED[name])
    assert {row['target_id'] for row in result['suggestions']} == automatic
    assert result['criteria'] == source['criteria']
    assert probe.classify(content, source, supplemental, result) == {
        'received': len(STATED[name]), 'passed': len(STATED[name]), 'quote': 0, 'value': 0, 'kind': 0,
        'json': 0, 'other': 0, 'screen_violation': 0}


# ── input window and prompt ──────────────────────────────────────────────────

def long_draft():
    value = draft()
    value['source_pages'] = [{'page': 1, 'text': PUBLIC + '\n' + '가' * 20_000}, {'page': 2, 'text': '나' * 20_000}]
    return value


@pytest.mark.parametrize(('setting', 'limit'), [
    ('', SEND_MAX_TEXT), ('5000', 5_000), ('999', SEND_MAX_TEXT), ('abc', SEND_MAX_TEXT), ('200001', SEND_MAX_TEXT),
])
def test_only_the_leading_window_of_a_long_notice_is_sent(setting, limit):
    assert send_limit({'JBAI_LLM_MAX_INPUT_CHARS': setting}) == limit
    sent = []

    def transport(url, headers, body, timeout):
        sent.append(json.loads(body['messages'][1]['content']))
        return reply(response())
    result = enrich_notice(long_draft(), provider=provider(transport, JBAI_LLM_MAX_INPUT_CHARS=setting))
    pages = sent[0]['notice_pages']
    assert sum(len(page['text']) for page in pages) == limit
    assert pages[0]['text'] == long_draft()['source_pages'][0]['text'][:limit]
    assert set(sent[0]) == {'notice_pages', 'supplemental'}
    # The citation sits in the sent part and is checked against the whole local text.
    assert result['suggestions'][0]['target_id'] == 'age_synthetic'


def test_request_holds_the_static_prompt_and_public_text_but_no_rule_candidate():
    bodies = []

    def transport(url, headers, body, timeout):
        bodies.append(body)
        return reply(response())
    enrich_notice(draft(), provider=provider(transport))
    body = bodies[0]
    assert body['messages'][0]['content'].startswith(SYSTEM_PROMPT)
    whole = json.dumps(body, ensure_ascii=False)
    assert all(word not in whole for word in ('age_synthetic', 'engine_rule', '1986-11-16', '2008-11-15', KEY))
    assert '1,200자' in SYSTEM_PROMPT


def test_long_notice_probe_adds_one_call_and_sends_only_the_window():
    bodies = []

    def transport(url, headers, body, timeout):
        bodies.append(json.loads(body['messages'][1]['content']))
        return reply(json.dumps({'guidance': None, 'criteria': []}))
    values = {'LLM_PROVIDER': 'jbai', 'JBAI_BASE_URL': BASE, 'JBAI_API_KEY': KEY, 'JBAI_TEXT_MODEL': 'synthetic-text-model'}
    report = probe.probe(environ=values, transport=transport, max_calls=15, mode='json_object', repeats=1, long=True)
    row = report['rows'][-1]
    assert (row['phase'], row['notice'], row['status'], row['schema_ok']) == ('long', probe.LONG, 200, True)
    assert row['notice_chars'] > SEND_MAX_TEXT and report['calls'] == 4
    assert sum(len(page['text']) for page in bodies[-1]['notice_pages']) == SEND_MAX_TEXT
    assert probe.LONG not in report['summary']
