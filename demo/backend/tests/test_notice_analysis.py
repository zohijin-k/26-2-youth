"""Synthetic public notice PDFs verify provenance and conservative bindings."""
import importlib

import pymupdf
import pytest

from demo.backend.notice_analysis import SUPPORTED_RULES, analyze_form, analyze_notice


def public_pdf(*pages):
    with pymupdf.open() as document:
        for lines in pages:
            page = document.new_page(width=1000, height=1000)
            for index, line in enumerate(lines):
                page.insert_text((30, 40 + 24 * index), line, fontname='korea', fontsize=11)
        return document.tobytes()


def all_candidates(draft):
    return [draft['title'], draft['period'], draft['guidance'], *draft['required_docs'], *draft['criteria']]


def test_synthetic_notice_extracts_title_period_documents_and_existing_rule_candidates():
    draft = analyze_notice(public_pdf([
        '2026 합성 청년 지원사업 모집 공고',
        '공고일: 2026. 11. 15.',
        '신청 기간: 2026. 11. 16. ~ 2026. 12. 15.',
        '지원 대상: 만 18세 이상 39세 이하 청년',
        '거주 요건: 전북특별자치도 거주자',
        '제출 서류: 주민등록초본, 건강보험료 납부확인서',
        '서류는 2026. 11. 15. 이후 발급분만 인정',
        '계속 근로 요건: 5개월 이상 연속 근로',
        '신청 방법: 온라인 신청',
        '문의: 합성청년센터 000-000-0000',
    ]))
    assert draft['status'] == 'draft'
    assert draft['title']['value'] == '2026 합성 청년 지원사업 모집 공고'
    assert draft['period']['value'] == {'apply_start': '2026-11-16', 'apply_end': '2026-12-15'}
    assert {row['slot_key'] for row in draft['required_docs']} >= {'resident_abstract', 'nhis_payment'}
    by_kind = {row['type']: row for row in draft['criteria']}
    assert {'age', 'residence', 'issue_date', 'work_continuity'} <= by_kind.keys()
    assert by_kind['age']['values']['birth_start'] == '1986-11-16'
    assert by_kind['age']['values']['birth_end'] == '2008-11-15'
    assert by_kind['residence']['values']['province'] == '전북특별자치도'
    assert by_kind['issue_date']['values']['date'] == '2026-11-15'
    assert by_kind['work_continuity']['values']['months'] == 5
    assert all(row['needs_review'] for row in all_candidates(draft))
    assert '신청 방법: 온라인 신청' in draft['guidance']['value']
    assert '문의: 합성청년센터' in draft['guidance']['value']


def test_each_suggestion_has_real_short_quote_page_and_bounded_confidence():
    draft = analyze_notice(public_pdf(['합성 청년 지원사업', '접수 기간: 2026-11-16 ~ 2026-12-31'],
                                    ['기준일: 2026-11-15', '자격: 만 18세 ~ 39세', '거주지: 전북 거주']))
    pages = {row['page']: row['text'] for row in draft['source_pages']}
    for candidate in all_candidates(draft):
        assert set(('page', 'quote', 'confidence', 'needs_review')) <= candidate.keys()
        assert 0 <= candidate['confidence'] <= 1
        if candidate['page'] is not None:
            assert candidate['quote'] in pages[candidate['page']]
            assert len(candidate['quote']) <= 240
    assert next(row for row in draft['criteria'] if row['type'] == 'age')['page'] == 2


def test_unsupported_condition_and_unknown_document_remain_manual_candidates():
    draft = analyze_notice(public_pdf(['합성 청년 지원사업', '대상: 지역 봉사활동 30시간 이상 참여하여야 함',
                                    '제출 서류: 봉사활동 증명서, 추천서']))
    assert all(row['type'] == 'checklist' and row['engine_rule'] is None for row in draft['criteria'])
    assert {row['original_label'] for row in draft['required_docs']} == {'봉사활동 증명서', '추천서'}
    assert all(row['label'] == '기타 서류' and row['slot_key'] is None and row['needs_review'] for row in draft['required_docs'])


