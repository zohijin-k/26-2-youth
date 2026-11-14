# Stage 5 local form drafting

Implemented `demo/backend/forms/draft.py` with `draft_layout(pdf, form_no=..., title=..., template=...)`. Widget-bearing PDFs use AcroForm exclusively. Other PDFs use observed table edges/label-adjacent blank cells plus printed check marks, small vector squares and signing/date hints. Renderer `type` remains text/check/image; additive `field_type` is text/number/date/check/radio/signature. `autofill_source` recognizes whole-label name/birth/mobile/address/email. Every field has needs_review=true and confirmed=false regardless of confidence. Empty and image-only documents yield manual_required. No OCR/model/network call, no filename inference, no fixture writes.

Targeted tests: **10 passed** with generated PDFs: text/number/signature/date/checks, same-line groups, autofill, mandatory review, AcroForm priority/required flag, blank/image-only/manual, unlabeled rectangle, multi-page coordinates/opaque IDs, invalid/encrypted PDFs, one-to-one/page-scoped geometric metrics and type mismatches.

## Measurement

Command: `.venv/bin/python -m demo.backend.tools.measure_form_drafts`

| 서식 | 수작업 칸 | 자동 초안 칸 | IoU ≥ 0.5 일치 | 일치율 | 종류 일치율¹ |
|---|---:|---:|---:|---:|---:|
| job_application.pdf | 40 | 30 | 29 | 72.5% | 100.0% |
| job_consent.pdf | 8 | 8 | 4 | 50.0% | 100.0% |
| job_interview_confirmation.pdf | 5 | 12 | 5 | 100.0% | 100.0% |
| 서식1.pdf | 69 | 59 | 56 | 81.2% | 100.0% |
| 서식2.pdf | 16 | 0 | 0 | 0.0% | 0.0% |
| 서식3.pdf | 7 | 5 | 4 | 57.1% | 100.0% |
| 서식4.pdf | 5 | 4 | 2 | 40.0% | 100.0% |
| 서식5.pdf | 8 | 3 | 2 | 25.0% | 100.0% |

¹ 기하적으로 일치한 칸 중 기존 렌더링 종류(text/check/image) 일치 비율. 일치 칸이 없으면 0%. 모든 자동 칸은 담당자 확인이 필요합니다.

## Limits

These are initial geometric suggestions, not finalized form extraction or real-document OCR accuracy. All types and positions require officer review. Check groups share a row but do not infer exclusive radio semantics; the editor must set that explicitly. Long/multiline labels and merged rows can be missed. A box may be suggested over a printed signing/date hint; the officer must reposition it. The self-check form with no blank label-adjacent cells correctly requires manual addition. Type accuracy above compares existing text/check/image rendering kinds only, because the original coordinate schema does not record semantic number/date types.

No existing fixtures or source files were modified; new code/tests/tool only. Root owns API integration and staged full regression gate.
