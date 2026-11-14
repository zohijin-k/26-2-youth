# Design — applicant design system

The owner's prompt (`research/design-prompt.md`) is the specification. This file records the decisions that adapt it to this repository.

## Reference implementation

`zohijin-k/26-2-savings-applicant`, branch `main`, under `demo/frontend/src`. Read it from the local clone's git objects without touching its working tree (another session is working there):

```
git -C /Users/zohijin/Desktop/26-2-savings-applicant show origin/main:demo/frontend/src/styles/tokens.css
```

Useful paths there: `styles/{tokens,base,components}.css`, `app-shell.css`, `components/{Icon,Notice,Spinner,ProgressBar,ConfirmDialog,Modal,PhoneLink,StatusBadge}.tsx`, `hooks/{useBeforeUnload,useDocumentTitle,useElapsed}.ts`, `lib/{error-copy,file-precheck,format,identity-validation,upload-estimate}.ts`, `pages/applicant/{ApplyFlow,IdentityCheck,DocumentUpload,MyPage}.tsx` with their CSS, `pages/applicant/{upload-queue,reupload-guidance}.ts`, `assets/fonts/PretendardGOV/`.

Port, do not copy blindly: this repository's applicant flow differs (job package only, subsidy items and a separate final-check screen, a program finder and program information in front, applicant code loaded as its own lazy chunk). Keep this repository's API calls, state and URL handling; take the reference's look, components, copy patterns and waiting-screen logic.

## Brand colours from `logo.png`

Pixel sampling (432×112, fully opaque):

| Ink | Sampled colour | Share of the image | Role |
| --- | --- | --- | --- |
| Background | `#fefefe` | about 60% | logo sits on white |
| Large lettering | `#241c14` (near-black brown) | about 7% | text ink, not a brand hue |
| Small lettering and symbol | `#143c74` (navy; darker half of the blue pixels has median `#173975`) | about 5% | **primary** |
| Symbol | `#bc2c2c` red, `#e4bc44` yellow, `#8cb444` green | about 1% each | decoration only |

Decision: the primary is the navy, the most used dark colour that has a hue. The near-black lettering is treated as text ink (the neutral scale already covers it); a black primary would give no usable tints or focus colour. Navy `#143c74` on white is about 11:1.

The implementer re-samples to confirm, builds the nine-step scale from the navy hue (50 must reach 4.5:1 on white, 60 is the primary, 70 and 80 darker), sets `--brand-accent-*` from the symbol colours, and reports the contrast table. Red, yellow and green appear only in the 4px accent band and other information-free decoration.

## Logo and shell

- Copy `logo.png` to `demo/frontend/src/assets/brand/jbyouthhub-logo.png` (the root file stays where the owner put it and is not committed by this task unless the owner asks). Add it to `THIRD_PARTY_NOTICES.md` the way the reference lists its banner: provided by the project owner, usage terms to be confirmed with the organisation.
- Header: 4px accent band, logo at 48px height (40px on phones) as the home button, `alt="전북지역거점 청년지원센터 전북청년허브센터"`. The logo has its own white background; if sampling shows a non-white strip at an edge, wrap it in the chip described in the prompt, otherwise place it as is.
- Right side of the header: application number and "마이페이지" only while the application flow is mounted (as today, through the header portal).
- Footer: inside the flow `「전북청년 취업지원패키지」 신청 · 전북청년허브센터`; on the finder and information screens `전북청년허브센터`. No phone line.
- Head band `h1`: finder "사업 찾기"; information — the program title; flow — "전북청년 취업지원패키지 신청" followed by the step indicator. `document.title` follows `{단계명} | {사업명} 신청`; finder and information use `사업 찾기 | 전북청년허브센터` and `{사업명} | 전북청년허브센터`.

## Keeping the officer side identical

- `styles/tokens.css` is new and additive. The variables the officer CSS reads from `index.css` keep their names and values.
- `styles/base.css` and `styles/components.css` rules apply under `.app-shell--applicant` (or are imported only by the applicant entry), so that element rules, `.btn`, `.field`, `.card`, the global focus rule and the font do not reach officer screens. The officer side keeps `officer.css`.
- Shared components used by the frozen review detail (`Modal`, `FilePreview`, `PdfPages`, `Skeleton`, `StatusBadge`) keep their officer rendering: restyle them only through selectors under `.app-shell--applicant`, or add applicant-only components (`Notice`, `Icon`, `Spinner`, `ProgressBar`, `ConfirmDialog`) in files the officer chunk does not import.
- `@font-face` for Pretendard GOV may be global; the font is applied only inside the applicant shell.
- Proof: capture the officer program list, new-program form, a program workspace, the application list and a review detail in mock mode before and after, and compare pixels.

## Constraints from the tests

- Scenario P4 scans source under `demo/` for the English words for saving a file from a browser and for the forced-save disposition. They are allowed only in `forms/PdfFormsWorkspace.tsx`, `forms/pdf-forms-workspace.css` and `pages/applicant/DocumentUpload.tsx`. New files ported from the reference (`upload-queue.ts`, `file-precheck.ts`, …) must not contain them.
- Those three files stay at their paths.
- Lint 0 warnings; no chunk-size notice (the shared chunk is at about 452 kB of 500 kB — new applicant code and CSS must stay in the applicant chunk; fonts and the logo are assets).
- `node src/forms/phone.test.ts` keeps passing; new pure logic (upload queue, file pre-check, time estimate, error copy, formatters) gets unit tests in the same style.

## Order of work

Part A — foundation and entry screens
1. Baseline captures of every applicant screen (1440×900, 390×844) and the five officer screens; count the colours, font sizes and button heights in use.
2. Logo, fonts, `tokens.css`, `base.css`, `components.css`, the component set, the applicant shell (skip link, header, head band, footer).
3. Program finder, program information, the flow frame (head band, step indicator, bottom button row, save status), identity check with the start notice, validation summary and confirm dialog.

Part B — the rest of the flow
4. Form writing chrome (not the form coordinates), subsidy items, document upload with the waiting-screen rules, final check and submit with the confirm dialog, the receipt, my page.
5. Copy pass (section 8), accessibility pass (section 9), captures of every state, report.

Each part ends with the application still working end to end.