@pytest.mark.parametrize('text', ['대상: 만 18세 이상 39세 이하', '거주 요건: 전북특별자치도 거주',
                                 '근로 요건: 5개월 계속 근로'])
def test_missing_basis_date_never_creates_automatic_condition(text):
    draft = analyze_notice(public_pdf(['합성 사업', text]))
    assert draft['criteria']
    assert all(row['type'] == 'checklist' and row['engine_rule'] is None for row in draft['criteria'])


def test_city_residence_stays_checklist_because_existing_rule_only_supports_province():
    draft = analyze_notice(public_pdf(['합성 사업', '공고일: 2026-11-15', '거주 요건: 전북특별자치도 전주시 거주']))
    residence = next(row for row in draft['criteria'] if row['candidate_type'] == 'residence')
    assert residence['type'] == 'checklist'
    assert residence['values'] == {'province': '전북특별자치도', 'city': '전주시', 'basis_date': '2026-11-15'}


@pytest.mark.parametrize('line', ['소득 기준: 중위소득 140% 이하', '소득 기준: 중위소득 120% 이하'])
def test_income_without_public_household_table_is_never_automatic(line):
    draft = analyze_notice(public_pdf(['합성 사업', line]))
    income = next(row for row in draft['criteria'] if row['candidate_type'] == 'income')
    assert income['type'] == 'checklist' and income['values']['household_table'] == {}


def test_arbitrary_household_table_cannot_inherit_fixed_existing_income_limits():
    draft = analyze_notice(public_pdf(['합성 사업', '소득 기준: 중위소득 140% 이하', '가구원 직장 지역 혼합',
                                    '1인 1,000 2,000 3,000', '2인 4,000 5,000 6,000']))
    income = next(row for row in draft['criteria'] if row['candidate_type'] == 'income')
    assert income['values']['household_table'][1] == {'직장': 1000, '지역': 2000, '혼합': 3000}
    assert income['type'] == 'checklist'


def test_exact_supported_income_table_can_bind_but_still_requires_officer_review():
    from demo.backend.rules.scoring import MEDIAN_INCOME_140
    table = [f'{size}인 ' + ' '.join(f'{row[key]:,}' for key in ('직장', '지역', '혼합') if key in row)
             for size, row in MEDIAN_INCOME_140.items()]
    draft = analyze_notice(public_pdf(['합성 사업', '소득 기준: 중위소득 140% 이하', '가구원 직장 지역 혼합', *table]))
    income = next(row for row in draft['criteria'] if row['candidate_type'] == 'income')
    assert income['type'] == 'income'
    assert income['engine_rule'] == SUPPORTED_RULES['income'] and income['needs_review']


def test_image_only_notice_explicitly_requires_manual_entry_and_does_not_guess_title():
    draft = analyze_notice(public_pdf([]))
    assert draft['status'] == 'manual_required'
    assert draft['title']['value'] == '' and draft['period']['value'] == {'apply_start': '', 'apply_end': ''}
    assert draft['criteria'] == [] and draft['required_docs'] == []
    assert any('자동 분석 불가' in warning and '직접 입력' in warning for warning in draft['warnings'])
    assert all(row['needs_review'] for row in all_candidates(draft))


def test_supplemental_candidates_keep_separate_source_and_cannot_fabricate_pdf_page():
    draft = analyze_notice(public_pdf(['합성 사업']), '대상: 봉사활동 참가자\n제출 서류: 추천서')
    item = draft['required_docs'][0]
    assert item['page'] is None and item['source'] == 'supplemental'
    assert item['needs_review'] and item['quote'] == '제출 서류: 추천서'


@pytest.mark.parametrize('supplemental', ['a' * 4001, None])
def test_supplemental_input_limit_is_enforced(supplemental):
    with pytest.raises(ValueError, match='4,000자'):
        analyze_notice(public_pdf(['합성 사업']), supplemental)


