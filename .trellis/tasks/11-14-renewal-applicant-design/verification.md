# 신청자 디자인 적용 검증 기록

코드 적용과 자동 검증을 마쳤습니다. 브라우저 시각·상호작용 검증이 남아 있으므로 Trellis 작업은 `in_progress`로 유지합니다. 2026. 11. 15. 소유자가 두 커밋과 기존 준비 파일 포함을 승인했습니다. 구현은 `258e88c1dbdc54bff635c90e1ede6d33a7aafe50` 커밋으로 저장했습니다. 푸시·배포는 하지 않았습니다.

## 반영한 화면

사업 찾기, 사업 안내, 본인인증, 서식 작업 영역, 지원 항목 선택, 서류 업로드, 확인 및 제출, 접수증, 마이페이지에 같은 토큰과 컴포넌트를 적용했습니다. 신청자 진입점에서만 스타일을 불러오며 담당자 화면 파일과 공유 담당자 대화상자·미리보기는 수정하지 않았습니다.

본인인증 오류 요약·입력칸 이동, 확정/삭제/최종 제출 확인창, 단계 제목 포커스와 문서 제목, 이탈 안내, 저장 상태, 모바일 표 레이블, SVG 상태 표시를 추가했습니다. 업로드는 즉시 로컬 미리보기 → 순차 대기열 → 실제 전송률 → 서버 확인(경과 시간·관측 기반 예상) → 응답 즉시 표시·뒤에서 목록 갱신 순서입니다. 칸별 오류, 같은 파일 재시도와 대기 취소를 제공합니다. 서버 API 경로·multipart 필드·응답과 기존 신청 통과 조건은 유지합니다.

## 교체한 로고

소유자가 교체한 루트 `logo.png`를 화면용 `demo/frontend/src/assets/brand/jbyouthhub-logo.png`에 그대로 복사했습니다. 두 파일의 SHA-256은 `9f65a44519e6f3320e791d57a24902ccbc4f0fa656d05a5c23eae6b16be24c57`로 같습니다.

844×226 RGBA, 알파 255이며 네 가장자리가 모두 흰색입니다. 이전 이미지의 베이지 줄과 칩 테두리를 제거했습니다. 비율을 유지한 48px/40px 표시를 사용합니다. 픽셀 표본은 남색 `#173975` 6,406개, 빨강 `#b82d2b` 1,823개, 노랑 `#e6b943` 1,501개, 초록 `#8db243` 1,065개입니다. 선택한 네 잉크의 비율 약 59:17:14:10을 강조 띠에 적용했습니다. 남색은 기존 척도를 유지하고 노랑·초록 장식 토큰을 새 표본으로 갱신했습니다.

## 자동 검증 결과

| 검증 | 결과 |
| --- | --- |
| `npm --prefix demo/frontend run build -- --manifest` | TypeScript·Vite 통과, 청크 크기 경고 없음 |
| `npm --prefix demo/frontend run lint` | 경고·오류 0 |
| `node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts` (frontend 폴더) | 32건 통과 |
| `.venv/bin/python -m pytest demo/backend/tests -q -ra` | 1,317건 통과, 기존 의존성 경고 9건 |
| `.venv/bin/python -m pytest engine_v2/tests -q -ra` | 1,267건 통과, 기존 의존성 경고 7건 |
| 기존 `run*scenarios.py` 모듈 | 18개 모두 종료 코드 0, P4 소스 경로 검사 포함 |
| `research/verify_design.py` | 대비 38조합, 색/글자 크기/모서리 토큰·600/900px 분기점 검사 통과 |
| 담당자 CSS 산출물 비교 | 동일한 374개 선택자·미디어별 선언 이력, 변경 0 |
| `git diff --check` | 통과 |

업로드 전송 시험은 multipart 요청 필드, 실제 진행 이벤트, 전송 완료 뒤 응답을 지연시킨 동안 미완료 유지, 응답값 일치, 오류 및 취소를 확인합니다. 실제 브라우저의 느린 응답 화면을 검증한 것은 아닙니다.

담당자 CSS 비교 기준은 HEAD `92e477486421c97fd0ca2da50879ff3bf3775520`의 별도 임시 빌드입니다. 신청자 전용 선택자를 제외한 담당자 로드 CSS 선언 이력이 같습니다. 담당자 TSX와 기존 공유 컴포넌트도 변경되지 않았습니다. 이는 픽셀 비교 결과가 아닙니다.

