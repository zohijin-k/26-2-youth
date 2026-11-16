# Public notice drafts

Extract public PDF text and supplemental public copy into unconfirmed candidates.
Every candidate carries a page, short verbatim quotation, confidence and
needs_review=true. Missing text, contradictory titles/periods or ambiguous basis
dates require manual entry; never choose a convenient first match silently.

Bindings name existing rule functions. They are configuration candidates, not
decisions. Use automatic bindings only for exact supported operators and values.
Exclusive age limits, upper-bounded work duration, residence duration, city scope,
document-specific issue cutoffs, disjunctions and mixed unsupported conditions
must retain a checklist candidate. Do not erase a residual requirement while
extracting a supported age or province fragment.

Select a basis date for its condition, rather than inheriting an unrelated issue
date. Preserve secondary basis citations and every income-table source row.
Income can bind only when the complete observed household table matches the
existing supported table; missing, contradictory or arbitrary tables remain
manual. Supplemental evidence has no fabricated PDF page.

Use synthetic PDFs generated inside tests. Image-only notices return a direct
entry state when no safe local OCR integration is available. Form analysis
delegates to the existing detector; it does not change coordinate templates or
document readers. A provider proposal may never supply a new verdict rule.

Authoring version 2 stores its evidence in posting metadata. Publication validates
all four sections, every human confirmation, valid dates and confirmed form
hashes. Incomplete unconfirmed criterion values may be saved, but cannot publish
or establish a rule binding. Confirmed invalid values fail validation. Old managed
drafts can opt in with manual evidence; existing published snapshots stay frozen.

Freeze applicant document requirements separately from officer criteria. Never
project citations, confidence, checklist configuration or rule paths into
applicant responses. Only existing certain failure kinds can block submission.
An unrecognized document gets an additive manual slot, skips OCR and always
requires review, including merged-document assignment. It cannot become PASS.

The old file-replacement endpoint must not erase version 2 evidence. Old metadata
PATCH endpoints cannot bypass the confirmed analysis: publication checks for any
mismatch between posting fields and the reviewed draft.
Published or closed version 2 postings reject legacy metadata PATCH entirely.
The runtime binding wrapper requires explicit finite numeric confidence and image
quality within zero and one, before and after existing engine conversion. Missing
values, booleans, NaN and infinity cannot establish trusted evidence.

The optional notice provider uses LLM_PROVIDER=jbai and JBAI_TEXT_MODEL; its
default is none. Project only notice page text and bounded public supplemental
copy at both service and transport boundaries. Use the existing no-redirect HTTP
transport (30s first call inside a 40s total budget, default `json_object` format
with one fallback) and real source quotations. Keep criterion proposals separate
from rule candidates; accept only proposals whose stated values agree with a
supported candidate and its source evidence (see "Scenario: notice provider
stability" below).

The provider may write the applicant guidance from the notice's overview
(모집 개요/사업 개요) section. That text replaces the local guidance value with
`ai_drafted: true`, `needs_review: true` and its verbatim overview citation. Reject
it (keeping the local guidance) unless the citation is verbatim, every number it
states occurs in the public source, and it makes no selection promise
('자동 선정', '누구나', '전원 지원' …) that the source does not make itself.
`ai_drafted` is a display-only boolean, accepted on guidance only.

Without a provider, guidance is built from the overview section when one exists:
its heading's marker family ('1.', '1)', 'Ⅰ', '가.', '□', none) bounds the
section, PDF-wrapped lines rejoin into one paragraph per bullet, and method and
contact lines are appended when the overview lacks them. Overview headings and
list-item lines are never title candidates.
Invalid JSON, timeouts, mismatches and transport errors return the local draft.
Never log provider exceptions or give a provider applicant records or OCR values.
Record a provider call only as a fixed outcome word, mode, attempt and seconds.

## Scenario: notice provider stability

### 1. Scope / Trigger

Apply when changing `notice_llm.py`, the transport or logging helpers in
`llm_drafts.py`, `tools/probe_jbai_notice.py`, or the `JBAI_*` / `LLM_PROVIDER`
environment wiring. The provider is an external service whose answers are slow,
occasionally malformed and never authoritative.

### 2. Signatures

