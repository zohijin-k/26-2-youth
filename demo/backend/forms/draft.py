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


# Inline vocabulary is limited to general administrative form words. No
# template name, form number, coordinate or form-specific sentence belongs here.
_CHOICE_PAIRS = {frozenset(pair) for pair in (("예", "아니오"), ("예", "아니요"), ("동의함", "동의하지않음"),
                                              ("있음", "없음"), ("해당", "해당없음"))}
_CHOICE_WORDS = {word for pair in _CHOICE_PAIRS for word in pair}
_SIGN_MARKS = {"(서명)", "(인)", "(서명또는인)"}
_LABEL_WORDS = set(_AUTOFILL)
_BOX_CHARS = ("□", "☐", "▢")
_SEPARATORS = ",，、/·"
_COLONS = (":", "：")
_PAGE_SHARE_LIMIT = .15
_INLINE_CONFIDENCE = .6
_LABEL_CONFIDENCE = .55


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


def _geometry(page: Any) -> tuple[list[Any], list[Any], list[tuple[float, float, float]], list[tuple[float, float, float]]]:
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
    return cells, squares, horizontal, vertical


def _cell_text(words: list[Any], rect: Any) -> str:
    return " ".join(str(word[4]) for word in words
                    if rect.x0 - .5 <= (word[0] + word[2]) / 2 <= rect.x1 + .5
                    and rect.y0 - .5 <= (word[1] + word[3]) / 2 <= rect.y1 + .5)


def _rows(words: list[Any]) -> list[list[Any]]:
    """Group words into visual rows by vertical centre, independent of PDF blocks."""
    rows: list[list[Any]] = []
    centers: list[float] = []
    for word in sorted(words, key=lambda item: ((item[1] + item[3]) / 2, item[0])):
        center, height = (word[1] + word[3]) / 2, word[3] - word[1]
        for index in range(len(rows) - 1, max(-1, len(rows) - 4), -1):
            row_height = min(item[3] - item[1] for item in rows[index])
            if abs(centers[index] - center) <= .35 * min(height, row_height):
                rows[index].append(word)
                break
        else:
            rows.append([word])
            centers.append(center)
    return [sorted(row, key=lambda item: item[0]) for row in rows]


def _union(words: list[Any]) -> Any:
    return pymupdf.Rect(min(w[0] for w in words), min(w[1] for w in words),
                        max(w[2] for w in words), max(w[3] for w in words))


def _edge(vertical: list[tuple[float, float, float]], x: float, band: Any, right: bool) -> float | None:
    """Nearest vertical rule crossing the row band on one side of ``x``."""
    middle = (band.y0 + band.y1) / 2
    crossing = [pos for pos, start, end in vertical
                if start <= middle <= end and end - start >= band.height * .8
                and (pos > x + .5 if right else pos < x - .5)]
    if not crossing:
        return None
    return min(crossing) if right else max(crossing)


def _choice_tokens(row: list[Any]) -> list[tuple[str, list[Any]]]:
    tokens: list[tuple[str, list[Any]]] = []
    index = 0
    while index < len(row):
        text = str(row[index][4]).strip(_SEPARATORS)
        if not text:
            index += 1
            continue
        if index + 1 < len(row) and not str(row[index][4]).endswith(tuple(_SEPARATORS)):
            joined = _compact(text + str(row[index + 1][4]).strip(_SEPARATORS))
            if joined in _CHOICE_WORDS:
                tokens.append((joined, [row[index], row[index + 1]]))
                index += 2
                continue
        tokens.append((_compact(text), [row[index]]))
        index += 1
    return tokens


def _choice_pairs(row: list[Any], vertical: list[tuple[float, float, float]]
                  ) -> list[tuple[tuple[str, list[Any]], tuple[str, list[Any]]]]:
    """Adjacent whole-word choice pairs in one cell; '예시' or '예정' never equals '예'."""
    tokens = _choice_tokens(row)
    pairs = []
    index = 0
    while index + 1 < len(tokens):
        first, second = tokens[index], tokens[index + 1]
        span = _union(first[1] + second[1])
        edge = _edge(vertical, first[1][-1][2], span, right=True)
        if (first[0] != second[0] and frozenset((first[0], second[0])) in _CHOICE_PAIRS
                and second[1][0][0] - first[1][-1][2] <= 3 * span.height
                and (edge is None or edge >= second[1][0][0])):
            pairs.append((first, second))
            index += 2
            continue
        index += 1
    return pairs


