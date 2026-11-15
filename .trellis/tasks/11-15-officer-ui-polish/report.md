# 담당자 UI 정리 작업 보고서

기준 브랜치: `main` (`b654752`). 작업 브랜치: `feat/officer-ui-polish`. 합성 자료와 격리 서버만 사용했다. 원래 있던 사용자 수정 2개는 커밋에서 제외했다.

## 1. 단계

| 단계 | 결과 | 커밋 | 새 시험 수 | 비고 |
| --- | --- | --- | ---: | --- |
| 0 | 통과 | — | 0 | main b654752; 보호 해시 일치; 이전 화면 8개; A/B/C/D 기준선 통과 |
| 1 | 통과 | f276db5 | 9 | A/B/C/D 통과; 프런트61개; lint/build 경고0 |
| 2 | 통과 | 0f8a1e8 | 5 | A/B/C/D 통과; 프런트66개; 키보드·근거 브라우저5그룹 |
| 3 | 실패·복원 | — | 0 | 디스크 공간 부족(ENOSPC)으로 실패; failed-stage3.patch 보관 후 복원 |
| 4 | 통과 | 266372d | 0 | A/B/C/D 통과; 프런트66개; 종단18건·작업 공간4그룹; 기존 픽셀 차이0 |
| 5 | 통과 | 이 보고서가 포함된 문서 커밋(HEAD) | 0 | 최종 A/B/C/D 통과; 문서·보고서·캡처·실패 패치 기록 |

## 2. 전체 시험: 기준선과 최종

| 시험 | 기준선 | 최종 |
| --- | --- | --- |
| engine | 통과 (1267개) | 통과 (1267개) |
| backend | 통과 (1645개) | 통과 (1645개) |
| C · run_p11_criteria_scenarios | 통과 (38개) | 통과 (38개) |
| C · run_p12_subsidy_criteria_scenarios | 통과 (29개) | 통과 (29개) |
| C · run_p13_household_scenarios | 통과 (26개) | 통과 (26개) |
| C · run_p14_pdf_forms_scenarios | 통과 (원본 서식 8개) | 통과 (원본 서식 8개) |
| C · run_p15_jbai_scenarios | 통과 (129개) | 통과 (129개) |
| C · run_p16_job_docs_scenarios | 통과 (96개) | 통과 (96개) |
| C · run_p17_own_scenarios | 통과 (75개) | 통과 (75개) |
| C · run_p18_applicant_precheck_scenarios | 통과 (180개) | 통과 (180개) |
| C · run_p19_nhis_history_scenarios | 통과 (24개) | 통과 (24개) |
| C · run_p20_nhis_continuation_scenarios | 통과 (7개) | 통과 (7개) |
| C · run_p2_scenarios | 통과 (53개) | 통과 (53개) |
| C · run_p3_scenarios | 통과 (186개) | 통과 (186개) |
| C · run_p4_scenarios | 통과 (189개) | 통과 (189개) |
| C · run_p5_scenarios | 통과 (152개) | 통과 (152개) |
| C · run_p6_scenarios | 통과 (261개) | 통과 (261개) |
| C · run_p7_scenarios | 통과 (253개) | 통과 (253개) |
| C · run_p8_localocr_scenarios | 통과 (89개) | 통과 (89개) |
| C · run_p9_identity_scenarios | 통과 (98개) | 통과 (98개) |
| D · 프런트 단위 | 통과 (52개) | 통과 (66개) |
| D · TypeScript (tsc -b) | 통과 | 통과 |
| D · oxlint (경고 0) | 통과 | 통과 |
| D · Vite build (청크 경고 없음) | 통과 | 통과 |

엔진·백엔드의 기존 의존성 경고는 기준선과 동일하며, 프런트 lint와 build는 경고 없이 통과해야 한다. 단계별 전체 시험 원본 결과는 `gate-*.json`에 있다.

## 3. 기존 프런트 시험 기대값 수정

없음. 동작·권한·게시·확인·선정 조건의 기존 기대값은 변경하지 않았다.

## 4. 보호 파일과 수정 범위

