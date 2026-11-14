"""Generated synthetic PDF coverage for conservative field drafting."""
import pymupdf
import pytest

from demo.backend.forms.draft import draft_layout


def synthetic_table():
    document = pymupdf.open()
    page = document.new_page(width=500, height=500)
    for y in (40, 80, 120, 160, 200):
        page.draw_line((40, y), (440, y))
    for x in (40, 160, 440):
        page.draw_line((x, 40), (x, 200))
    for index, text in enumerate(("성명", "금액 (원)", "서명", "년 월 일")):
        page.insert_text((50, 65 + 40 * index), text, fontname="korea", fontsize=11)
    for x, text in ((50, "동의"), (150, "미동의")):
        page.draw_rect(pymupdf.Rect(x, 250, x + 10, 260))
        page.insert_text((x + 16, 260), text, fontname="korea", fontsize=10)
    return document


def test_table_drafts_text_number_signature_date_and_checkboxes_with_review_gate():
    with synthetic_table() as document:
        layout = draft_layout(document.tobytes())
    fields = list(layout["fields"].values())
    assert {field["field_type"] for field in fields} == {"text", "number", "signature", "date", "check"}
    assert next(field for field in fields if field["label"] == "성명")["autofill_source"] == "name"
    assert next(field for field in fields if field["field_type"] == "signature")["type"] == "image"
    checks = [field for field in fields if field["field_type"] == "check"]
    assert len(checks) == 2 and checks[0]["group"] == checks[1]["group"]
    assert all(field["needs_review"] and 0 <= field["confidence"] <= 1 for field in fields)
    assert all(len(field["box"]) == 4 and field["page"] == 0 for field in fields)
    assert not layout["confirmed"] and layout["status"] == "draft"
    assert layout["page_sizes"] == [{"width": 500.0, "height": 500.0}]


def test_acroform_widgets_take_priority_over_table_guesses():
    with synthetic_table() as document:
        page = document[0]
        widget = pymupdf.Widget()
        widget.field_name = "연락처"
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_flags = pymupdf.PDF_FIELD_IS_REQUIRED
        widget.rect = pymupdf.Rect(100, 320, 250, 350)
        page.add_widget(widget)
        layout = draft_layout(document.tobytes(), form_no="uploaded_2", title="합성")
    assert layout["source_kind"] == "acroform" and layout["form_no"] == "uploaded_2"
    assert len(layout["fields"]) == 1
    field = next(iter(layout["fields"].values()))
    assert field["autofill_source"] == "mobile" and field["required"]
    assert field["box"] == [100, 320, 250, 350]
    assert field["needs_review"] and not layout["confirmed"]


@pytest.mark.parametrize("with_image", [False, True])
def test_blank_and_image_only_pdf_request_manual_addition(with_image):
    with pymupdf.open() as document:
        page = document.new_page()
        if with_image:
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
            pixmap.clear_with(200)
            page.insert_image(pymupdf.Rect(20, 20, 400, 500), stream=pixmap.tobytes("png"))
        layout = draft_layout(document.tobytes())
    assert layout["fields"] == {} and layout["status"] == "manual_required"
    assert "직접" in layout["message"] and not layout["confirmed"]


def test_standalone_blank_rectangle_without_label_does_not_invent_input():
    with pymupdf.open() as document:
        page = document.new_page()
        page.draw_rect(pymupdf.Rect(40, 40, 300, 100))
        layout = draft_layout(document.tobytes())
    assert layout["fields"] == {}


def test_multi_page_boxes_keep_page_coordinates_and_opaque_identifiers():
    with synthetic_table() as document:
        page = document.new_page(width=400, height=600)
        widget = pymupdf.Widget()
        widget.field_name = "주소"
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.rect = pymupdf.Rect(30, 40, 300, 70)
        page.add_widget(widget)
        layout = draft_layout(document.tobytes())
    assert set(layout["fields"]) == {"f0000"}
    assert layout["fields"]["f0000"]["page"] == 1
    assert layout["page_sizes"][1] == {"width": 400.0, "height": 600.0}


def test_invalid_pdf_is_rejected_without_echoing_source():
    with pytest.raises(ValueError, match="서식 PDF를 읽을 수 없습니다"):
        draft_layout(b"SYNTHETIC INVALID PDF")


def test_encrypted_pdf_is_rejected():
    with synthetic_table() as document:
        raw = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="synthetic-owner", user_pw="synthetic-user")
    with pytest.raises(ValueError, match="암호"):
        draft_layout(raw)


def test_measurement_matching_is_one_to_one_and_page_scoped():
    from demo.backend.tools.measure_form_drafts import compare

    reference = {"fields": {"a": {"type": "text", "page": 0, "box": [0, 0, 20, 20]},
                            "b": {"type": "image", "page": 1, "box": [0, 0, 20, 20]}}}
    candidates = {"fields": {"one": {"type": "text", "page": 0, "box": [0, 0, 20, 20]},
                             "duplicate": {"type": "text", "page": 0, "box": [0, 0, 20, 20]}}}
    result = compare(reference, candidates)
    assert result["iou_matches"] == 1 and result["iou_match_rate"] == .5
    assert result["kind_match_rate"] == 1


def test_measurement_kind_accuracy_counts_only_geometric_matches():
    from demo.backend.tools.measure_form_drafts import compare

    reference = {"fields": {"sign": {"type": "image", "page": 0, "box": [0, 0, 20, 20]}}}
    candidates = {"fields": {"text": {"type": "text", "page": 0, "box": [0, 0, 20, 20]}}}
    result = compare(reference, candidates)
    assert result["iou_matches"] == 1 and result["kind_match_rate"] == 0