- `enrich_notice(draft, supplemental='', *, provider=None) -> dict` — unchanged shape; adds only `guidance` (when `ai_drafted`) and `suggestions`.
- `DraftProvider.generate(purpose, payload) -> str | None` — unchanged protocol; fakes in tests implement it.
- `JbaiNoticeProvider(base_url, environ, transport, name='jbai', fallback=True, clock=time.monotonic)` — `clock` exists for fake-clock tests.
- `values_match(candidate, values) -> bool` — the single value comparison, shared by `enrich_notice` and the probe.
- `stated_values(kind, values, quote) -> dict | None` — the provider's directly stated values in display form, only when the cited sentence prints every one of them; shared by `enrich_notice` and the probe.
- `reference_for(proposal, values, draft, source) -> dict | None` — a display-only reference on an officer-check candidate of the cited sentence.
- `guidance_check(guide, payload) -> (text | None, state)`; `guidance_text` returns only the text.
- `llm_drafts.failure_outcome(error) -> str`, `llm_drafts.log_call(purpose, mode, attempt, outcome, seconds)`.
- `python -m demo.backend.tools.probe_jbai_notice [--mode M] [--repeats N] [--max-calls N<=15] [--long] [--json]`.

### 3. Contracts

Environment (all optional, read per call):

| Key | Default | Bounds | Meaning |
|---|---|---|---|
| `JBAI_RESPONSE_FORMAT` | `json_object` | `json_schema` / `json_object` / `prompt` | first format; one fallback to the next |
| `JBAI_LLM_BUDGET_SEC` | 40 | 5–120, else default | total provider seconds for one analysis |
| `JBAI_LLM_MAX_INPUT_CHARS` | 30000 | 1000–200000, else default | leading notice characters sent, in page order |

Call record (logger `demo.backend.llm`, `ok` at INFO, everything else WARNING):

```
llm_call purpose=notice_analysis mode=json_object attempt=1 outcome=timeout seconds=30.0
llm_result purpose=notice_analysis guidance=accepted criteria_received=4 criteria_accepted=3 criteria_reference=1
```

`criteria_accepted` counts suggestions attached to automatic candidates;
`criteria_reference` counts references. The two never overlap.

`outcome` is one of `ok`, `timeout`, `http_429`, `http_4xx`, `http_5xx`, `network`,
`bad_transport`, `no_content`, `truncated`, `too_large`, `bad_shape`,
`budget_exhausted`. `guidance` is one of `accepted`, `none`, `shape`, `quote`,
`length`, `number`, `promise`. A line holds these words, static names and
numbers only.

Time: first call timeout is `min(30, budget)`. A second call runs only when at
least 8 seconds of budget remain and gets `min(30, remaining)`. At most two
calls per analysis.

Reading an answer (`_parse`): strip a leading `<think>…</think>` block and one
enclosing code fence; parse JSON; if that fails parse from the first `{` to the
last `}`. The object must contain both `guidance` and a `criteria` list. Extra
keys are ignored. A malformed guidance or criterion drops only itself;
`values_json` may be a string or an object; only the first 50 criteria are read.

Stated-value matching (`values_match`), after the unchanged preconditions (same
type, candidate has `engine_rule`, same page, overlapping verbatim quotation):

| Type | One complete group must be present |
|---|---|
| age | `min_age`+`max_age`, or `birth_start`+`birth_end` |
| residence | `province` |
| issue_date | `date` |
| income | `percent` |
| work_continuity | `months` |

Every key the provider wrote must exist in the candidate with an equal value
after normalization (numeric strings and `140` vs `140.0`, dotted or Korean
dates to ISO, the extractor's province aliases). An accepted suggestion carries
the candidate's own values, never the provider's.

Reference suggestion (`reference_for`), tried only when no automatic candidate
accepted the proposal:

```python
{'target_id': '<officer-check candidate id>', 'type': 'age', 'reference': True,
 'read': '18~39세', 'read_values': {'min_age': 18, 'max_age': 39},
 'page': 1, 'quote': '<verbatim proposal quote>', 'source': 'jbai',
 'confidence': 0.0, 'needs_review': True}
```

- The target is a candidate without `engine_rule` on the same page whose
  quotation overlaps the proposal's. Preference: `candidate_type` equal to the
  proposal type, then `checklist`, then any other.
- `read_values` holds only keys of the type's stated groups (plus `operator`
  for income). Every kept key must be printed in the proposal's quotation:
  numbers as standalone numbers (`18` is not found in `2018` or `180`; months
  also as `N년` × 12), dates in ISO after reading `YYYY.M.D`, `YYYY년 M월 D일`
  or a quoted two-digit year (`'26. 3. 3.` → 2026), the province by its name or
  an extractor alias, `operator` as `이하` / `미만`. One complete group is
  required. Other keys the provider wrote (`basis_date` …) are neither checked
  nor kept.
