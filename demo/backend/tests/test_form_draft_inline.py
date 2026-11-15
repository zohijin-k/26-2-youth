"""Synthetic PDFs for inline form-draft rules: choice words, date blanks,
label blanks, signature marks and false-positive guards.

Every document is generated here with PyMuPDF; no fixture file is read.
"""
import time

import pymupdf

from demo.backend.forms.draft import draft_layout

FONT = {"fontname": "korea", "fontsize": 11}


def _page(width=500, height=700):
    document = pymupdf.open()
    return document, document.new_page(width=width, height=height)


def _text(page, x, y, text, size=11):
    page.insert_text((x, y), text, fontname="korea", fontsize=size)


def _fields(document):
    layout = draft_layout(document.tobytes())
    document.close()
    fields = list(layout["fields"].values())
    assert all(field["needs_review"] for field in fields) and not layout["confirmed"]
    return fields


def _inside(box, left, right):
    return left - .5 <= box[0] and box[2] <= right + .5


# a. Choice words without printed boxes ------------------------------------------------

def test_choice_word_pair_becomes_grouped_word_checks_without_comma():
    document, page = _page()
    _text(page, 40, 100, "1. 귀하는 해당 지역 거주자입니까?")
    _text(page, 360, 100, "예,")
    _text(page, 390, 100, "아니오")
    checks = [field for field in _fields(document) if field["field_type"] == "check"]
    assert [field["label"] for field in checks] == ["예", "아니오"]
    assert checks[0]["group"] == checks[1]["group"]
    assert checks[0]["box"][2] <= 371.5  # the comma glyph is outside the 예 box
    assert _inside(checks[1]["box"], 389, 424)
    assert all(field["confidence"] == .6 and field["type"] == "check" for field in checks)


def test_multi_word_choice_pairs_are_joined():
    document, page = _page()
    _text(page, 40, 100, "동의함,")
    _text(page, 110, 100, "동의하지 않음")
    _text(page, 40, 140, "해당")
    _text(page, 90, 140, "해당 없음")
    labels = sorted(field["label"] for field in _fields(document) if field["field_type"] == "check")
    assert labels == ["동의하지 않음", "동의함", "해당", "해당 없음"]


def test_choice_word_inside_sentence_is_not_a_check():
    document, page = _page()
    _text(page, 40, 100, "예시를 참고하세요 예정된 일정은 없음")
    _text(page, 40, 140, "아니오 라고 적은 예외 사항")
    assert [field for field in _fields(document) if field["field_type"] == "check"] == []


def test_choice_header_split_by_cell_border_is_not_a_word_pair():
    document, page = _page()
    for x in (300, 340, 400):
        page.draw_line((x, 80), (x, 120))
    _text(page, 310, 100, "예")
    _text(page, 350, 100, "아니오")
    assert [field for field in _fields(document) if field["field_type"] == "check"] == []


def test_choice_words_next_to_printed_boxes_use_the_boxes_only():
    document, page = _page()
    for x, word in ((300, "예"), (360, "아니오")):
        page.draw_rect(pymupdf.Rect(x, 90, x + 10, 100))
        _text(page, x + 14, 100, word)
    checks = [field for field in _fields(document) if field["field_type"] == "check"]
    assert len(checks) == 2
    assert {tuple(field["box"]) for field in checks} == {(300, 90, 310, 100), (360, 90, 370, 100)}


# b. Inline date blanks --------------------------------------------------------------

def test_printed_century_and_spaced_date_tokens_yield_three_blanks():
    document, page = _page()
    _text(page, 200, 300, "20")
    _text(page, 250, 300, "년")
    _text(page, 300, 300, "월")
    _text(page, 350, 300, "일")
    dates = [field for field in _fields(document) if field["field_type"] == "date"]
    assert [field["label"] for field in dates] == ["연", "월", "일"]
    # Each blank runs from the previous token's right edge to the next token.
    assert [round(field["box"][2]) for field in dates] == [249, 299, 349]
    assert all(right - left >= 25 for left, _, right, _ in (field["box"] for field in dates))
    assert all(field["confidence"] == .6 and field["type"] == "text" for field in dates)


def test_filled_or_tight_dates_do_not_yield_blanks():
    document, page = _page()
    _text(page, 100, 300, "2026년 11월 15일")
    _text(page, 100, 340, "2026 년")  # printed year with a single space
    _text(page, 180, 340, "월")
    _text(page, 230, 340, "일")
    dates = [field for field in _fields(document) if field["field_type"] == "date"]
    assert [field["label"] for field in dates] == ["월", "일"]
    assert all(field["box"][1] > 320 for field in dates)


# c. Label blanks --------------------------------------------------------------------

def test_colon_label_blank_runs_to_cell_border_with_autofill():
    document, page = _page()
    page.draw_line((420, 80), (420, 200))
    _text(page, 60, 100, "성명 :")
    _text(page, 60, 140, "생년월일:")
    fields = {field["autofill_source"]: field for field in _fields(document)}
    assert fields["name"]["field_type"] == "text" and fields["name"]["box"][2] == 417
    assert fields["birth"]["field_type"] == "date" and fields["birth"]["box"][2] == 417
    assert fields["name"]["box"][0] > 90 and fields["name"]["confidence"] == .55


def test_underlined_label_without_colon_is_a_blank():
    document, page = _page()
    _text(page, 60, 100, "연락처")
    page.draw_line((100, 103), (300, 103), width=.5)
    fields = _fields(document)
    assert len(fields) == 1 and fields[0]["autofill_source"] == "mobile"
    assert _inside(fields[0]["box"], 100, 300)


