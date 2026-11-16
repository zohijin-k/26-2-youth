"""Fake-transport tests for the JBAI notice probe: no network, no real values."""
from email.message import Message
import json
from urllib.error import HTTPError

import pytest

from demo.backend.tools import probe_jbai_notice as probe

KEY = 'synthetic-probe-credential-value'
HOST = 'probe-host.example.invalid'
MODEL = 'synthetic-probe-model'
MARKER = 'SYNTHETIC-RESPONSE-BODY-MARKER'
AGE_A = {'min_age': 18, 'max_age': 39, 'basis_date': '2026-11-15',
         'birth_start': '1986-11-16', 'birth_end': '2008-11-15'}
QUOTE_A = '지원 대상: 만 18세 이상 39세 이하 청년'


def environ():
    return {'LLM_PROVIDER': 'jbai', 'JBAI_BASE_URL': f'https://{HOST}/open-api/v1',
            'JBAI_API_KEY': KEY, 'JBAI_TEXT_MODEL': MODEL}


def env_text(**values):
    rows = {**values, 'JBAI_API_KEY': KEY, 'JBAI_TEXT_MODEL': MODEL}
    return ''.join(f'{name}={value}\n' for name, value in rows.items())


def reply(content):
    return {'choices': [{'message': {'content': content}}]}


def valid_body():
    return json.dumps({'guidance': {'text': '신청 방법: 온라인 신청', 'page': 1, 'quote': '신청 방법: 온라인 신청'},
                       'criteria': [{'type': 'age', 'values_json': json.dumps(AGE_A), 'page': 1, 'quote': QUOTE_A}]},
                      ensure_ascii=False)


class FakeTransport:
    def __init__(self, answer):
        self.answer, self.bodies = answer, []

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(body)
        result = self.answer(body)
        if isinstance(result, Exception):
            raise result
        return result


def formats(transport):
    return [body.get('response_format', {}).get('type', 'none') for body in transport.bodies]


def test_modes_fall_back_in_order_and_stop_at_first_schema_valid_mode():
    def answer(body):
        kind = body.get('response_format', {}).get('type')
        if kind == 'json_schema':
            return HTTPError('https://' + HOST, 400, 'bad request', Message(), None)
        if kind == 'json_object':
            return reply('```json\n' + valid_body() + '\n```')
        return reply(valid_body())
    transport = FakeTransport(answer)
    report = probe.probe(environ=environ(), transport=transport, max_calls=9)
    modes = [row for row in report['rows'] if row['phase'] == 'mode']
    assert [(row['mode'], row['status'], row['json_ok'], row['schema_ok']) for row in modes] == [
        ('json_schema', 400, False, False), ('json_object', 200, False, False), ('prompt', 200, True, True)]
    assert report['mode'] == 'prompt'
    assert formats(transport)[:3] == ['json_schema', 'json_object', 'none']
    assert set(formats(transport)[3:]) == {'none'} and len(transport.bodies) == 3 + 3 * 2
    # json_object and prompt modes add the JSON-only instruction; json_schema is the provider body unchanged.
    assert probe.JSON_ONLY not in transport.bodies[0]['messages'][0]['content']
    assert all(probe.JSON_ONLY in body['messages'][0]['content'] for body in transport.bodies[1:])
    # The user payload is the same public projection in every mode.
    assert len({body['messages'][1]['content'] for body in transport.bodies[:3]}) == 1


def test_working_json_schema_skips_other_modes_unless_all_modes_requested():
    transport = FakeTransport(lambda body: reply(valid_body()))
    report = probe.probe(environ=environ(), transport=transport, max_calls=9)
    assert report['mode'] == 'json_schema' and [row['mode'] for row in report['rows'] if row['phase'] == 'mode'] == ['json_schema']
    assert report['calls'] == 1 + 6
    transport = FakeTransport(lambda body: reply(valid_body()))
    report = probe.probe(environ=environ(), transport=transport, max_calls=9, all_modes=True)
    assert [row['mode'] for row in report['rows'] if row['phase'] == 'mode'] == list(probe.MODES)
    assert report['mode'] == 'json_schema' and report['calls'] == 9


def test_call_budget_is_enforced_and_capped_at_fifteen():
    transport = FakeTransport(lambda body: reply(valid_body()))
    report = probe.probe(environ=environ(), transport=transport, max_calls=4)
    assert len(transport.bodies) == 4 and report['calls'] == 4
    assert [row['status'] for row in report['rows']].count('budget') == 3
    transport = FakeTransport(lambda body: reply(valid_body()))
    probe.probe(environ=environ(), transport=transport, max_calls=99, all_modes=True, repeats=10)
    assert len(transport.bodies) == probe.HARD_CALL_LIMIT