def test_short_period_end_reuses_only_explicit_start_year():
    draft = analyze_notice(public_pdf(['합성 사업', '접수기간: 2026.11.16. ~ 12.31.']))
    assert draft['period']['value'] == {'apply_start': '2026-11-16', 'apply_end': '2026-12-31'}


@pytest.mark.parametrize('line', ['신청기간: 2026.13.16 ~ 2026.12.31', '신청기간: 2026.12.31 ~ 2026.11.16'])
def test_invalid_or_reversed_period_does_not_become_usable_dates(line):
    result = analyze_notice(public_pdf(['합성 사업', line]))
    assert result['period']['value'] == {'apply_start': '', 'apply_end': ''}
    assert result['period']['confidence'] == 0 and result['period']['needs_review']


def test_explicit_birth_range_has_inclusive_existing_age_contract():
    draft = analyze_notice(public_pdf(['합성 사업', '대상: 1987.1.1 ~ 2008.12.31 출생자']))
    age = next(row for row in draft['criteria'] if row['type'] == 'age')
    assert age['values']['birth_start'] == '1987-01-01' and age['values']['birth_end'] == '2008-12-31'
    assert age['engine_rule'] == SUPPORTED_RULES['age']


def test_all_rule_bindings_resolve_to_existing_functions():
    for path in SUPPORTED_RULES.values():
        module, name = path.rsplit('.', 1)
        assert callable(getattr(importlib.import_module(module), name))


def test_form_analysis_delegates_to_existing_five_stage_detector_without_auto_confirmation():
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        widget = pymupdf.Widget()
        widget.field_name = '성명'
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.rect = pymupdf.Rect(40, 40, 200, 65)
        page.add_widget(widget)
        draft = analyze_form(pdf.tobytes(), form_no='form_7', title='합성 서식')
    assert draft['form_no'] == 'form_7' and draft['source_kind'] == 'acroform'
    assert not draft['confirmed']
    assert all(row['needs_review'] for row in draft['fields'].values())


def test_invalid_pdf_has_static_value_free_error():
    with pytest.raises(ValueError, match='정상 PDF'):
        analyze_notice(b'SYNTHETIC INVALID PDF')


def test_reanalysis_has_stable_candidate_identifiers():
    pdf = public_pdf(['합성 사업', '공고일: 2026.11.15', '대상: 만18세 ~ 39세', '제출 서류: 주민등록초본'])
    first, second = analyze_notice(pdf), analyze_notice(pdf)
    assert [row['id'] for row in all_candidates(first)] == [row['id'] for row in all_candidates(second)]


@pytest.mark.parametrize('line,kind', [
    ('지원 대상: 만18세 이상 39세 미만 청년', 'age'),
    ('근로 요건: 5개월 이하 연속 근로', 'work_continuity'),
    ('근로 요건: 최대 5개월 계속 근로', 'work_continuity'),
    ('거주 요건: 전북특별자치도 1년 이상 계속 거주', 'residence'),
    ('주민등록초본은 2026-11-15 이후 발급분만 인정', 'issue_date'),
])
def test_unrepresentable_operator_duration_and_document_scope_remain_checklist(line, kind):
    result = analyze_notice(public_pdf(['합성 지원사업', '공고일: 2026-11-15', line]))
    candidates = [row for row in result['criteria'] if row['candidate_type'] == kind]
    assert candidates and all(row['type'] == 'checklist' and row['engine_rule'] is None for row in candidates)
    assert all(row['needs_review'] for row in candidates)


def test_supported_age_does_not_discard_mixed_unemployment_qualification():
    line = '지원 대상: 만18세 ~ 39세 미취업 청년만 가능하여야 함'
    result = analyze_notice(public_pdf(['합성 지원사업', '공고일: 2026-11-15', line]))
    assert any(row['type'] == 'age' for row in result['criteria'])
    remainder = next(row for row in result['criteria'] if row['type'] == 'checklist')
    assert remainder['quote'] == line and '미취업' in remainder['label'] and remainder['needs_review']