- `read` is built by the server from `read_values`; provider prose is never shown.
- A reference has no `values` key and never changes the target candidate, its
  `needs_review`, or `analysis_blockers`. Like every suggestion it exists only
  in the analysis response and is not persisted by `validate_analysis`.
- Frontend: `suggestionPresentation` in `officer-modern-model.ts` shows the chip
  `AI 참고 · 담당자가 직접 확인` and the line `AI가 읽은 조건: <type label> · <read>`.
  There is no control that copies a reference into a criterion.

### 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| Transport raises `TimeoutError` / `HTTPError` / `URLError` / `ValueError` | named outcome, single fallback if budget allows, else local draft |
| Answer is not readable or lacks either top-level key (`{}`, fenced `{}`, `[]`) | `bad_shape` (or `truncated` when `finish_reason` is `length`), fallback |
| Answer readable but nothing passes validation | `ok`, no fallback, local draft unchanged |
| Provider value conflicts with the candidate, or uses a key the candidate lacks | proposal discarded |
| Provider gives only derived values (`basis_date`) or an incomplete group | proposal discarded |
| Cited sentence has an automatic candidate of the proposal's type | no reference; the value comparison above decides |
| Cited sentence has only officer-check candidates and prints every stated value | reference on one of them, candidate unchanged |
| Cited sentence has no extractor candidate | no reference (the provider never creates a criterion) |
| A stated value is not printed in the cited sentence | no reference |
| The target candidate's own non-empty value for a read key differs | no reference |
| Guidance cites a non-verbatim line / states a number absent from the source / promises selection | guidance discarded with state `quote` / `number` / `promise` |
| `LLM_PROVIDER` not `jbai`, missing key or model, non-https base URL | `NoneProvider`, zero calls, no log line |

### 5. Good / Base / Bad Cases

- Good: the provider answers `{"min_age": 18, "max_age": 39}` for the cited age sentence; the suggestion attaches to the extractor's age candidate and shows the candidate's full values.
- Good: on a real notice the extractor leaves `② 연령: … 만 18~39세 청년` for the officer; the provider's `{"min_age": 18, "max_age": 39}` becomes a reference reading `18~39세` on that item, which stays an officer check.
- Base: the provider is off or fails twice; the officer sees the unchanged rule draft within the budget.
- Bad: accepting a proposal on its quotation alone, or copying provider values into a suggestion — a misread value would then look confirmed.
- Bad: showing a reference value the sentence does not print (a birth range computed from an age), or binding `engine_rule` because a reference exists.

### 6. Tests Required

- `tests/test_notice_llm_stability.py`: outcome per exception type; log lines contain no key, host, model, body or exception text; worst case bounded by the budget with a fake clock; second call skipped below 8s; wrapped answers read; `{}` and missing keys unusable; stated-value match and mismatch tables; every automatic candidate of probe notices A/B/C reachable from stated values; input window size.
- `tests/test_notice_llm.py`, `tests/test_notice_llm_formats.py`: boundary projection, exactly one fallback, first timeout 30s, conflicting value / unknown key / unrelated citation rejected in every mode.
- `tests/test_notice_llm_references.py`: `stated_values` pass and discard tables per type; `criteria`, `guidance` and blockers equal with and without references; target preference; no reference beside an automatic candidate, on a sentence without a candidate, or against the extractor's own value; duplicates removed; the `llm_result` line; a tampered reference is a probe screen violation.
- `tests/test_probe_jbai_notice.py`: the probe prints only status, mode, counts and seconds; `screen_violation` stays 0 for accepted items.
- `demo/frontend/tests/officer-modern.test.ts`: `suggestionPresentation` for a reference and for an ordinary suggestion.
- Real calls use synthetic public notices only, through the probe, with the 15-call hard limit.

### 7. Wrong vs Correct

Wrong: require the provider's values to equal the candidate's whole `values`
object. The provider cannot compute `basis_date` or a birth range from one
sentence, so every proposal is discarded (measured 2026-11-16: 0–0.5 accepted
per notice).

Correct: ask for the values printed in the cited sentence, require that group to
be complete, and reject any stated value that differs from the candidate.

Wrong: `log.warning('provider failed: %s', error)` — the exception text can hold
the URL, key or response body.

Correct: `log_call(purpose, mode, attempt, failure_outcome(error), seconds)`.

Wrong: turn an officer-check candidate into an automatic one, or fill its
values, because the provider read the sentence. The provider would then supply
a verdict rule.

Correct: keep the candidate as it is and append a reference whose every value
the officer can find in the quoted sentence; the officer still sets and
confirms the criterion.
