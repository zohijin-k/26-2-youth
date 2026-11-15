"""Synthetic PDFs for the follow-up decisions: four more plain labels and the
"(서명/인)" signature mark.

Every document is generated here with PyMuPDF; no fixture file is read.
"""
import pymupdf

from demo.backend.forms.draft import draft_layout


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


# Plain labels: 기간, 수령액, 회사명, 담당자 ---------------------------------------------

def test_new_plain_labels_with_colons_yield_blanks_without_autofill():
    document, page = _page()
    for y, label in ((100, "기간 :"), (140, "수령액 :"), (180, "회사명 :"), (220, "담당자:")):
        _text(page, 40, y, label)
    fields = _fields(document)
    assert sorted(field["label"] for field in fields) == sorted(["기간", "수령액", "회사명", "담당자"])
    assert all(field["autofill_source"] is None and field["field_type"] == "text" for field in fields)


def test_new_plain_label_with_underline_yields_a_blank():
    document, page = _page()
    _text(page, 40, 100, "회사명")
    page.draw_line((80, 103), (300, 103), width=.5)
    fields = _fields(document)
    assert [(field["label"], field["autofill_source"]) for field in fields] == [("회사명", None)]


def test_new_plain_label_words_in_lists_filled_or_sentences_are_not_blanks():
    document, page = _page()
    _text(page, 40, 100, "기간, 수령액, 회사명 등을 적습니다")
    _text(page, 40, 140, "담당자: 합성담당")
    _text(page, 40, 180, "지원 기간 안내는 공고문을 참고하세요")
    assert _fields(document) == []


# Signature mark "(서명/인)" -------------------------------------------------------------

def test_sign_or_seal_mark_after_label_blank_is_a_signature():
    document, page = _page()
    _text(page, 40, 100, "담당자 :")
    _text(page, 300, 100, "(서명/인)")
    fields = _fields(document)
    blank = next(field for field in fields if field["field_type"] == "text")
    sign = next(field for field in fields if field["field_type"] == "signature")
    assert blank["label"] == "담당자" and blank["box"][2] < 300
    assert sign["label"] == "(서명/인)" and sign["type"] == "image" and sign["box"][0] >= blank["box"][2]


def test_sign_or_seal_mark_after_plain_word_includes_the_blank():
    document, page = _page()
    _text(page, 100, 400, "확인자")
    _text(page, 260, 400, "(서명/인)")
    fields = _fields(document)
    assert len(fields) == 1 and fields[0]["field_type"] == "signature"
    assert fields[0]["box"][0] < 200 and fields[0]["box"][2] > 300


def test_sign_or_seal_text_in_sentence_or_attached_is_not_a_mark():
    document, page = _page()
    _text(page, 60, 100, "서명/인 란에 날인합니다")
    _text(page, 60, 140, "홍길동(서명/인)")
    assert _fields(document) == []