## 대비 계산

WCAG 상대 휘도 계산식으로 검사한 UI 토큰 조합입니다. 주 색/흰색 11.179:1, 포커스/흰색 6.517:1입니다. 38조합의 최솟값은 주의 글자/주의 진한 배경 4.553:1입니다. 로고 그림과 원본 PDF 자체의 모든 픽셀을 검사한 수치는 아닙니다.

| 글자/표식 토큰 | 배경 토큰 | 대비 |
| --- | --- | ---: |
| `--gray-90` | `--gray-0` | 16.176:1 |
| `--gray-90` | `--gray-5` | 14.819:1 |
| `--gray-90` | `--color-bg` | 15.175:1 |
| `--gray-90` | `--brand-5` | 14.802:1 |
| `--gray-70` | `--gray-0` | 8.681:1 |
| `--gray-70` | `--gray-5` | 7.953:1 |
| `--gray-70` | `--color-bg` | 8.144:1 |
| `--gray-70` | `--brand-5` | 7.944:1 |
| `--gray-60` | `--gray-0` | 6.301:1 |
| `--gray-60` | `--gray-5` | 5.772:1 |
| `--gray-60` | `--color-bg` | 5.911:1 |
| `--gray-60` | `--brand-5` | 5.766:1 |
| `--brand-60` | `--gray-0` | 11.179:1 |
| `--brand-60` | `--gray-5` | 10.241:1 |
| `--brand-60` | `--color-bg` | 10.487:1 |
| `--brand-60` | `--brand-5` | 10.230:1 |
| `--brand-50` | `--gray-0` | 6.517:1 |
| `--brand-50` | `--gray-5` | 5.970:1 |
| `--brand-50` | `--color-bg` | 6.113:1 |
| `--brand-50` | `--brand-5` | 5.963:1 |
| `--danger-60` | `--gray-0` | 5.947:1 |
| `--danger-60` | `--danger-5` | 5.306:1 |
| `--danger-60` | `--danger-10` | 4.729:1 |
| `--warning-60` | `--gray-0` | 5.815:1 |
| `--warning-60` | `--warning-5` | 5.287:1 |
| `--warning-60` | `--warning-10` | 4.553:1 |
| `--success-60` | `--gray-0` | 5.850:1 |
| `--success-60` | `--success-5` | 5.263:1 |
| `--success-60` | `--success-10` | 4.789:1 |
| `--info-60` | `--gray-0` | 5.639:1 |
| `--info-60` | `--info-5` | 5.040:1 |
| `--info-60` | `--info-10` | 4.584:1 |
| `--gray-0` | `--brand-60` | 11.179:1 |
| `--gray-0` | `--brand-70` | 14.251:1 |
| `--gray-0` | `--brand-80` | 16.702:1 |
| `--gray-60` | `--gray-10` | 5.129:1 |
| `--success-60` | `--brand-tint-a` | 5.428:1 |
| `--success-60` | `--brand-tint-b` | 5.422:1 |

전체 값과 검사 파일은 [design-audit.json](research/design-audit.json), 재실행 스크립트는 [verify_design.py](research/verify_design.py)에 있습니다.

## 기존 스타일과 의도한 변경

시작 시점 스타일 선언 조사에서는 색 리터럴 84종과 글자 크기 선언 20종(변수 참조 포함)이 있었습니다. 공용 셸의 담당자 규칙도 포함한 정적 조사로, 실제 계산 스타일의 개수는 아닙니다. 높이 선언은 레이아웃 요소도 포함하므로 버튼 개수로 보고하지 않습니다. 이후 신청자 화면 CSS는 색 리터럴 없이 토큰을 사용하고 일반 버튼은 40/48/56px로 맞췄습니다. 원자료는 [baseline-style-inventory.json](research/baseline-style-inventory.json)에 있습니다.