| 보호 파일 | 시작 | 최종 SHA-256 일치 |
| --- | --- | --- |
| `demo/frontend/src/pages/officer/ReviewDetail.tsx` | 일치 | 일치 |
| `demo/frontend/src/pages/officer/DocumentViewer.tsx` | 일치 | 일치 |
| `demo/frontend/src/pages/officer/officer.css` | 일치 | 일치 |
| `demo/frontend/src/components/StatusBadge.tsx` | 일치 | 일치 |
| `demo/frontend/src/components/Skeleton.tsx` | 일치 | 일치 |
| `demo/frontend/src/components/skeleton.css` | 일치 | 일치 |
| `demo/frontend/src/components/FilePreview.tsx` | 일치 | 일치 |
| `demo/frontend/src/components/file-preview.css` | 일치 | 일치 |
| `demo/frontend/src/hooks/useDelayedFlag.ts` | 일치 | 일치 |
| `demo/frontend/src/pages/officer/format.ts` | 일치 | 일치 |

백엔드·엔진 diff: 0. 보호 파일은 시작·각 커밋 직전·최종에 검사한다.

## 5. 기존 화면 픽셀 비교

- job-list: 차이 0픽셀 (1440×900), 임시 좌표 보정 없이 전체 화면 비교.
- job-review: 차이 0픽셀 (1440×900), 임시 좌표 보정 없이 전체 화면 비교.

## 6. 이전·이후 캡처와 화면 측정

1440×900 캡처. 버튼 수는 현재 시야에 보이는 버튼, 최소 글자는 공유 머리줄·원본 PDF 외 화면 본문을 측정했다.

| 화면 | 이전 → 이후 | 버튼 수 | 최소 글자 크기 | 바뀐 점 |
| --- | --- | --- | --- | --- |
| login | [이전](shots/before/login.png) · [이후](shots/after/login.png) | 2 → 2 | 13 → 13px | 3단계 실패로 원래 화면 복원 |
| upload | [이전](shots/before/upload.png) · [이후](shots/after/upload.png) | 5 → 5 | 12.5 → 12.5px | 3단계 실패로 원래 화면 복원 |
| program-list | [이전](shots/before/program-list.png) · [이후](shots/after/program-list.png) | 3 → 3 | 12 → 12px | 3단계 실패로 원래 화면 복원 |
| preview | [이전](shots/before/preview.png) · [이후](shots/after/preview.png) | 11 → 14 | 11 → 14px | 고정 진행 막대·항목별 확인·근거 접기·저장 후 게시 |
| workspace | [이전](shots/before/workspace.png) · [이후](shots/after/workspace.png) | 9 → 10 | 13 → 14px | 칩 탭·상태 필터·행 더보기 |
| generic-review | [이전](shots/before/generic-review.png) · [이후](shots/after/generic-review.png) | 10 → 13 | 11.6667 → 14px | 판정 카드·큰 확인란·아래 처리 영역 |
| job-list | [이전](shots/before/job-list.png) · [이후](shots/after/job-list.png) | 26 → 26 | 12 → 12px | 보호된 기존 화면 유지 |
| job-review | [이전](shots/before/job-review.png) · [이후](shots/after/job-review.png) | 17 → 17 | 11.5 → 11.5px | 보호된 기존 화면 유지 |

버튼 수에는 진행·필터 칩과 공유 머리줄 버튼도 포함한다. 3단계 복원으로 해당 화면의 최소 글자 크기 개선은 적용되지 않았다.

1280·1024px 가로 넘침 결과:

- login: 1280px 넘침 없음, 1024px 넘침 없음
- upload: 1280px 넘침 없음, 1024px 넘침 없음
- program-list: 1280px 넘침 없음, 1024px 넘침 없음
- preview: 1280px 넘침 없음, 1024px 넘침 없음
- workspace: 1280px 넘침 없음, 1024px 넘침 없음
- generic-review: 1280px 넘침 없음, 1024px 넘침 없음
- job-list: 1280px 넘침 없음, 1024px 넘침 있음
- job-review: 1280px 넘침 없음, 1024px 넘침 있음

기존 취업패키지 목록·상세의 1024px 넘침은 기준선에도 존재한다. 보호 범위와 픽셀 일치 요구에 따라 수정하지 않았다.

## 7. 덤 확인

