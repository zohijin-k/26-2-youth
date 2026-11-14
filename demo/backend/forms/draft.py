"""Conservative, local PDF-to-form drafts; every candidate requires officer review.

Geometry uses PDF points with the same top-left origin as existing form_coords.
No OCR or external service is used. The renderer's text/check/image vocabulary
is retained; ``field_type`` adds the editable semantic type without changing it.
"""
from __future__ import annotations

import re
from typing import Any

import pymupdf

_TOLERANCE = 1.5
_MAX_FIELDS_PER_PAGE = 200
_AUTOFILL = {
    "성명": "name", "이름": "name", "name": "name",
    "생년월일": "birth", "birth": "birth", "연락처": "mobile",
    "휴대폰": "mobile", "전화번호": "mobile", "phone": "mobile",
    "주소": "address", "address": "address", "이메일": "email", "email": "email",
}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _kind(label: str) -> str:
    compact = _compact(label)
    if "서명" in compact or "(인)" in compact or "signature" in compact:
        return "signature"
    if re.search(r"년.*월.*일", compact) or any(x in compact for x in ("날짜", "신청일", "date", "생년월일")):
        return "date"
    if any(x in compact for x in ("금액", "비용", "가격", "원)", "(원", "amount", "cost")) or compact == "원":
        return "number"
    return "text"


def _autofill(label: str) -> str | None:
    compact = _compact(label).strip(":：*()")
    # Whole-label recognition prevents an instruction mentioning a name from
    # becoming an applicant-identity source.
    return _AUTOFILL.get(compact)


def _field(box: Any, page: int, label: str, kind: str, confidence: float, **extra: Any) -> dict[str, Any]:
    rect = pymupdf.Rect(box)
    size = min(11.0, max(7.0, rect.height * .5))
    return {
        "type": "image" if kind == "signature" else "check" if kind in {"check", "radio"} else "text",
        "field_type": kind,
        "page": page,
        "box": [round(value, 2) for value in rect],
        "x": round(rect.x0 + min(3.0, rect.width * .05), 2),
        "y": round(min(rect.y1 - 2, rect.y0 + (rect.height + size) / 2), 2),
        "size": size,
        "align": "left",
        "font_family": "sans",
        "label": label.strip()[:200] or "입력칸",
        "anchor": label.strip()[:200],
        "required": False,
        "autofill_source": _autofill(label),
        "confidence": confidence,
        "needs_review": True,
        **extra,
    }


def _merged(values: list[float]) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or value - result[-1] > _TOLERANCE:
            result.append(value)
    return result


def _covered(segments: list[tuple[float, float, float]], fixed: float, start: float, end: float) -> bool:
    intervals = sorted((max(a, start), min(b, end)) for pos, a, b in segments
                       if abs(pos - fixed) <= _TOLERANCE and b >= start and a <= end)
    cursor = start
    for a, b in intervals:
        if a - cursor > _TOLERANCE:
            return False
        cursor = max(cursor, b)
    return cursor >= end - _TOLERANCE


def _geometry(page: Any) -> tuple[list[Any], list[Any]]:
    horizontal: list[tuple[float, float, float]] = []
    vertical: list[tuple[float, float, float]] = []
    squares: list[Any] = []

    def line(a: Any, b: Any) -> None:
        if abs(a.y - b.y) <= .5:
            horizontal.append(((a.y + b.y) / 2, min(a.x, b.x), max(a.x, b.x)))
        elif abs(a.x - b.x) <= .5:
            vertical.append(((a.x + b.x) / 2, min(a.y, b.y), max(a.y, b.y)))

    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l":
                line(item[1], item[2])
            elif item[0] == "re":
                rect = pymupdf.Rect(item[1])
                line(rect.tl, rect.tr)
                line(rect.tr, rect.br)
                line(rect.bl, rect.br)
                line(rect.tl, rect.bl)
                if 5 <= rect.width <= 18 and 5 <= rect.height <= 18 and .7 <= rect.width / rect.height <= 1.4:
                    squares.append(rect)

    cells: list[Any] = []
    ys = _merged([v[0] for v in horizontal])
    # Small checkbox geometry need not split a larger table's row bands.
    ys = [y for y in ys if any(abs(pos - y) <= _TOLERANCE and end - start >= 25
                              for pos, start, end in horizontal)]
    for top, bottom in zip(ys, ys[1:]):
        if bottom - top < 9:
            continue
        xs = _merged([pos for pos, start, end in vertical if start <= top + _TOLERANCE and end >= bottom - _TOLERANCE])
        for left, right in zip(xs, xs[1:]):
            if right - left < 15:
                continue
            if all(_covered(horizontal, y, left, right) for y in (top, bottom)):
                cells.append(pymupdf.Rect(left, top, right, bottom))
    return cells, squares


