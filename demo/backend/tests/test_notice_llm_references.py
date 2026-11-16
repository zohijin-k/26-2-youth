"""Display-only references on officer-check candidates: fake providers only, no network.

The sentences are shapes seen in public notices (several conditions on one
line, a two-digit year, two income ratios); every value in them is synthetic.
"""
from copy import deepcopy
import json
import logging

import pytest

from demo.backend.api.program_analysis import validate_analysis
from demo.backend.notice_analysis import analyze_notice
from demo.backend.notice_llm import enrich_notice, notice_payload, reference_for, stated_values
from demo.backend.tests.test_notice_llm import QUOTE, VALUES, FakeProvider, draft
from demo.backend.tools import probe_jbai_notice as probe

TARGET = '□ 모집대상 : 전북특별자치도 내 주소지를 둔 청년(18~39세)'
BIRTH = '② 연 령 : 2025.12.31.기준 만 18~39세 청년(1986.1.1.~2007.12.31. 출생)'
INCOME = '소득요건 : 청년가구 기준 중위소득 60% 이하 / 원가구(청년+부모) 기준 중위소득 100% 이하'
ISSUE = "m 모든 서류는 공고일('26. 5. 18.~) 이후 발급분만 인정하며, 접수한 서류는 반환하지 않음"
ISSUE_NO_DATE = '※ 서류 발급일 기준은 공고일 이후 발행한 서류를 원칙으로 함'
WORK = '계속 근로 요건: 1년 이상 근로 중인 사람'
LINES = ['2026 합성 청년 직무체험 참여자 모집 공고', '신청 기간: 2026. 5. 18. ~ 2026. 6. 2.', TARGET, INCOME, ISSUE,
         ISSUE_NO_DATE, '제출 서류: 주민등록초본', '신청 방법: 온라인 신청', '문의: 합성청년센터 063-000-0000']
LOGGER = 'demo.backend.llm'


# ── stated values must be printed in the cited sentence ──────────────────────

@pytest.mark.parametrize(('kind', 'values', 'quote', 'expected'), [
    ('age', {'min_age': 18, 'max_age': 39}, TARGET, {'min_age': 18, 'max_age': 39}),
    ('age', {'min_age': '18', 'max_age': 39.0, 'basis_date': '2026-05-18'}, TARGET, {'min_age': 18, 'max_age': 39}),
    ('age', {'birth_start': '1986-01-01', 'birth_end': '2007-12-31'}, BIRTH, {'birth_start': '1986-01-01', 'birth_end': '2007-12-31'}),
    ('age', {'min_age': 18, 'max_age': 39, 'birth_start': '1986.1.1', 'birth_end': '2007년 12월 31일'}, BIRTH,
     {'min_age': 18, 'max_age': 39, 'birth_start': '1986-01-01', 'birth_end': '2007-12-31'}),
    ('residence', {'province': '전북특별자치도'}, TARGET, {'province': '전북특별자치도'}),
    ('residence', {'province': '전북', 'city': ''}, TARGET, {'province': '전북특별자치도'}),
    ('residence', {'province': '전북특별자치도'}, '주민등록상 전북도에 거주 시 지원 가능', {'province': '전북특별자치도'}),
    ('issue_date', {'date': '2026-05-18'}, ISSUE, {'date': '2026-05-18'}),
    ('issue_date', {'date': '2026. 11. 16.', 'mode': 'after_date'}, '서류는 2026.11.16 이후 발급분만 인정', {'date': '2026-11-16'}),
    ('income', {'percent': 60, 'operator': '이하'}, INCOME, {'percent': 60, 'operator': '이하'}),
    ('income', {'percent': 100.0}, INCOME, {'percent': 100}),
    ('income', {'percent': '62.5'}, '기준 중위소득 62.5% 이하', {'percent': 62.5}),
    ('work_continuity', {'months': 5}, '계속 근로 요건: 5개월 이상 연속 근로', {'months': 5}),
    ('work_continuity', {'months': 12}, WORK, {'months': 12}),
])
def test_values_printed_in_the_sentence_are_kept_in_display_form(kind, values, quote, expected):
    assert stated_values(kind, values, quote) == expected


