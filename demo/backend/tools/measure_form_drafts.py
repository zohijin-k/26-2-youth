"""Measure local template drafting against unchanged hand-authored coordinates.

Run: python -m demo.backend.tools.measure_form_drafts [--json]
Only the repository's public template originals and coordinate fixtures are read.
Metrics are geometric drafting coverage, never document-recognition accuracy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..forms.draft import draft_layout

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
OVERSIZED_PAGE_SHARE = .15


def _area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _rounded(box: list[float]) -> list[float]:
    return [round(float(value), 1) for value in box]


def iou(first: list[float], second: list[float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    overlap = max(0.0, right - left) * max(0.0, bottom - top)
    areas = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1]) + max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    return overlap / (areas - overlap) if areas > overlap else 0.0


def compare(reference: dict[str, Any], drafted: dict[str, Any]) -> dict[str, Any]:
    named = [(name, field) for name, field in reference.get("fields", {}).items() if field.get("box")]
    names = [name for name, _ in named]
    originals = [field for _, field in named]
    candidates = list(drafted.get("fields", {}).values())
    edges = sorted(((iou(original["box"], candidate["box"]), original_no, candidate_no)
                    for original_no, original in enumerate(originals)
                    for candidate_no, candidate in enumerate(candidates)
                    if original.get("page", 0) == candidate.get("page", 0)), reverse=True)
    used_originals: set[int] = set()
    used_candidates: set[int] = set()
    kind_matches = 0
    for overlap, original_no, candidate_no in edges:
        if overlap < .5:
            break
        if original_no in used_originals or candidate_no in used_candidates:
            continue
        used_originals.add(original_no)
        used_candidates.add(candidate_no)
        # Both use the established rendering vocabulary: text/check/image.
        kind_matches += originals[original_no].get("type") == candidates[candidate_no].get("type")
    matched = len(used_originals)
    # A candidate that overlaps no reference at IoU >= 0.5 is a false field; a
    # duplicate of an already matched reference is neither matched nor false.
    near = {candidate_no for overlap, _, candidate_no in edges if overlap >= .5}
    sizes = drafted.get("page_sizes") or []
    oversized = 0
    for candidate in candidates:
        page = candidate.get("page", 0)
        if 0 <= page < len(sizes) and _area(candidate["box"]) > OVERSIZED_PAGE_SHARE * sizes[page]["width"] * sizes[page]["height"]:
            oversized += 1
    missed = [{"name": names[index], "type": original.get("type"), "page": original.get("page", 0),
               "box": _rounded(original["box"])}
              for index, original in enumerate(originals) if index not in used_originals]
    extra = [{"type": candidate.get("type"), "field_type": candidate.get("field_type"),
              "page": candidate.get("page", 0), "box": _rounded(candidate["box"]),
              "label": str(candidate.get("label") or "")[:20]}
             for index, candidate in enumerate(candidates) if index not in near]
    return {"reference_fields": len(originals), "draft_fields": len(candidates), "iou_matches": matched,
            "iou_match_rate": round(matched / len(originals), 4) if originals else 0.0,
            "kind_matches": kind_matches,
            "kind_match_rate": round(kind_matches / matched, 4) if matched else 0.0,
            "precision": round(matched / len(candidates), 4) if candidates else 0.0,
            "false_fields": len(extra), "oversized": oversized, "missed": missed, "extra": extra}


def totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Micro-averaged recall and precision over every measured template."""
    reference = sum(row["reference_fields"] for row in rows)
    drafted = sum(row["draft_fields"] for row in rows)
    matched = sum(row["iou_matches"] for row in rows)
    kinds = sum(row["kind_matches"] for row in rows)
    return {"template": "전체", "reference_fields": reference, "draft_fields": drafted, "iou_matches": matched,
            "iou_match_rate": round(matched / reference, 4) if reference else 0.0,
            "kind_matches": kinds, "kind_match_rate": round(kinds / matched, 4) if matched else 0.0,
            "precision": round(matched / drafted, 4) if drafted else 0.0,
            "false_fields": sum(row["false_fields"] for row in rows),
            "oversized": sum(row["oversized"] for row in rows)}


def measure() -> list[dict[str, Any]]:
    rows = []
    for coordinate in sorted((FIXTURES / "form_coords").glob("*.json")):
        reference = json.loads(coordinate.read_text())
        relative = Path(reference.get("template", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "templates":
            continue
        template = FIXTURES / relative
        if not template.is_file():
            continue
        draft = draft_layout(template.read_bytes(), form_no=reference.get("form_no", coordinate.stem))
        rows.append({"template": template.name, **compare(reference, draft)})
    return rows


def markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["| 서식 | 수작업 칸 | 자동 초안 칸 | IoU ≥ 0.5 일치 | 일치율 | 종류 일치율¹ | 정밀도 | 오검출 | 과대 칸² |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in [*rows, totals(rows)]:
        lines.append(f'| {row["template"]} | {row["reference_fields"]} | {row["draft_fields"]} | {row["iou_matches"]} | {row["iou_match_rate"]:.1%} | {row["kind_match_rate"]:.1%} | {row["precision"]:.1%} | {row["false_fields"]} | {row["oversized"]} |')
    lines.append("\n¹ 기하적으로 일치한 칸 중 기존 렌더링 종류(text/check/image) 일치 비율. 일치 칸이 없으면 0%. 모든 자동 칸은 담당자 확인이 필요합니다.")
    lines.append("² 쪽 면적의 15%를 넘는 자동 칸 수. 전체 줄의 일치율·정밀도는 칸 수 기준(micro) 평균입니다.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="출력을 JSON으로 표시")
    args = parser.parse_args()
    rows = measure()
    print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json else markdown(rows))


if __name__ == "__main__":
    main()