- 원본 PDF의 좌표·마스크·입력 크기·축척·서체는 유지합니다. 원본 셀의 2px 모서리와 좌표에 비례하는 글자 크기는 문서 예외이며 UI에 확장하지 않습니다. 문서 잉크·배경은 같은 값의 `--pdf-*` 토큰으로 옮겼습니다.
- 이전의 조용한 비활성 진행 버튼을 눌러 남은 항목을 확인하는 방식으로 바꿨습니다. 서버의 제출·자격 조건은 바꾸지 않았습니다.
- 다른 저장소의 기본 예상 시간은 가져오지 않았습니다. 측정값이 없는 첫 파일에는 예상 시간을 표시하지 않습니다.
- 신청자 전용 전역 CSS는 lazy 진입점에서만 불러옵니다. 담당자 CSS나 기존 전역 `--brand` 값은 바꾸지 않았습니다.
- 접수증의 다음 절차는 서버 제출 응답만 보관해 같은 탭의 새로고침에서도 복원합니다. 저장소 사용이 차단된 브라우저에서는 서버가 제공하는 현재 접수 사실을 표시합니다.
- 새 로고의 흰 가장자리를 확인해 이전 칩 테두리를 제거했습니다. 장식 색상은 글자·버튼·상태에 사용하지 않습니다.

## 확인하지 못한 항목

CUA 브라우저 호스트가 연결되지 않았으며, 대체로 시도한 네이티브 Chrome 제어도 컴퓨터 사용 권한이 없어 실패했습니다. 따라서 다음은 미검증 상태입니다.

- 1440×900·390×844 전후 캡처 및 320px/400% 확대에서의 가로 넘침·겹침.
- 빈 양식·오류·진행 중·완료·실패의 실제 렌더링, 느린 응답 화면과 인쇄 결과.
- 키보드만으로 전 과정, 대화상자 실제 포커스 가두기·복귀, 스크린리더·다른 브라우저.
- 실제 백엔드에서 처음부터 제출까지의 브라우저 진행 및 원본 PDF 입력 정렬.
- 담당자 5개 화면 픽셀 비교. 정적 선언 이력 일치만 확인했습니다.

## 이번 세션에서 변경한 파일

- `.trellis/spec/frontend/applicant-design-system.md`
- `.trellis/spec/frontend/index.md`
- `.trellis/spec/frontend/pdf-form-workspace.md`
- `.trellis/spec/frontend/state-management.md`
- `.trellis/tasks/11-14-renewal-applicant-design/design.md`
- `.trellis/tasks/11-14-renewal-applicant-design/implement.md`
- `.trellis/tasks/11-14-renewal-applicant-design/prd.md`
- `.trellis/tasks/11-14-renewal-applicant-design/research/baseline-style-inventory.json`
- `.trellis/tasks/11-14-renewal-applicant-design/research/design-audit.json`
- `.trellis/tasks/11-14-renewal-applicant-design/research/officer-css-comparison.json`
- `.trellis/tasks/11-14-renewal-applicant-design/research/verify_design.py`
- `demo/frontend/src/App.tsx`
- `demo/frontend/src/api.ts`
- `demo/frontend/src/app-shell.css`
- `demo/frontend/src/assets/brand/jbyouthhub-logo.png`
- `demo/frontend/src/components/ApplicantFileLink.tsx`
- `demo/frontend/src/components/ApplicantFilePreview.tsx`
- `demo/frontend/src/components/ApplicantModal.tsx`
- `demo/frontend/src/components/ApplicantStatusBadge.tsx`
- `demo/frontend/src/components/Dialog.tsx`
- `demo/frontend/src/components/SignaturePad.tsx`
- `demo/frontend/src/forms/FormSheet.tsx`
- `demo/frontend/src/forms/PdfFormsWorkspace.tsx`
- `demo/frontend/src/forms/pdf-forms-workspace.css`
- `demo/frontend/src/lib/file-precheck.ts`
- `demo/frontend/src/lib/receipt-steps.ts`
- `demo/frontend/src/lib/upload-estimate.ts`
- `demo/frontend/src/pages/applicant/ApplicantApp.tsx`
- `demo/frontend/src/pages/applicant/ApplyFlow.tsx`
- `demo/frontend/src/pages/applicant/DocumentUpload.tsx`
- `demo/frontend/src/pages/applicant/FinalCheck.tsx`
- `demo/frontend/src/pages/applicant/IdentityCheck.tsx`
- `demo/frontend/src/pages/applicant/MyPage.tsx`
- `demo/frontend/src/pages/applicant/ProgramFinder.tsx`
- `demo/frontend/src/pages/applicant/ProgramInfo.tsx`
- `demo/frontend/src/pages/applicant/SubsidyItems.tsx`
- `demo/frontend/src/pages/applicant/applicant-shell.css`
- `demo/frontend/src/pages/applicant/apply-flow.css`
- `demo/frontend/src/pages/applicant/document-upload.css`
- `demo/frontend/src/pages/applicant/final-check.css`
- `demo/frontend/src/pages/applicant/identity-check.css`
- `demo/frontend/src/pages/applicant/my-page.css`
- `demo/frontend/src/pages/applicant/program-finder.css`
- `demo/frontend/src/pages/applicant/program-info.css`
- `demo/frontend/src/pages/applicant/subsidy-items.css`
- `demo/frontend/src/pages/applicant/upload-queue.ts`
- `demo/frontend/src/styles/base.css`
- `demo/frontend/src/styles/components.css`
- `demo/frontend/src/styles/tokens.css`
- `demo/frontend/tests/file-precheck.test.ts`
- `demo/frontend/tests/receipt-steps.test.ts`
- `demo/frontend/tests/upload-estimate.test.ts`
- `demo/frontend/tests/upload-queue.test.ts`
- `demo/frontend/tests/upload-transport.test.ts`