def test_filled_or_unmarked_labels_do_not_yield_blanks():
    document, page = _page()
    _text(page, 60, 100, "성명: 홍길동")
    _text(page, 60, 140, "주소")
    _text(page, 60, 180, "수집 항목: 성명, 생년월일, 연락처")
    assert _fields(document) == []


# d. Signature marks -----------------------------------------------------------------

def test_name_blank_and_seal_mark_are_split_without_overlap():
    document, page = _page()
    _text(page, 200, 400, "성 명:")
    _text(page, 330, 400, "(서명 또는 인)")
    fields = _fields(document)
    name = next(field for field in fields if field["autofill_source"] == "name")
    sign = next(field for field in fields if field["field_type"] == "signature")
    assert sign["type"] == "image" and sign["box"][0] >= name["box"][2]
    assert sign["box"][0] == 328 and name["confidence"] == sign["confidence"] == .55


def test_seal_mark_after_plain_blank_includes_the_blank():
    document, page = _page()
    _text(page, 100, 400, "확인자")
    _text(page, 260, 400, "(인)")
    fields = _fields(document)
    assert len(fields) == 1 and fields[0]["field_type"] == "signature"
    assert fields[0]["box"][0] < 200 and fields[0]["box"][2] > 270


def test_signature_word_in_sentence_or_attached_text_is_not_a_mark():
    document, page = _page()
    _text(page, 60, 100, "본인은 아래 내용에 서명합니다")
    _text(page, 60, 140, "홍길동(인)")
    assert _fields(document) == []


# e. False-positive guards -----------------------------------------------------------

def test_large_notice_cell_with_date_keeps_only_inline_blanks():
    document, page = _page(595, 841)
    page.draw_rect(pymupdf.Rect(50, 300, 545, 700))
    for row in range(5):
        _text(page, 70, 340 + 20 * row, "위 내용을 확인하였으며 관련 법령에 따라 처리합니다")
    _text(page, 250, 560, "20")
    _text(page, 290, 560, "년")
    _text(page, 330, 560, "월")
    _text(page, 370, 560, "일")
    fields = _fields(document)
    area = 595 * 841
    assert all((field["box"][2] - field["box"][0]) * (field["box"][3] - field["box"][1]) <= .15 * area for field in fields)
    assert sorted(field["label"] for field in fields) == ["연", "월", "일"]


def test_short_date_cell_still_yields_cell_hint():
    document, page = _page()
    for y in (40, 80):
        page.draw_line((40, y), (440, y))
    for x in (40, 440):
        page.draw_line((x, 40), (x, 80))
    _text(page, 50, 65, "신청일")
    fields = _fields(document)
    assert len(fields) == 1 and fields[0]["field_type"] == "date" and fields[0]["confidence"] == .52


def test_leading_box_before_sentence_is_a_bullet_not_a_check():
    document, page = _page()
    _text(page, 40, 100, "□ 수집하는 개인정보의 항목 및 이용 목적")
    page.draw_rect(pymupdf.Rect(40, 200, 52, 212))
    _text(page, 58, 211, "제공받는 자의 이용 목적 안내")
    assert [field for field in _fields(document) if field["field_type"] == "check"] == []


def test_boxes_with_choices_or_stacked_options_are_kept():
    document, page = _page()
    _text(page, 40, 100, "□ 동의함 □ 동의하지 않음")
    _text(page, 40, 200, "□ 기초생활 수급 가구")
    _text(page, 40, 216, "□ 그 외 일반 가구 해당")
    checks = [field for field in _fields(document) if field["field_type"] == "check"]
    assert len(checks) == 4


# Ordering, duplicates and performance ----------------------------------------------

def test_acroform_widgets_still_suppress_inline_rules():
    document, page = _page()
    _text(page, 360, 100, "예,")
    _text(page, 390, 100, "아니오")
    _text(page, 60, 200, "성명 :")
    widget = pymupdf.Widget()
    widget.field_name = "이메일"
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(60, 300, 260, 320)
    page.add_widget(widget)
    fields = _fields(document)
    assert len(fields) == 1 and fields[0]["autofill_source"] == "email"


def test_label_blank_inside_label_cell_yields_to_value_cell():
    document, page = _page()
    for y in (80, 110):
        page.draw_line((40, y), (440, y))
    for x in (40, 120, 440):
        page.draw_line((x, 80), (x, 110))
    _text(page, 50, 100, "성명:")
    fields = _fields(document)
    assert len(fields) == 1 and fields[0]["confidence"] == .72 and fields[0]["box"][0] == 122


def test_overlapping_candidates_keep_the_more_confident_one_in_order():
    from demo.backend.forms.draft import _deduplicated

    def field(name, box, confidence, page=0):
        return {"label": name, "box": box, "confidence": confidence, "page": page}

    candidates = [field("low", [0, 0, 100, 20], .52), field("other", [200, 0, 260, 20], .6),
                  field("high", [5, 0, 100, 20], .6), field("next page", [0, 0, 100, 20], .5, page=1)]
    assert [item["label"] for item in _deduplicated(candidates)] == ["other", "high", "next page"]


def test_dense_vector_page_drafts_under_two_seconds():
    document, page = _page(595, 841)
    shape = page.new_shape()
    for index in range(4000):
        x, y = 40 + (index % 80) * 6, 100 + (index // 80) * 12
        shape.draw_line((x, y), (x + 4, y))
    shape.finish(width=.3)
    shape.commit()
    _text(page, 360, 780, "예,")
    _text(page, 390, 780, "아니오")
    started = time.perf_counter()
    fields = _fields(document)
    assert time.perf_counter() - started < 2
    assert len([field for field in fields if field["field_type"] == "check"]) == 2