@pytest.mark.parametrize(('kind', 'values', 'quote'), [
    ('age', {'min_age': 19, 'max_age': 39}, TARGET),                       # 19 is not printed
    ('age', {'min_age': 18}, TARGET),                                      # incomplete group
    ('age', {'basis_date': '2026-05-18'}, TARGET),                         # derived value only
    ('age', {**VALUES}, QUOTE),                                            # computed birth range not printed
    ('age', {'min_age': 18, 'max_age': 39}, '2018년 이전 출생, 139명 선발'),     # digits inside longer numbers
    ('age', {'min_age': True, 'max_age': 39}, TARGET),
    ('age', {'birth_start': '1986-01-01', 'birth_end': '2007-12-30'}, BIRTH),
    ('residence', {'province': '전라남도'}, TARGET),
    ('residence', {'province': '전북 39세'}, TARGET),
    ('residence', {'province': '가' * 13}, '가' * 13),
    ('issue_date', {'date': '2026-05-18'}, ISSUE_NO_DATE),                 # the sentence prints no date
    ('issue_date', {'date': '1926-05-18'}, ISSUE),                         # two-digit years are 20xx only
    ('issue_date', {'date': '공고일'}, ISSUE),
    ('income', {'percent': 150}, INCOME),
    ('income', {'percent': 60, 'operator': '초과'}, INCOME),
    ('income', {'operator': '이하'}, INCOME),
    ('work_continuity', {'months': 6}, '계속 근로 요건: 5개월 이상 연속 근로'),
    ('work_continuity', {'months': 24}, WORK),
    ('checklist', {'min_age': 18, 'max_age': 39}, TARGET),
    ('age', None, TARGET), ('age', [18, 39], TARGET), ('age', {'min_age': 18, 'max_age': 39}, None), (None, {}, TARGET),
])
def test_unverifiable_or_incomplete_values_give_no_reference(kind, values, quote):
    assert stated_values(kind, values, quote) is None


# ── references on a notice whose conditions the extractor leaves for the officer ──

def source():
    return analyze_notice(probe.public_pdf([LINES]), '')


def reply(*items, guidance=None):
    return json.dumps({'guidance': guidance, 'criteria': [
        {'type': kind, 'values_json': json.dumps(values, ensure_ascii=False), 'page': 1, 'quote': quote}
        for kind, values, quote in items]}, ensure_ascii=False)


