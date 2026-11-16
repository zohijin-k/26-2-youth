"""Evaluation-only supplements: a separate "보충 포함" column, original keys untouched."""
import json
from pathlib import Path

from demo.backend.tools import measure_form_drafts as tool
from demo.backend.tools.measure_form_drafts import compare, iou, markdown, measure, supplement, totals

EVAL = Path(tool.__file__).resolve().parents[2] / "fixtures" / "form_draft_eval"
COORDS = Path(tool.__file__).resolve().parents[2] / "fixtures" / "form_coords"


def _reference():
    return {"fields": {"name": {"type": "text", "page": 0, "box": [0, 0, 20, 20]}}}


def _draft():
    return {"page_sizes": [{"width": 500, "height": 500}],
            "fields": {"a": {"type": "text", "page": 0, "box": [0, 0, 20, 20]},
                       "b": {"type": "text", "page": 0, "box": [100, 100, 200, 120]}}}


def test_supplement_adds_a_separate_column_and_keeps_original_values(tmp_path, monkeypatch):
    (tmp_path / "synthetic.extra.json").write_text(json.dumps(
        {"status": "사람 확인 필요", "fields": {"supplement.blank": {"type": "text", "page": 0, "box": [100, 100, 200, 120]}}}))
    monkeypatch.setattr(tool, "EVAL_DIR", tmp_path)
    base = compare(_reference(), _draft())
    row = tool.measured_row("synthetic.pdf", "synthetic", _reference(), _draft())
    assert {key: row[key] for key in base} == base and base["precision"] == .5
    assert row["supplement_fields"] == 1
    assert row["supplemented"]["iou_match_rate"] == 1.0 and row["supplemented"]["precision"] == 1.0
    total = totals([row])
    assert total["precision"] == .5 and total["supplemented"]["precision"] == 1.0
    lines = markdown([row]).splitlines()
    assert lines[0].endswith("| 보충 칸 | 보충 포함 일치율 | 보충 포함 정밀도 |")
    assert lines[2].startswith("| synthetic.pdf | 1 | 2 | 1 | 100.0% | 100.0% | 50.0% |") and lines[2].endswith("| 1 | 100.0% | 100.0% |")


def test_without_supplement_file_the_column_repeats_the_original(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "EVAL_DIR", tmp_path)
    assert supplement("missing") == {} and supplement("../form_coords/서식1") == {}
    row = tool.measured_row("synthetic.pdf", "synthetic", _reference(), _draft())
    assert row["supplement_fields"] == 0
    assert row["supplemented"]["iou_match_rate"] == row["iou_match_rate"]
    # Rows from older callers without the supplement keys still render.
    plain = {key: value for key, value in row.items() if key not in {"supplement_fields", "supplemented"}}
    assert markdown([plain]).splitlines()[2].endswith("| – | – | – |")


def test_supplement_fixture_is_evaluation_only_and_new_to_the_coordinates():
    files = sorted(EVAL.glob("*.extra.json"))
    assert [path.name for path in files] == ["job_interview_confirmation.extra.json"]
    for path in files:
        raw = json.loads(path.read_text())
        assert raw["status"] == "사람 확인 완료(2026-11-16)" and raw["fields"]
        coords = json.loads((COORDS / path.name.replace(".extra.json", ".json")).read_text())
        for key, field in raw["fields"].items():
            assert key.startswith("supplement.") and key not in coords["fields"]
            assert all(iou(field["box"], original["box"]) < .5 for original in coords["fields"].values())


def test_measure_reports_the_supplemented_interview_confirmation():
    rows = {row["template"]: row for row in measure()}
    row = rows["job_interview_confirmation.pdf"]
    assert row["reference_fields"] == 5 and row["supplement_fields"] == 12
    assert row["supplemented"]["reference_fields"] == 17
    assert all(other["supplement_fields"] == 0 for name, other in rows.items() if name != "job_interview_confirmation.pdf")
