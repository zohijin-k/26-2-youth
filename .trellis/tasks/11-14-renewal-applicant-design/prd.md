# 리뉴얼: 신청자 화면 디자인 시스템 적용

Parent: `11-14-program-service-renewal`.

## Approval

On 2026-11-14 the owner pasted the design prompt "청년정책 신청 화면 디자인 프롬프트" (kept verbatim in `research/design-prompt.md`) and placed `logo.png` (전북청년허브센터) at the repository root. The prompt is the requirement; this file adds what is specific to this repository.

## Goal

Every applicant screen follows the owner's public-service design: one token file with brand colours taken from the logo, one component set, one shell, the flow patterns, the waiting-screen rules, the copy rules and the accessibility checks. The aim stated in the prompt is a screen that produces no complaints: it explains what to do, what is happening, and how to fix a mistake.

## Filled values

| Item | Value |
| --- | --- |
| 사업명 | 사업마다 다르다. 지금 신청할 수 있는 사업은 「전북청년 취업지원패키지」. 사업 찾기·사업 안내는 여러 사업을 다룬다. |
| 운영기관 | 전북청년허브센터 (로고와 사업 규칙의 신청 방법 문구가 근거) |
| 로고 파일 | 저장소 루트 `logo.png` (432×112, 불투명, 가로형). `demo/frontend/src/assets/brand/`로 복사해 쓴다. 정사각 심볼은 없다. |
| 문의 전화 | 없음 (`rules/programs.py`의 취업지원패키지 `call_center`가 비어 있다). 문의 줄은 생략한다. |
| 신청 단계 | 본인인증 → 서식 작성 → 서류 업로드 → 확인 및 제출 (`ApplyFlow.tsx`의 `APPLY_STEPS`; 지원 항목 선택은 서식 작성 뒤에 이어지는 화면) |
| 대상 화면 | `demo/frontend/src`의 신청자 쪽 전부: 신청자 셸(`App.tsx`의 신청자 머리·바닥), `pages/applicant/**`, `forms/**`의 화면 틀, 신청자 쪽에서 쓰는 공용 컴포넌트 |
| 건드리면 안 되는 것 | 백엔드와 API 형태, URL 체계, 저장 순서, 통과 조건, 원본 서식 좌표와 그 렌더링, 담당자 화면(특히 `ReviewDetail.tsx`, `DocumentViewer.tsx`), 시나리오 P4가 읽는 경로(`forms/PdfFormsWorkspace.tsx`, `forms/pdf-forms-workspace.css`, `pages/applicant/DocumentUpload.tsx`) |

## Requirements

### R1 — The prompt, section by section

Sections 1–10 of `research/design-prompt.md` apply to every applicant screen: program finder, program information, identity check, form writing (the chrome around the PDF forms), subsidy items, document upload, final check and submit, the receipt after submission, and my page.

### R2 — Officer screens do not change

The officer side must render exactly as before (pixel comparison on the program list, new-program form, program workspace, application list and review detail in mock mode). Tokens are added, not replaced; anything shared with the officer side is changed only under the applicant scope.

### R3 — Function is unchanged

No change to API requests or responses, URLs, save order or pass conditions. No new npm dependency and no external request for fonts or icons. Fixed, approved texts (legal notices, per-reason guidance) keep their wording.

### R4 — Honest content

No invented phone number, address, operating hours, processing time or policy text. Where the server does not provide a value, the line is omitted.

### R5 — Reporting

The report required by section 11.5: files changed, the contrast table, what was not checked, and what was deliberately changed from the previous rules.

## Acceptance Criteria

- [ ] `styles/tokens.css` holds every colour, size, radius and spacing; applicant CSS has no colour literal outside it (checked by a script, with the list of exceptions if any).
- [ ] Brand scale derived from `logo.png` by pixel sampling; contrast table reported; primary ≥ 7:1 on white, focus ≥ 4.5:1.
- [ ] Applicant screens captured at 1440×900 and 390×844 before and after; every state named in section 11.4 captured after (empty form, error, in progress, done, failed); no horizontal scroll at 390px.
- [ ] Officer screens: 0 differing pixels before/after on the five screens in R2.
- [ ] `npm run lint` 0 warnings, `npm run build` without a chunk-size notice, existing unit test and new unit tests for new pure logic pass; backend suite and 18 scenarios unchanged.
- [ ] A full applicant walk-through in a browser against the real backend: find → information → identity → forms → subsidy items → upload (including a slowed response) → final check → submit → receipt → my page.