def _ink(words: list[Any], chars: list[tuple[Any, str]]) -> Any:
    """Word box narrowed to its glyphs, excluding separators such as a comma."""
    rect = _union(words)
    inside = [box for box, char in chars if char not in _SEPARATORS and not char.isspace()
              and rect.x0 - .5 <= (box.x0 + box.x1) / 2 <= rect.x1 + .5
              and rect.y0 - .5 <= (box.y0 + box.y1) / 2 <= rect.y1 + .5]
    if not inside:
        return rect
    return pymupdf.Rect(min(box.x0 for box in inside), rect.y0, max(box.x1 for box in inside), rect.y1)


def _page_chars(page: Any) -> list[tuple[Any, str]]:
    return [(pymupdf.Rect(char["bbox"]), char["c"]) for block in page.get_text("rawdict")["blocks"]
            for line in block.get("lines", []) for span in line["spans"] for char in span["chars"]]


def _date_blanks(row: list[Any], vertical: list[tuple[float, float, float]]) -> list[tuple[Any, str]]:
    """Blanks in a printed '20  년  월  일' row: before 년 and between the tokens."""
    found: list[tuple[Any, str]] = []
    for index, year in enumerate(row[:-2]):
        month, day = row[index + 1], row[index + 2]
        if not re.fullmatch(r"\d{0,4}년", str(year[4])) or month[4] != "월" or day[4] != "일":
            continue
        band = _union([year, month, day])
        minimum = max(6.0, band.height)
        gaps = [(year[2], month[0], "월"), (month[2], day[0], "일")]
        if year[4] == "년":
            previous = row[index - 1] if index else None
            if previous is not None and re.fullmatch(r"\d{1,3}", str(previous[4])):
                gaps.insert(0, (previous[2], year[0], "연"))
            else:
                # No printed century: assume the year blank is as wide as the month blank.
                left = year[0] - (month[0] - year[2])
                boundary = _edge(vertical, year[0], band, right=False)
                if previous is not None:
                    left = max(left, previous[2])
                if boundary is not None:
                    left = max(left, boundary)
                gaps.insert(0, (left, year[0], "연"))
        for start, end, label in gaps:
            edge = _edge(vertical, start, band, right=True)
            if end - start >= minimum and (edge is None or edge >= end - .5):
                found.append((pymupdf.Rect(start + 2, band.y0 - 2, end - 1, band.y1 + 2), label))
    return found


def _marks(row: list[Any]) -> list[tuple[int, int]]:
    found = []
    index = 0
    while index < len(row):
        for size in range(1, 6):
            if index + size <= len(row) and _compact("".join(str(w[4]) for w in row[index:index + size])) in _SIGN_MARKS:
                found.append((index, index + size))
                index += size
                break
        else:
            index += 1
    return found


def _label_at(row: list[Any], index: int) -> tuple[int, bool] | None:
    """Vocabulary label starting at ``index``: (index after label/colon, has colon)."""
    for size in (3, 2, 1):
        if index + size > len(row):
            continue
        raw = "".join(str(w[4]) for w in row[index:index + size])
        stop, colon = index + size, raw.endswith(_COLONS)
        if not colon and stop < len(row) and row[stop][4] in _COLONS:
            stop, colon = stop + 1, True
        if _compact(raw).rstrip(":：") in _LABEL_WORDS:
            return stop, colon
    return None


def _underline(horizontal: list[tuple[float, float, float]], vertical: list[tuple[float, float, float]],
               label: Any, band: Any) -> tuple[float, float] | None:
    """A rule just below the row that starts after the label and is not a cell border."""
    for pos, start, end in horizontal:
        if (band.y1 - 1 <= pos <= band.y1 + .6 * band.height and label.x1 - 2 <= start <= label.x1 + 2 * band.height
                and end - start >= 2 * band.height
                and not any(abs(x - start) <= _TOLERANCE and a <= pos + .5 and b >= pos - .5 for x, a, b in vertical)):
            return start, end
    return None