- 작성 중 공고문 무쿠키 접근: **X** (응답 404).
- preview=false가 신청자 입력값을 그리지 않음: **O** (응답 200).

보안 관찰만 수행했으며 관련 백엔드는 수정하지 않았다.

## 8. 사람이 결정할 것

- 진행·필터 칩을 포함한 시야 버튼 수가 예시 편집 11→14, 작업 공간 9→10, 범용 상세 10→13으로 증가했다. 부가 동작은 메뉴에 접었지만 총 버튼 수 감소 목표는 충족하지 못했다. 추가 단순화 여부를 결정해야 한다.
- 기존 취업패키지의 1024px 가로 넘침을 추후 별도 작업으로 다룰지 결정할 수 있다.
- 3단계는 디스크 공간 부족으로 전체 게이트에 실패해 되돌렸다. 로그인·업로드·사업 목록 개선안은 [failed-stage3.patch](failed-stage3.patch)에 보관했다. 적용 재시도는 후속 작업으로 결정해야 한다. 중간 캡처 shots/intermediate는 되돌린 제안의 참고 자료다.

### 브라우저 검증

- 종단 흐름: 통과; 명시적 확인 18건.
- 메뉴·서랍·확인 대화상자 키보드/포커스: passed.
- 작업 공간 키보드/검색 선택 상태/처리 영역 검사: workspace-verification.json의 4개 그룹 통과.
- 원본 확인 전 심사 화면: [종단 캡처](shots/after-journey/officer-generic-review-detail.png).
- 목업 목록·상세가 로그인·API 요청 없이 동작하고, 목업 데이터는 별도 동적 청크로 유지된다.
- 대비 검사 9개 조합 모두 4.5:1 이상(contrast.json).
- 캡처·측정·시험에 실서류를 사용하지 않았다.

### 실행 메모

- Authorized unattended execution, task setup and five named commits by explicit request. No additional approval gate.
- Initial user changes excluded: task metadata for 11-14 applicant design; untracked logo.png.
- Branch starts at b654752. Protected hashes all match at start.
- Default Trellis dispatch uses implementation/check agents; task context manifests supplied.

- Baseline D measured from pristine main archive with root ignore rules, because new untracked stage1 sources were scanned by the initial lint run. Pristine baseline: 52 frontend tests, tsc/lint/build clean.
- Original historical browser runner completed generic final selection, then timed out on a fixed-width PDF zoom assumption. Separate before captures completed all eight surfaces without manipulating the viewer.
- Existing protected legacy list/detail overflow at 1024px before edits; preserve pixel parity rather than change shared legacy CSS.
- README and DEVELOPMENT startup examples already contain the requested environment-file option; final docs will clarify its requirement.

- Stage3 engine gate aborted because synthetic pytest artifacts exhausted disk (ENOSPC); backend log creation also failed. Stage3 exported to failed-stage3.patch and code restored per explicit failure policy. Only test directories created after this task started were cleaned, freeing about 10GB. No engine/backend/test files changed. Stage3 is not retried or committed.

- Final generic journey passed18 assertions, including observed PUT analysis → GET workspace → POST publish without separate Save. No browser page errors.
- Stage4 targeted browser checks passed: settings arrow→loaded heading, delayed search clears invisible selections, row-menu Escape focus return, review footer bottom872.74px at1440/1280/1024 widths with900px height.
- Final legacy captures compare at0 differing pixels for both full1440×900 images; no DOM or coordinate alignment adjustment.
- After program-list capture filters the isolated synthetic server list to the same built-in + baseline program IDs, excluding programs created by later QA.
- Read-only security probes: draft notice without cookies404 (X); preview=false unchanged raster after saving synthetic text (O).
- Nine modern text/background contrast pairs exceed4.5:1. Mock data remains a separate dynamic chunk, absent from applicant/officer static entry graphs.
- Strengthened new token test to compare base and media token declarations independently. Existing pre-task frontend assertions unchanged.
- Stage3 patch passes git apply --check against final tree. Its temp screenshots are retained in shots/intermediate as unapplied proposal references.

- Final full gate: engine1267, backend1645, all18scenario modules, frontend66, tsc/lint/build pass; frontend warnings0. Stage5 commit includes this report; its own hash is available from final HEAD (self-reference cannot be embedded in the same commit).
