"""Synthetic PDFs for the follow-up draft rules: general labels, dotted dates,
boxes inside words, label cleanup and the snap page range.

Every document is generated here with PyMuPDF; no fixture file is read.
"""
import pymupdf

from demo.backend.forms.draft import draft_layout
from demo.backend.tests.test_form_snap import upload
from demo.backend.tests.test_postings_api import client, storage  # noqa: F401


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


def _word(page, text):
    return next(word for word in page.get_text("words") if word[4] == text)


# a. General labels -------------------------------------------------------------------

def test_general_labels_with_colons_yield_blanks_without_autofill():
    document, page = _page()
    _text(page, 40, 100, "(은행명 :")
    _text(page, 150, 100, "/ 계좌번호 :")
    _text(page, 330, 100, "/ 예금주 :")
    _text(page, 470, 100, ")")
    _text(page, 40, 160, "근무처 명 :")
    _text(page, 40, 220, "보호자:")
    fields = _fields(document)
    labels = {field["label"]: field for field in fields}
    assert set(labels) == {"은행명", "계좌번호", "예금주", "근무처 명", "보호자"}
    assert all(field["autofill_source"] is None and field["field_type"] == "text" for field in fields)
    # Each blank ends before the next printed separator on the row.
    assert labels["은행명"]["box"][2] < 150 and labels["계좌번호"]["box"][2] < 330
    assert labels["예금주"]["box"][2] < 470


def test_general_label_words_in_lists_filled_or_unmarked_are_not_blanks():
    document, page = _page()
    _text(page, 40, 100, "수집범위 성명, 은행명, 계좌번호 등")
    _text(page, 40, 140, "소속: 합성기관")
    _text(page, 40, 180, "확인자 직위")
    _text(page, 300, 180, "부서")
    _text(page, 40, 220, "사업명 안내는 공고문을 참고하세요")
    assert _fields(document) == []


def test_existing_autofill_sources_are_not_widened():
    document, page = _page()
    _text(page, 40, 100, "신청인 :")
    _text(page, 40, 140, "성명 :")
    sources = {field["label"]: field["autofill_source"] for field in _fields(document)}
    assert sources == {"신청인": None, "성명": "name"}


# b. Dotted dates ---------------------------------------------------------------------

def test_dotted_date_with_printed_century_yields_three_blanks():
    document, page = _page()
    for x, token in ((200, "20"), (250, "."), (290, "."), (330, ".")):
        _text(page, x, 300, token)
    dates = [field for field in _fields(document) if field["field_type"] == "date"]
    assert [field["label"] for field in dates] == ["연", "월", "일"]
    assert [round(field["box"][2]) for field in dates] == [249, 289, 329]
    assert all(field["confidence"] == .6 and field["type"] == "text" for field in dates)


def test_dotted_date_with_printed_year_yields_month_and_day():
    document, page = _page()
    for x, token in ((150, "2026."), (260, "."), (300, ".")):
        _text(page, x, 300, token)
    dates = [field for field in _fields(document) if field["field_type"] == "date"]
    assert [field["label"] for field in dates] == ["월", "일"]
    assert dates[0]["box"][0] > 205 and dates[1]["box"][2] < 300


def test_decimals_numbering_and_filled_dotted_dates_are_not_blanks():
    document, page = _page()
    _text(page, 40, 100, "1. 신청 자격")
    _text(page, 40, 140, "10. 제출 서류는 3.14 배수로 계산")
    _text(page, 40, 180, "2026. 11. 15.")
    _text(page, 40, 220, "2026.11.15.")
    for x, token in ((40, "2026."), (97, "."), (110, ".")):  # dots printed without blanks between them
        _text(page, x, 260, token)
    for x, token in ((40, "1."), (80, "."), (120, ".")):  # single-digit numbering
        _text(page, x, 300, token)
    assert [field for field in _fields(document) if field["field_type"] == "date"] == []


# c. Box glyphs inside words ----------------------------------------------------------

def test_box_inside_word_is_placed_on_its_glyph():
    document, page = _page()
    _text(page, 100, 100, "참여 여부□ 미참여")
    _text(page, 100, 140, "동의□")
    word, second = _word(page, "여부□"), _word(page, "동의□")
    checks = sorted((field for field in _fields(document) if field["field_type"] == "check"), key=lambda f: f["box"][1])
    assert len(checks) == 2
    assert checks[0]["box"][0] > word[0] + 15 and checks[0]["box"][2] <= word[2] + .5
    assert checks[1]["box"][0] > second[0] + 15 and checks[1]["box"][2] <= second[2] + .5
    assert checks[0]["label"].startswith("미참여")


def test_leading_box_keeps_its_position_and_plain_text_has_none():
    document, page = _page()
    _text(page, 100, 100, "□동의 □미동의")
    _text(page, 100, 160, "여부 확인 후 동의")
    first, second = _word(page, "□동의"), _word(page, "□미동의")
    checks = sorted((field["box"] for field in _fields(document) if field["field_type"] == "check"))
    height = first[3] - first[1]
    assert [round(box[0], 1) for box in checks] == [round(first[0], 1), round(second[0], 1)]
    assert all(round(box[2] - box[0], 1) == round(min(height, first[2] - first[0]), 1) for box in checks)
    assert all(box[1] < 120 for box in checks)


# d. Label cleanup --------------------------------------------------------------------

def test_label_drops_trailing_colons_and_keeps_the_anchor():
    document, page = _page()
    _text(page, 60, 100, "성명 :")
    _text(page, 60, 140, "생년월일：")
    _text(page, 60, 180, "주소:")
    fields = {field["autofill_source"]: field for field in _fields(document)}
    assert [fields[key]["label"] for key in ("name", "birth", "address")] == ["성명", "생년월일", "주소"]
    assert [fields[key]["anchor"] for key in ("name", "birth", "address")] == ["성명 :", "생년월일：", "주소:"]


def test_label_without_trailing_colon_is_unchanged():
    document, page = _page()
    _text(page, 60, 100, "연락처")
    page.draw_line((100, 103), (300, 103), width=.5)
    _text(page, 60, 160, "구분: 내용")
    for x in (40, 200):
        page.draw_line((x, 140), (x, 180))
    fields = _fields(document)
    assert [(field["label"], field["anchor"]) for field in fields] == [("연락처", "연락처")]


# e. Snap page range ------------------------------------------------------------------

def test_snap_route_rejects_pages_outside_the_document(client):  # noqa: F811
    base, form_id = upload(client)
    path = f'{base}/workspace/forms/{form_id}/snap'
    assert client.post(path, json={'page': -1, 'x': 300, 'y': 60}).status_code == 422
    assert client.post(path, json={'page': 1, 'x': 300, 'y': 60}).status_code == 422  # one-page PDF
    assert client.post(path, json={'page': 0, 'x': 300, 'y': 60}).status_code == 200
