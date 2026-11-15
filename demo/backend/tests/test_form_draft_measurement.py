"""Precision, oversize and miss reporting in the form draft measurement tool."""
from demo.backend.tools.measure_form_drafts import compare, markdown, totals


def _reference():
    return {"fields": {"name": {"type": "text", "page": 0, "box": [0, 0, 20, 20]},
                       "sign": {"type": "image", "page": 0, "box": [100, 100, 140, 120]}}}


def test_precision_false_fields_and_missed_names():
    drafted = {"page_sizes": [{"width": 500, "height": 500}],
               "fields": {"a": {"type": "text", "field_type": "text", "page": 0, "box": [0, 0, 20, 20], "label": "성명"},
                          "b": {"type": "check", "field_type": "check", "page": 0, "box": [300, 300, 310, 310],
                                "label": "가" * 30}}}
    result = compare(_reference(), drafted)
    assert result["precision"] == .5 and result["false_fields"] == 1
    assert result["missed"] == [{"name": "sign", "type": "image", "page": 0, "box": [100, 100, 140, 120]}]
    assert len(result["extra"]) == 1
    extra = result["extra"][0]
    assert extra["field_type"] == "check" and extra["box"] == [300, 300, 310, 310]
    assert extra["label"] == "가" * 20


def test_duplicate_match_is_not_false_field_and_original_keys_remain():
    drafted = {"fields": {"one": {"type": "text", "page": 0, "box": [0, 0, 20, 20]},
                          "dup": {"type": "text", "page": 0, "box": [0, 0, 20, 21]}}}
    result = compare(_reference(), drafted)
    assert {"reference_fields", "draft_fields", "iou_matches", "iou_match_rate",
            "kind_matches", "kind_match_rate"} <= set(result)
    assert result["iou_matches"] == 1 and result["false_fields"] == 0 and result["precision"] == .5


def test_oversized_counts_fields_over_fifteen_percent_of_page():
    drafted = {"page_sizes": [{"width": 100, "height": 100}],
               "fields": {"big": {"type": "text", "page": 0, "box": [0, 0, 50, 40]},
                          "edge": {"type": "text", "page": 0, "box": [0, 0, 15, 10]}}}
    assert compare(_reference(), drafted)["oversized"] == 1
    # Without page sizes the size cannot be judged and nothing is counted.
    assert compare(_reference(), {"fields": drafted["fields"]})["oversized"] == 0


def test_empty_draft_has_zero_precision_and_every_reference_missed():
    result = compare(_reference(), {"fields": {}})
    assert result["precision"] == 0 and result["false_fields"] == 0
    assert [row["name"] for row in result["missed"]] == ["name", "sign"]


def test_totals_are_micro_averaged_and_rendered_as_last_row():
    rows = [{"template": "a.pdf", "reference_fields": 10, "draft_fields": 5, "iou_matches": 5, "iou_match_rate": .5,
             "kind_matches": 5, "kind_match_rate": 1.0, "precision": 1.0, "false_fields": 0, "oversized": 0},
            {"template": "b.pdf", "reference_fields": 2, "draft_fields": 5, "iou_matches": 1, "iou_match_rate": .5,
             "kind_matches": 1, "kind_match_rate": 1.0, "precision": .2, "false_fields": 4, "oversized": 1}]
    total = totals(rows)
    assert total["iou_match_rate"] == .5 and total["precision"] == .6
    assert total["false_fields"] == 4 and total["oversized"] == 1
    assert markdown(rows).splitlines()[4].startswith("| 전체 | 12 | 10 | 6 | 50.0% |")