def test_condition_specific_basis_does_not_inherit_document_issue_basis():
    result = analyze_notice(public_pdf(['합성 지원사업', '서류발급 기준일: 2026-10-01',
                                       '연령 기준일: 2026-12-31', '지원 대상: 만18세 ~ 39세']))
    age = next(row for row in result['criteria'] if row['candidate_type'] == 'age')
    assert age['values']['basis_date'] == '2026-12-31'
    assert age['basis_evidence']['quote'] == '연령 기준일: 2026-12-31'


def test_conflicting_common_basis_dates_require_manual_age_verification():
    result = analyze_notice(public_pdf(['합성 지원사업', '공고일: 2026-10-01',
                                       '기준일: 2026-12-31', '지원 대상: 만18세 ~ 39세']))
    age = next(row for row in result['criteria'] if row['candidate_type'] == 'age')
    assert age['type'] == 'checklist' and age['values']['basis_date'] is None


def test_conflicting_periods_are_not_resolved_by_first_match():
    result = analyze_notice(public_pdf(['합성 지원사업', '신청 기간: 2026-11-16 ~ 2026-12-15',
                                       '신청 기간 변경: 2026-11-17 ~ 2026-12-16']))
    assert result['period']['value'] == {'apply_start': '', 'apply_end': ''}
    assert len(result['period']['sources']) == 2 and result['period']['needs_review']
    assert any('서로 다른 신청 기간' in warning for warning in result['warnings'])


def test_residence_and_work_retain_separate_basis_citations():
    result = analyze_notice(public_pdf(['합성 지원사업', '공고일: 2026-11-15',
        '거주 요건: 전북특별자치도 거주자', '계속 근로 요건: 5개월 이상 연속 근로']))
    for row in result['criteria']:
        if row['type'] in {'residence', 'work_continuity'}:
            assert row['basis_evidence']['value'] == '2026-11-15'
            assert row['basis_evidence']['quote'] == '공고일: 2026-11-15'
            assert row['basis_evidence']['needs_review']


def test_income_table_values_retain_each_source_row():
    from demo.backend.rules.scoring import MEDIAN_INCOME_140
    rows = [f'{size}인 ' + ' '.join(f'{row[key]:,}' for key in ('직장', '지역', '혼합') if key in row)
            for size, row in MEDIAN_INCOME_140.items()]
    result = analyze_notice(public_pdf(['합성 지원사업', '소득 기준: 중위소득 140% 이하', '가구원 직장 지역 혼합', *rows]))
    income = next(row for row in result['criteria'] if row['candidate_type'] == 'income')
    assert {row['quote'] for row in income['table_evidence']} >= set(rows)
    assert all(row['page'] == 1 and row['needs_review'] for row in income['table_evidence'])


def test_issue_basis_without_lower_bound_operator_is_not_an_automatic_cutoff():
    result = analyze_notice(public_pdf(['합성 지원사업', '서류 발급 기준일: 2026-11-15']))
    issue = next(row for row in result['criteria'] if row['candidate_type'] == 'issue_date')
    assert issue['type'] == 'checklist'


def test_duplicate_conflicting_income_rows_cannot_silently_overwrite_one_another():
    from demo.backend.rules.scoring import MEDIAN_INCOME_140
    rows = [f'{size}인 ' + ' '.join(f'{row[key]:,}' for key in ('직장', '지역', '혼합') if key in row)
            for size, row in MEDIAN_INCOME_140.items()]
    result = analyze_notice(public_pdf(['합성 지원사업', '소득 기준: 중위소득 140% 이하',
        '가구원 직장 지역 혼합', '1인 1 2 3', '가구원 직장 지역 혼합', *rows]))
    income = next(row for row in result['criteria'] if row['candidate_type'] == 'income')
    assert income['type'] == 'checklist' and income['values']['household_table'] == {}


