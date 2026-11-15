# Form draft detection

> Rules for `demo/backend/forms/draft.py`: how uploaded form PDFs become
> review-required input-field drafts, and how an officer click is snapped.

## Boundaries (never change)

- Recognition is geometry, judgement is rules. Only PyMuPDF words, characters,
  lines and rectangles are used. No OCR, external service or LLM.
- Every drafted field has `needs_review: True`; layouts have `confirmed: False`.
  Confidence is informational only and never confirms a field.
- AcroForm widgets win: when any widget exists, only widgets are used and no
  vector rule runs.
- Empty and image-only PDFs return `status: manual_required` with no fields.
- A blank rectangle without a label never becomes a field.
- Drafting runs only on upload (`posting_workspace`) and on the officer's
  "자동 초안 다시 만들기" (`posting_draft`). Saved or confirmed `layout_json` is
  never rewritten in bulk.

## No overfitting

`draft.py` must not contain fixture file names, `form_no` values, reference
coordinates, numbers of four or more digits, or sentences specific to one form.
Vocabulary is limited to general administrative words:

| Purpose | Words |
|---|---|
| Choice pairs | 예/아니오(아니요), 동의함/동의하지 않음, 있음/없음, 해당/해당 없음 |
| Labels (rule c) | keys of `_AUTOFILL` (성명, 이름, 생년월일, 연락처, 휴대폰, 전화번호, 주소, 이메일, English equivalents) |
| Signature marks | (서명), (인), (서명 또는 인) — spacing ignored |

Each rule is covered by synthetic PDFs generated inside
`demo/backend/tests/test_form_draft_inline.py` (positive and negative cases).
Fixtures are used only by the measurement tool, never by rules or tests of rules.

## Rows

Words are grouped into visual rows by vertical centre (`_rows`), not by PDF
block/line numbers, because printed forms often split one visual line into
several blocks. Cell borders are vertical rules crossing the row band (`_edge`).

## Rules

| Rule | Trigger | Field | Confidence |
|---|---|---|---|
| table value cell (existing) | blank cell whose left neighbour cell has a label | cell − 2pt, kind from label | 0.72 |
| checkbox (existing) | drawn square 5–18pt or □/☐/▢ glyph | box, row-grouped | 0.65 |
| a. choice words | adjacent whole-word choice pair, same cell, separated only by comma/space, no printed box within 3× row height | each word's glyph box (comma excluded), one group | 0.6 |
| b. inline date | `[digits]년`, `월`, `일` consecutive on one row | blank before 년 (after a 1–3 digit century, or as wide as the month blank), between 년–월 and 월–일 when wider than the row height and not crossing a cell border; labels 연/월/일, `field_type: date` | 0.6 |
| c. label blank | vocabulary label followed by a colon, or by an underline that starts after the label and is not a cell border | from label end to next word / signature mark / cell border / mirrored text margin | 0.55 |
| d. signature mark | mark words on a row | mark box when rule c ends at it; `label : ____ (mark)` → text blank + mark; otherwise blank (≤ 8× height) + mark as one image field | 0.55 |
| cell hint (existing, narrowed) | cell text implies date/signature | whole cell | 0.52 |

## False-positive guards (rule e)

1. A cell hint is dropped when the cell is taller than two text lines
   (2 × 1.8 × median word height), holds more than two rows or more than five
   words, or exceeds 15% of the page area. A cell hint that contains an inline
   blank is also dropped; inline rules are more specific.
2. A box is a bullet, not a checkbox, when it starts its row (no word between
   it and the left cell border), at least four words follow, the row holds no
   choice word and no other box, and no other box is stacked in the same column
   within 2.5 row heights.
3. A label blank that ends where a labeled blank value cell begins yields to
   that cell.

## Ordering and duplicates

Candidates are collected (cells, checkboxes, choice words, inline rules), then
`_deduplicated` keeps, among fields overlapping at IoU ≥ 0.5 on the same page,
the more confident one, preserving the original order. The per-page limit
(`_MAX_FIELDS_PER_PAGE`) is applied after deduplication.

## Officer snap (`snap_field`)

`POST /api/officer/postings/{posting_id}/workspace/forms/{form_id}/snap` with
`{page, x, y}` returns `{box, field_type, label}` or `{box: null}`:

1. a drafted candidate containing the point (smallest),
2. the smallest blank table cell containing the point (≤ 15% of page),
   labelled by its left neighbour,
3. the blank between words on the clicked row, bounded by cell borders.

Officer session required (401 without), posting/form mismatch → 404, bad page
→ 422. The label is capped at 200 characters; page text is never returned in
bulk. The editor adds the field with `needs_review: true`; a null answer adds
the default 120×20 box (`demo/frontend/src/lib/form-snap.ts`).

## Measurement

`python -m demo.backend.tools.measure_form_drafts [--json]` compares drafts with
hand-authored coordinates of the public blank templates: recall (IoU ≥ 0.5,
one-to-one), precision, false fields, oversized (> 15% of page), and
missed/extra lists. Report numbers honestly; do not tune rules to fixture
coordinates.