def test_references_attach_to_officer_check_candidates_without_changing_them(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    value = source()
    by_id = {row['id']: row for row in value['criteria']}
    assert not any(row.get('engine_rule') for row in value['criteria'])   # nothing here is automatic
    saved = deepcopy(value)
    content = reply(('age', {'min_age': 18, 'max_age': 39}, TARGET), ('residence', {'province': '전북'}, TARGET),
                    ('income', {'percent': 60, 'operator': '이하'}, INCOME), ('issue_date', {'date': '2026-05-18'}, ISSUE),
                    ('issue_date', {'date': '2026-05-18'}, ISSUE_NO_DATE))
    result = enrich_notice(value, provider=FakeProvider(content))
    assert value == saved
    assert result['criteria'] == saved['criteria'] and result['guidance'] == saved['guidance']
    rows = result['suggestions']
    assert [(row['type'], row['read']) for row in rows] == [
        ('age', '18~39세'), ('residence', '전북특별자치도'), ('income', '60% 이하'), ('issue_date', '2026-05-18')]
    for row in rows:
        target = by_id[row['target_id']]
        assert target['engine_rule'] is None and target['quote'].strip() in (TARGET, INCOME, ISSUE)
        assert target.get('candidate_type') in (row['type'], 'checklist')
        assert set(row) == {'target_id', 'type', 'reference', 'read', 'read_values', 'page', 'quote', 'source',
                            'confidence', 'needs_review'}
        assert row['reference'] is True and row['needs_review'] is True and row['confidence'] == 0.0
        assert stated_values(row['type'], row['read_values'], row['quote']) == row['read_values']
    assert [record.getMessage() for record in caplog.records if record.name == LOGGER] == [
        'llm_result purpose=notice_analysis guidance=none criteria_received=5 criteria_accepted=0 criteria_reference=4']
    counts = probe.classify(content, value, '', result)
    assert (counts['received'], counts['passed'], counts['value'], counts['screen_violation']) == (5, 4, 1, 0)


def manual(kind='age', values=None, quote=TARGET, identifier='manual_item', page=1):
    return {'id': identifier, 'type': 'checklist', 'candidate_type': kind, 'label': quote, 'values': values or {},
            'page': page, 'quote': quote, 'engine_rule': None, 'confidence': .7, 'needs_review': True}


def notice(*rows, text=None):
    lines = '\n'.join([TARGET, BIRTH, INCOME, WORK] if text is None else text)
    return {'version': 1, 'source_pages': [{'page': 1, 'text': lines}],
            'guidance': {'id': 'guidance', 'value': '기존 규칙 안내', 'needs_review': True}, 'criteria': list(rows)}


def suggestions(value, *items):
    return enrich_notice(value, provider=FakeProvider(reply(*items))).get('suggestions', [])


def test_a_checklist_candidate_gets_a_reference_and_stays_a_checklist_item():
    value = notice(manual())
    result = enrich_notice(value, provider=FakeProvider(reply(('age', {'min_age': 18, 'max_age': 39}, TARGET))))
    assert result['criteria'] == value['criteria'] and result['criteria'][0]['engine_rule'] is None
    assert [(row['target_id'], row['reference'], row['read']) for row in result['suggestions']] == [('manual_item', True, '18~39세')]
    assert 'values' not in result['suggestions'][0]


def test_same_kind_candidate_is_preferred_then_unknown_kind_then_another_kind():
    proposal = ('residence', {'province': '전북특별자치도'}, TARGET)
    rows = [manual('age', identifier='age_item'), manual('checklist', identifier='plain_item'), manual('residence', identifier='home_item')]
    assert suggestions(notice(*rows), proposal)[0]['target_id'] == 'home_item'
    assert suggestions(notice(*rows[:2]), proposal)[0]['target_id'] == 'plain_item'
    assert suggestions(notice(rows[0]), proposal)[0]['target_id'] == 'age_item'


def test_no_reference_where_an_automatic_candidate_of_that_type_reads_the_sentence():
    value = draft()                                           # automatic age candidate on QUOTE
    value['criteria'].append(manual('checklist', quote=QUOTE, identifier='rest_item'))
    for values in ({**VALUES, 'unsupported': True}, {'min_age': 18}):
        content = json.dumps({'guidance': None, 'criteria': [
            {'type': 'age', 'values_json': json.dumps(values), 'page': 1, 'quote': QUOTE}]})
        assert enrich_notice(value, provider=FakeProvider(content)) == value
    # Another type on the same sentence may still be shown on its officer-check item.
    value['source_pages'][0]['text'] += '\n' + TARGET
    value['criteria'] = [{**value['criteria'][0], 'quote': TARGET, 'label': TARGET}, manual('checklist', identifier='rest_item')]
    rows = suggestions(value, ('residence', {'province': '전북'}, TARGET))
    assert [(row['target_id'], row['type'], row['reference']) for row in rows] == [('rest_item', 'residence', True)]


def test_no_reference_when_the_extractor_read_the_sentence_differently():
    quote = '지원대상: 18~39세 청년, 20~30세 우대'
    value = notice(manual(values={'min_age': 18, 'max_age': 39, 'basis_date': None}, quote=quote), text=[quote])
    assert suggestions(value, ('age', {'min_age': 20, 'max_age': 30}, quote)) == []
    assert [row['read'] for row in suggestions(value, ('age', {'min_age': 18, 'max_age': 39}, quote))] == ['18~39세']


@pytest.mark.parametrize('items', [
    [('age', {'min_age': 18, 'max_age': 39}, '원문에 없는 인용 문장')],          # citation not verbatim
    [('age', {'min_age': 18, 'max_age': 39}, WORK)],                        # sentence has no candidate
    [('age', {'min_age': 19, 'max_age': 39}, TARGET)],                      # value not printed
    [('new_rule', {'min_age': 18, 'max_age': 39}, TARGET)],                 # type outside the rule types
    [('age', {'min_age': 18, 'max_age': 39}, TARGET[:3])],                  # citation too short
])
def test_no_reference_without_a_verbatim_citation_a_candidate_and_printed_values(items):
    value = notice(manual())
    assert enrich_notice(value, provider=FakeProvider(reply(*items))) == value


def test_one_reference_per_target_and_type_and_several_types_on_one_item():
    value = notice(manual('checklist'))
    rows = suggestions(value, ('age', {'min_age': 18, 'max_age': 39}, TARGET), ('age', {'min_age': 18, 'max_age': 39}, TARGET),
                       ('residence', {'province': '전북'}, TARGET))
    assert [(row['target_id'], row['type']) for row in rows] == [('manual_item', 'age'), ('manual_item', 'residence')]


def test_reference_for_ignores_candidates_without_an_identifier_or_on_another_page():
    proposal = {'type': 'age', 'values_json': '{}', 'page': 1, 'quote': TARGET}
    values = {'min_age': 18, 'max_age': 39}
    nameless = manual()
    nameless.pop('id')
    assert reference_for(proposal, values, notice(nameless), 'fake') is None
    assert reference_for(proposal, values, notice(manual(page=2)), 'fake') is None
    assert reference_for(proposal, values, notice(manual()), 'fake')['source'] == 'fake'


def test_saving_a_draft_that_carries_references_stores_the_draft_without_them():
    value = source()
    result = enrich_notice(value, provider=FakeProvider(reply(('age', {'min_age': 18, 'max_age': 39}, TARGET))))
    assert [row['reference'] for row in result['suggestions']] == [True]
    # The officer's save sends the suggestions back; the server keeps none of them.
    stored = validate_analysis(result, value)
    assert 'suggestions' not in stored and stored == validate_analysis(value, value)


def test_probe_flags_a_tampered_reference_as_a_screen_violation():
    value = notice(manual())
    payload = notice_payload(value)
    result = enrich_notice(value, provider=FakeProvider(reply(('age', {'min_age': 18, 'max_age': 39}, TARGET))))
    assert probe.screen_violations(value, payload, result) == 0
    for change in ({'read_values': {'min_age': 19, 'max_age': 39}}, {'target_id': 'missing'}, {'needs_review': False},
                   {'quote': '원문에 없는 인용 문장'}, {'values': {'min_age': 18}}):
        tampered = deepcopy(result)
        tampered['suggestions'][0].update(change)
        assert probe.screen_violations(value, payload, tampered) == 1
    # A reference may not sit on an automatic candidate.
    automatic, moved = deepcopy(value), deepcopy(result)
    for item in (automatic, moved):
        item['criteria'][0]['engine_rule'] = 'demo.backend.rules.age_eligibility.assess_age'
    assert probe.screen_violations(automatic, payload, moved) == 1