def _cell_text(words: list[Any], rect: Any) -> str:
    return " ".join(str(word[4]) for word in words
                    if rect.x0 - .5 <= (word[0] + word[2]) / 2 <= rect.x1 + .5
                    and rect.y0 - .5 <= (word[1] + word[3]) / 2 <= rect.y1 + .5)


def _vector_fields(page: Any, page_no: int) -> list[dict[str, Any]]:
    words = page.get_text("words", sort=True)
    cells, squares = _geometry(page)
    labels = [(cell, _cell_text(words, cell)) for cell in cells]
    found: list[dict[str, Any]] = []
    for cell, text in labels:
        # A labeled cell immediately to the left is evidence for a blank value
        # cell. An unlabeled blank rectangle alone is not an input field.
        if not text.strip():
            previous = [(left, label) for left, label in labels if label.strip()
                        and abs(left.x1 - cell.x0) <= _TOLERANCE
                        and abs(left.y0 - cell.y0) <= _TOLERANCE
                        and abs(left.y1 - cell.y1) <= _TOLERANCE]
            if len(previous) == 1:
                label = previous[0][1]
                found.append(_field(cell + (2, 2, -2, -2), page_no, label, _kind(label), .72))
        elif _kind(text) in {"signature", "date"} and not any(
                abs(right.x0 - cell.x1) <= _TOLERANCE and abs(right.y0 - cell.y0) <= _TOLERANCE
                for right, _ in labels):
            # Inline printed signing/date hints are intentionally lower confidence.
            found.append(_field(cell + (2, 2, -2, -2), page_no, text, _kind(text), .52))

    check_boxes = list(squares)
    for word in words:
        if any(char in str(word[4]) for char in ("□", "☐", "▢")):
            width = min(word[3] - word[1], word[2] - word[0])
            check_boxes.append(pymupdf.Rect(word[0], word[1], word[0] + width, word[3]))
    unique_boxes: list[Any] = []
    for rect in sorted(check_boxes, key=lambda box: (box.y0, box.x0)):
        if any((rect & previous).get_area() >= .8 * min(rect.get_area(), previous.get_area()) for previous in unique_boxes):
            continue
        unique_boxes.append(rect)
        nearby = [word for word in words if word[0] >= rect.x1 - 1 and word[0] - rect.x1 <= 100
                  and abs((word[1] + word[3] - rect.y0 - rect.y1) / 2) <= max(8, rect.height)]
        label = " ".join(word[4] for word in nearby[:6]) or "선택"
        # The same visual row shares a choice group, without guessing exclusivity.
        row = next((field["group"] for field in found if field["field_type"] == "check"
                    and abs(field["box"][1] - rect.y0) <= 5), f"p{page_no}_choices_{len(found)}")
        found.append(_field(rect, page_no, label, "check", .65, group=row))
    return found[:_MAX_FIELDS_PER_PAGE]


def draft_layout(pdf: bytes, *, form_no: str = "form_1", title: str = "서식", template: str = "") -> dict[str, Any]:
    """Draft from explicit widgets first, otherwise observed vector cells/text.

    Invalid or encrypted sources raise a value-free validation error. Empty and
    image-only pages return ``manual_required`` with no invented input fields.
    No candidate is automatically confirmed, regardless of confidence.
    """
    try:
        document = pymupdf.open(stream=pdf, filetype="pdf")
    except Exception as error:
        raise ValueError("서식 PDF를 읽을 수 없습니다.") from error
    with document:
        if document.needs_pass:
            raise ValueError("암호가 설정된 PDF는 사용할 수 없습니다.")
        widgets = [(page.number, widget) for page in document for widget in (page.widgets() or [])]
        fields: list[dict[str, Any]] = []
        source_kind = "acroform" if widgets else "vector"
        if widgets:
            for page_no, widget in widgets:
                if widget.field_type in {pymupdf.PDF_WIDGET_TYPE_BUTTON, pymupdf.PDF_WIDGET_TYPE_UNKNOWN}:
                    continue
                kind = "check" if widget.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX else "radio" if widget.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON else "signature" if widget.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE else _kind(widget.field_label or widget.field_name or "")
                fields.append(_field(widget.rect, page_no, widget.field_label or widget.field_name or "입력칸", kind, .95,
                                     required=bool(widget.field_flags & pymupdf.PDF_FIELD_IS_REQUIRED),
                                     group=widget.field_name if kind == "radio" else None))
        else:
            for page in document:
                fields.extend(_vector_fields(page, page.number))
        return {
            "form_no": form_no,
            "title": title,
            "template": template,
            "public_form": None,
            "internal_form": None,
            "page_sizes": [{"width": page.rect.width, "height": page.rect.height} for page in document],
            "fields": {f"f{index:04d}": field for index, field in enumerate(fields)},
            "source_kind": source_kind if fields else "none",
            "status": "draft" if fields else "manual_required",
            "confirmed": False,
            "message": "입력칸 초안을 확인해 주세요." if fields else "자동 초안 없음 — 직접 입력칸을 추가해 주세요.",
        }