## 시작 전부터 존재하던 준비 파일

아래 파일은 이번 세션 시작 전부터 수정되거나 추적되지 않은 상태였습니다. 소유자가 이번 후속 요청에서 포함을 승인하여 기능 커밋에 함께 저장했습니다.

- `THIRD_PARTY_NOTICES.md`
- `demo/frontend/src/assets/fonts/PretendardGOV/LICENSE.txt`
- `demo/frontend/src/assets/fonts/PretendardGOV/PretendardGOV-Bold.subset.woff2`
- `demo/frontend/src/assets/fonts/PretendardGOV/PretendardGOV-Medium.subset.woff2`
- `demo/frontend/src/assets/fonts/PretendardGOV/PretendardGOV-Regular.subset.woff2`
- `demo/frontend/src/components/ConfirmDialog.tsx`
- `demo/frontend/src/components/Icon.tsx`
- `demo/frontend/src/components/Notice.tsx`
- `demo/frontend/src/components/ProgressBar.tsx`
- `demo/frontend/src/components/Spinner.tsx`
- `demo/frontend/src/hooks/useBeforeUnload.ts`
- `demo/frontend/src/hooks/useDocumentTitle.ts`
- `demo/frontend/src/lib/error-copy.ts`
- `demo/frontend/src/lib/error-copy.test.ts`
- `demo/frontend/src/lib/format.ts`
- `demo/frontend/src/lib/format.test.ts`
- `demo/frontend/src/lib/identity-validation.ts`
- `demo/frontend/src/lib/identity-validation.test.ts`

별도로 루트 `logo.png`(소유자 제공 원본)와 기존 `task.json` 변경은 기본 커밋 대상에서 제외합니다.

## 2026. 11. 15. 후속 검토

소유자는 현재 신청자 디자인 작업 마무리만 요청했습니다. CUA 브라우저 호스트 연결과 네이티브 Chrome 제어를 다시 시도했으나 각각 호스트 연결 불가와 컴퓨터 사용 권한 미부여로 실패했습니다. 시각 검증 항목은 여전히 미완료입니다.

다음 문제를 수정했습니다.

- 계산 가능한 전송 이벤트 이전에는 퍼센트를 표시하지 않습니다. 실제로 측정된 0%와 길이 미확정을 구분하고, 재시도 때 측정 상태를 초기화합니다. 해당 순수 로직 회귀 시험을 추가했습니다.
- 올바른 날짜를 입력한 뒤에도 날짜 입력의 도움말 연결 대상이 존재하도록 유지합니다.
- 지원 항목 초기 목록 조회 실패에 재시도 버튼을 추가하고, 여러 저장 요청 중 일부만 끝난 상태를 저장 완료로 표시하지 않습니다.
- 서명 PNG는 실제 이미지 판독 후 같은 PNG 형식으로 준비합니다. 잘못된 이미지·오래된 파일 읽기 결과를 안내/무시하며, 캔버스 크기가 바뀌었을 때 저장된 서명을 복원합니다.
- 배정되지 않은 서류의 삭제 실패도 보이는 안내로 표시합니다.

이후 빌드·린트와 프런트엔드 32건이 통과했습니다. P4 시나리오 재실행은 189개 확인 항목 통과·실패 0입니다. 대비 38조합과 담당자 CSS 374개 선언 이력 비교도 다시 통과했습니다. 변경이 없는 백엔드·엔진 전체 시험과 나머지 시나리오는 직전 기록의 성공 결과를 유지합니다.