def test_distinct_title_candidates_require_manual_choice():
    result = analyze_notice(public_pdf(['합성 청년 지원사업', '합성 주거 지원사업']))
    assert result['title']['value'] == '' and result['title']['needs_review']
    assert any('사업 제목 후보' in warning for warning in result['warnings'])



def test_disjunction_between_supported_conditions_is_not_silently_read_as_one_range():
    result = analyze_notice(public_pdf(['합성 지원사업', '공고일: 2026-11-15',
        '지원 대상: 만18세 ~ 39세 또는 만60세 ~ 65세']))
    assert result['criteria'] and all(row['type'] == 'checklist' and row['engine_rule'] is None for row in result['criteria'])


OVERVIEW_NOTICE = [
    '2026 합성 청년 지원사업 모집 공고',
    '1. 모집개요',
    '가. 사업목적: 지역 청년의 구직 활동을 돕습니다.',
    '나. 지원대상: 전북특별자치도 거주 만 18세 이상 39세 이하 청년',
    '다. 지원내용: 월 30만원, 최대 6개월 지원',
    '(구직활동 계획서 제출자에 한함)',
    '라. 모집인원: 100명',
    '2. 신청자격',
    '가. 공고일 현재 미취업 상태인 사람',
    '3. 신청방법',
    '신청 방법: 온라인 신청',
    '문의: 합성청년센터 063-000-0000',
]


def test_overview_section_becomes_guidance_with_one_paragraph_per_item():
    draft = analyze_notice(public_pdf(OVERVIEW_NOTICE))
    guidance = draft['guidance']
    assert guidance['value'].split('\n') == [
        '2026 합성 청년 지원사업 모집 공고 신청 안내',
        '가. 사업목적: 지역 청년의 구직 활동을 돕습니다.',
        '나. 지원대상: 전북특별자치도 거주 만 18세 이상 39세 이하 청년',
        '다. 지원내용: 월 30만원, 최대 6개월 지원 (구직활동 계획서 제출자에 한함)',
        '라. 모집인원: 100명',
        '신청 방법: 온라인 신청',
        '문의: 합성청년센터 063-000-0000',
    ]
    # The next same-level heading ends the overview: eligibility text is not guidance.
    assert '미취업' not in guidance['value']
    assert guidance['quote'] == '1. 모집개요' and guidance['page'] == 1 and guidance['needs_review']
    assert [row['value'] for row in guidance['sources']][:2] == ['1. 모집개요', '가. 사업목적: 지역 청년의 구직 활동을 돕습니다.']
    assert all(row['page'] == 1 and row['quote'] for row in guidance['sources'])


def test_overview_with_box_heading_stops_at_next_box_but_not_at_nested_numbers():
    draft = analyze_notice(public_pdf([
        '합성 지원사업 공고', '□ 사업 개요', '1) 지원대상: 합성 청년', '2) 지원규모: 50명',
        '□ 신청 자격', '1) 미취업자']))
    assert draft['guidance']['value'].split('\n') == [
        '합성 지원사업 공고 신청 안내', '1) 지원대상: 합성 청년', '2) 지원규모: 50명']


def test_overview_without_marker_stops_at_a_short_section_line():
    draft = analyze_notice(public_pdf([
        '합성 지원사업 공고', '모집 개요', '- 지원대상: 합성 청년', '- 지원내용: 교육비 지원', '신청 자격', '- 미취업자']))
    assert draft['guidance']['value'].split('\n') == [
        '합성 지원사업 공고 신청 안내', '- 지원대상: 합성 청년', '- 지원내용: 교육비 지원']


def test_notice_without_overview_keeps_the_field_by_field_guidance():
    draft = analyze_notice(public_pdf(['합성 지원사업 공고', '지원 대상: 합성 청년', '신청 방법: 온라인 신청']))
    assert draft['guidance']['value'].split('\n')[1] == '지원 대상: 합성 청년'