def test_discard_reasons_are_classified_and_only_verified_items_pass():
    draft = probe.analyze_notice(probe.public_pdf(probe.NOTICES['A'][0]), '합성 공개 부가 설명')
    content = json.dumps({'guidance': {'text': '자동 선정됩니다', 'page': 1, 'quote': '신청 방법: 온라인 신청'},
        'criteria': [
            {'type': 'age', 'values_json': json.dumps(AGE_A), 'page': 1, 'quote': QUOTE_A},
            {'type': 'age', 'values_json': json.dumps(AGE_A), 'page': 1, 'quote': '원문에 없는 인용 문장'},
            {'type': 'residence', 'values_json': json.dumps({'province': '전북'}), 'page': 1,
             'quote': '거주 요건: 전북특별자치도 거주자'},
            {'type': 'work_continuity', 'values_json': 'not json', 'page': 1, 'quote': '계속 근로 요건: 5개월 이상 연속 근로'},
        ]}, ensure_ascii=False)
    result = probe.enrich_notice(draft, '합성 공개 부가 설명', provider=_Fixed(content))
    counts = probe.classify(content, draft, '합성 공개 부가 설명', result)
    assert counts == {'received': 5, 'passed': 1, 'quote': 1, 'value': 3, 'kind': 0, 'json': 0,
                      'other': 0, 'screen_violation': 0}

    kind = json.dumps({'guidance': None, 'criteria': [
        {'type': 'invented_rule', 'values_json': '{}', 'page': 1, 'quote': QUOTE_A}]})
    result = probe.enrich_notice(draft, '', provider=_Fixed(kind))
    assert result == draft
    assert probe.classify(kind, draft, '', result) == {'received': 1, 'passed': 0, 'quote': 0, 'value': 0,
        'kind': 1, 'json': 0, 'other': 0, 'screen_violation': 0}

    for broken in ('not json', '```json\n{}\n```', '[]', json.dumps({'criteria': []})):
        result = probe.enrich_notice(draft, '', provider=_Fixed(broken))
        assert result == draft
        assert probe.classify(broken, draft, '', result)['json'] == 1


def test_screen_violation_detects_an_unverified_suggestion():
    draft = probe.analyze_notice(probe.public_pdf(probe.NOTICES['A'][0]), '')
    forged = {**draft, 'suggestions': [{'target_id': 'guidance', 'type': 'guidance', 'text': '자동 선정',
        'page': 1, 'quote': '원문에 없는 인용', 'source': 'jbai', 'confidence': 0.0, 'needs_review': True}]}
    payload = probe.notice_payload(draft, '')
    assert probe.screen_violations(draft, payload, forged) == 1
    assert probe.screen_violations(draft, payload, draft) == 0


def test_rule_draft_is_returned_on_timeout_and_status_is_recorded():
    transport = FakeTransport(lambda body: TimeoutError(KEY))
    report = probe.probe(environ=environ(), transport=transport, max_calls=3)
    assert [row['status'] for row in report['rows']] == ['timeout'] * 3
    assert report['mode'] is None and all(row['passed'] == 0 for row in report['rows'])


@pytest.mark.parametrize('flag', [[], ['--json']])
def test_output_never_contains_key_host_model_or_response_body(tmp_path, capsys, caplog, flag):
    env_file = tmp_path / 'synthetic.env'
    env_file.write_text(env_text(LLM_PROVIDER='none', JBAI_BASE_URL=f'https://{HOST}/open-api/v1'))
    body = json.dumps({'guidance': {'text': MARKER, 'page': 1, 'quote': MARKER}, 'criteria': []})
    transport = FakeTransport(lambda request: reply(body))
    assert probe.main(['--env-file', str(env_file), *flag], transport=transport) == 0
    output = capsys.readouterr()
    text = output.out + output.err + caplog.text
    assert KEY not in text and HOST not in text and MODEL not in text and MARKER not in text
    assert transport.bodies and KEY not in json.dumps(transport.bodies)
    if flag:
        report = json.loads(output.out)
        assert set(report) == {'configured', 'calls', 'mode', 'rows', 'summary'}
        assert all('content' not in row for row in report['rows'])


def test_errors_print_nothing_from_the_exception(tmp_path, capsys, monkeypatch):
    env_file = tmp_path / 'synthetic.env'
    env_file.write_text(env_text(JBAI_BASE_URL=f'https://{HOST}/v1'))
    monkeypatch.setattr(probe, 'probe', lambda **kwargs: (_ for _ in ()).throw(RuntimeError(KEY + HOST)))
    assert probe.main(['--env-file', str(env_file)]) == 1
    output = capsys.readouterr().out
    assert output.strip() == 'probe failed'


def test_missing_or_unsafe_configuration_makes_no_call(tmp_path, capsys):
    env_file = tmp_path / 'synthetic.env'
    env_file.write_text(env_text(JBAI_BASE_URL=f'http://{HOST}'))
    transport = FakeTransport(lambda body: reply(valid_body()))
    assert probe.main(['--env-file', str(env_file)], transport=transport) == 2
    assert transport.bodies == [] and HOST not in capsys.readouterr().out


def test_probe_notices_match_the_existing_test_notices():
    from demo.backend.tests import test_program_analysis
    from demo.backend.notice_analysis import analyze_notice
    assert analyze_notice(probe.public_pdf(probe.NOTICES['C'][0]))['source_pages'] == \
        analyze_notice(test_program_analysis.notice())['source_pages']


class _Fixed:
    name = 'jbai'

    def __init__(self, content):
        self.content = content

    def generate(self, purpose, payload):
        return self.content