def _inline_fields(rows: list[list[Any]], horizontal: list[tuple[float, float, float]],
                   vertical: list[tuple[float, float, float]], right_margin: float, page_no: int) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for row in rows:
        for rect, label in _date_blanks(row, vertical):
            found.append(_field(rect, page_no, label, "date", _INLINE_CONFIDENCE))
        marks = _marks(row)
        mark_starts = {start for start, _ in marks}
        claimed: set[int] = set()
        for index in range(len(row)):
            located = _label_at(row, index)
            if located is None:
                continue
            stop, colon = located
            label_words = row[index:stop]
            label_rect = _union(label_words)
            height = label_rect.height
            line = None if colon else _underline(horizontal, vertical, label_rect, label_rect)
            if not colon and line is None:
                continue
            start = label_rect.x1 + 3 if line is None else max(label_rect.x1 + 3, line[0])
            edge = _edge(vertical, label_rect.x1, label_rect, right=True)
            limits = [right_margin + 3 if edge is None else edge]
            if stop < len(row):
                limits.append(row[stop][0])
            end = min(limits) - 3
            if line is not None:
                end = min(end, line[1])
            if end - start < 1.5 * height:
                continue
            if stop < len(row) and stop in mark_starts and row[stop][0] - 3 <= end + 3:
                claimed.add(stop)
            text = " ".join(str(w[4]) for w in label_words)
            found.append(_field(pymupdf.Rect(start, label_rect.y0, end, label_rect.y1), page_no, text,
                                _kind(text), _LABEL_CONFIDENCE))
        for begin, stop in marks:
            mark = _union(row[begin:stop])
            height = mark.height
            mark_box = mark + (-2, -1.5, 2, 1.5)
            previous = row[begin - 1] if begin else None
            if begin in claimed:
                found.append(_field(mark_box, page_no, " ".join(str(w[4]) for w in row[begin:stop]), "signature",
                                    _LABEL_CONFIDENCE))
                continue
            edge = _edge(vertical, mark.x0, mark, right=False)
            if previous is not None and edge is not None and previous[2] < edge:
                previous = None
            sign_text = " ".join(str(w[4]) for w in row[begin:stop])
            if previous is not None and str(previous[4]).endswith(_COLONS) and mark.x0 - previous[2] >= 1.5 * height + 6:
                # "label : ____ (seal)" — the blank holds the written name; the mark holds the seal.
                label_words = row[max(0, begin - 2):begin] if previous[4] in _COLONS else [previous]
                text = " ".join(str(w[4]) for w in label_words)
                found.append(_field(pymupdf.Rect(previous[2] + 3, mark.y0, mark.x0 - 3, mark.y1), page_no, text,
                                    _kind(text), _LABEL_CONFIDENCE))
                found.append(_field(mark_box, page_no, sign_text, "signature", _LABEL_CONFIDENCE))
                continue
            left = mark.x0 - 8 * height
            if previous is not None:
                left = max(left, previous[2] + 3)
            if edge is not None:
                left = max(left, edge + 3)
            box = mark_box if mark.x0 - left < 2 * height else pymupdf.Rect(left, mark_box.y0, mark_box.x1, mark_box.y1)
            found.append(_field(box, page_no, sign_text, "signature", _LABEL_CONFIDENCE))
    return found


def _is_bullet(rect: Any, rows: list[list[Any]], boxes: list[Any], vertical: list[tuple[float, float, float]]) -> bool:
    """A leading box followed by a sentence, with no choice word or second box, is a bullet."""
    middle = (rect.y0 + rect.y1) / 2
    row = min(rows, key=lambda words: abs((_union(words).y0 + _union(words).y1) / 2 - middle), default=None)
    if row is None or abs((_union(row).y0 + _union(row).y1) / 2 - middle) > max(4.0, rect.height * .6):
        return False
    edge = _edge(vertical, rect.x0, rect, right=False)
    edge = -1.0 if edge is None else edge
    if any(w[2] <= rect.x0 + .5 and w[0] > edge for w in row):
        return False
    following = [w for w in row if w[0] >= rect.x1 - 1]
    own = [w for w in row if w[0] < rect.x1 - 1 and w[2] > rect.x0 + .5]
    count = len(following) + sum(1 for w in own if str(w[4]).strip("".join(_BOX_CHARS)))
    if count < 4:
        return False
    if any(token in _CHOICE_WORDS for token, _ in _choice_tokens(row)):
        return False
    others = [box for box in boxes if not box.intersects(rect)]
    if any(abs((box.y0 + box.y1) / 2 - middle) <= max(4.0, rect.height * .6) for box in others):
        return False
    # A box stacked directly above/below in the same column makes an option list.
    return not any(abs(box.x0 - rect.x0) <= 2 and abs((box.y0 + box.y1) / 2 - middle) <= 2.5 * _union(row).height
                   for box in others)


def _center(box: list[float]) -> Any:
    return pymupdf.Point((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _box_iou(first: list[float], second: list[float]) -> float:
    overlap = (pymupdf.Rect(first) & pymupdf.Rect(second)).get_area()
    union = pymupdf.Rect(first).get_area() + pymupdf.Rect(second).get_area() - overlap
    return overlap / union if union > 0 else 0.0


def _vector_fields(page: Any, page_no: int) -> list[dict[str, Any]]:
    words = page.get_text("words", sort=True)
    cells, squares, horizontal, vertical = _geometry(page)
    rows = _rows(words)
    heights = sorted(word[3] - word[1] for word in words)
    line_height = heights[len(heights) // 2] if heights else 12.0
    page_area = page.rect.get_area()
    # Without a cell border a blank runs to the text margin, mirrored from the left.
    right_margin = max([word[2] for word in words] + [page.rect.x1 - min((word[0] for word in words), default=0)])
    labels = [(cell, _cell_text(words, cell)) for cell in cells]
    found: list[dict[str, Any]] = []
    hint_fields: list[int] = []
    value_cells: list[Any] = []
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
                value_cells.append(cell)
                found.append(_field(cell + (2, 2, -2, -2), page_no, label, _kind(label), .72))
        elif _kind(text) in {"signature", "date"} and not any(
                abs(right.x0 - cell.x1) <= _TOLERANCE and abs(right.y0 - cell.y0) <= _TOLERANCE
                for right, _ in labels):
            # A whole cell is a signing/date area only when it is a short hint in
            # a short cell; paragraphs and large boxes are left to inline rules.
            text_rows = sum(1 for row in rows if cell.contains(pymupdf.Point(
                (row[0][0] + row[-1][2]) / 2, (_union(row).y0 + _union(row).y1) / 2)))
            if (cell.height > 2 * 1.8 * line_height or cell.get_area() > _PAGE_SHARE_LIMIT * page_area
                    or text_rows > 2 or len(text.split()) > 5):
                continue
            # Inline printed signing/date hints are intentionally lower confidence.
            hint_fields.append(len(found))
            found.append(_field(cell + (2, 2, -2, -2), page_no, text, _kind(text), .52))

    check_boxes = list(squares)
    for word in words:
        if any(char in str(word[4]) for char in _BOX_CHARS):
            width = min(word[3] - word[1], word[2] - word[0])
            check_boxes.append(pymupdf.Rect(word[0], word[1], word[0] + width, word[3]))
    unique_boxes: list[Any] = []
    for rect in sorted(check_boxes, key=lambda box: (box.y0, box.x0)):
        if any((rect & previous).get_area() >= .8 * min(rect.get_area(), previous.get_area()) for previous in unique_boxes):
            continue
        unique_boxes.append(rect)
        if _is_bullet(rect, rows, check_boxes, vertical):
            continue
        nearby = [word for word in words if word[0] >= rect.x1 - 1 and word[0] - rect.x1 <= 100
                  and abs((word[1] + word[3] - rect.y0 - rect.y1) / 2) <= max(8, rect.height)]
        label = " ".join(word[4] for word in nearby[:6]) or "선택"
        # The same visual row shares a choice group, without guessing exclusivity.
        row = next((field["group"] for field in found if field["field_type"] == "check"
                    and abs(field["box"][1] - rect.y0) <= 5), f"p{page_no}_choices_{len(found)}")
        found.append(_field(rect, page_no, label, "check", .65, group=row))

    chars: list[tuple[Any, str]] | None = None
    for row in rows:
        for first, second in _choice_pairs(row, vertical):
            words_in_pair = first[1] + second[1]
            span = _union(words_in_pair)
            reach = 3 * span.height
            if any(abs((box.y0 + box.y1) / 2 - (span.y0 + span.y1) / 2) <= max(4.0, span.height * .6)
                   and span.x0 - reach <= box.x1 and box.x0 <= span.x1 + reach for box in check_boxes):
                continue  # A printed box next to the word is the field.
            chars = _page_chars(page) if chars is None else chars
            group = f"p{page_no}_words_{len(found)}"
            for _, choice_words in (first, second):
                label = " ".join(str(w[4]).strip(_SEPARATORS) for w in choice_words)
                found.append(_field(_ink(choice_words, chars), page_no, label, "check", _INLINE_CONFIDENCE, group=group))

    inline = [field for field in _inline_fields(rows, horizontal, vertical, right_margin, page_no)
              if not _yields_to_value_cell(field, value_cells)]
    # A cell-wide date/sign hint yields to the more specific inline blanks inside it.
    dropped = {index for index in hint_fields
               if any(pymupdf.Rect(found[index]["box"]).contains(_center(field["box"])) for field in inline)}
    candidates = [field for index, field in enumerate(found) if index not in dropped] + inline
    return _deduplicated(candidates)[:_MAX_FIELDS_PER_PAGE]


def _yields_to_value_cell(field: dict[str, Any], value_cells: list[Any]) -> bool:
    """A label blank that ends at a labeled blank value cell is already that cell."""
    if field["confidence"] != _LABEL_CONFIDENCE or field["type"] != "text":
        return False
    box = field["box"]
    return any(0 <= cell.x0 - box[2] <= 8 and min(box[3], cell.y1) - max(box[1], cell.y0) >= .5 * (box[3] - box[1])
               for cell in value_cells)


def _deduplicated(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Of candidates overlapping at IoU >= 0.5 keep the more confident one, in original order."""
    order = sorted(range(len(candidates)), key=lambda index: -candidates[index]["confidence"])
    kept: list[int] = []
    for index in order:
        if all(candidates[index]["page"] != candidates[other]["page"]
               or _box_iou(candidates[index]["box"], candidates[other]["box"]) < .5 for other in kept):
            kept.append(index)
    return [candidates[index] for index in sorted(kept)]


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


def _suggestion(box: Any, kind: str, label: str) -> dict[str, Any]:
    rect = pymupdf.Rect(box)
    return {"box": [round(value, 2) for value in rect], "field_type": kind, "label": label.strip()[:200] or "입력칸"}


def snap_field(pdf: bytes, page_no: int, x: float, y: float) -> dict[str, Any] | None:
    """Suggest a box around one officer click, or ``None`` when nothing surrounds it.

    Order: a drafted candidate under the point, the smallest table cell holding the
    point when that cell is blank, then the blank between words on the clicked row.
    The officer still reviews every added field; nothing here is confirmed.
    """
    try:
        document = pymupdf.open(stream=pdf, filetype="pdf")
    except Exception as error:
        raise ValueError("서식 PDF를 읽을 수 없습니다.") from error
    with document:
        if document.needs_pass:
            raise ValueError("암호가 설정된 PDF는 사용할 수 없습니다.")
        if not 0 <= page_no < document.page_count:
            raise IndexError(page_no)
        page = document[page_no]
        point = pymupdf.Point(x, y)
        drafted = [field for field in _vector_fields(page, page_no) if pymupdf.Rect(field["box"]).contains(point)]
        if drafted:
            field = min(drafted, key=lambda item: pymupdf.Rect(item["box"]).get_area())
            return _suggestion(field["box"], field["field_type"], field["label"])
        words = page.get_text("words", sort=True)
        cells, _, _, vertical = _geometry(page)
        around = [cell for cell in cells if cell.contains(point)]
        if around:
            cell = min(around, key=lambda item: item.get_area())
            if cell.get_area() <= _PAGE_SHARE_LIMIT * page.rect.get_area() and not _cell_text(words, cell).strip():
                left = [_cell_text(words, other) for other in cells if abs(other.x1 - cell.x0) <= _TOLERANCE
                        and min(other.y1, cell.y1) - max(other.y0, cell.y0) >= .5 * cell.height]
                label = next((text for text in left if text.strip()), "입력칸")
                return _suggestion(cell + (2, 2, -2, -2), _kind(label), label)
        row = next((row for row in _rows(words) if _union(row).y0 - 2 <= y <= _union(row).y1 + 2), None)
        if row is None:
            return None
        band = _union(row)
        if any(word[0] < x < word[2] for word in row):
            return None  # The click is on printed text, not on a blank.
        before = [word for word in row if word[2] <= x]
        after = [word for word in row if word[0] >= x]
        lefts = [value for value in (before[-1][2] if before else None, _edge(vertical, x, band, right=False))
                 if value is not None]
        rights = [value for value in (after[0][0] if after else None, _edge(vertical, x, band, right=True))
                  if value is not None]
        if not lefts or not rights:
            return None
        left, right = max(lefts), min(rights)
        if right - left - 6 < 1.5 * band.height:
            return None
        label = " ".join(str(word[4]) for word in before[-2:]) if before and before[-1][2] == left else "입력칸"
        return _suggestion(pymupdf.Rect(left + 3, band.y0, right - 3, band.y1), _kind(label), label)
