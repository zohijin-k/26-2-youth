# Renewal master run report

## 1. 한 줄 요약

범용 사업 등록·서식 확정·신청·접수 목록 연결을 구현하고 합성 종단 흐름을 검증했습니다. 범용 심사 상세는 보호 규칙에 따라 연결하지 않았습니다.

## 2. 단계별 결과

| 단계 | 결과 | 커밋 해시 | 새 시험 수 | 비고 |
|---|---|---|---|---|
| 0 | 기록만 | — | — | origin/main(7472697)에서 브랜치 생성·기준선 측정 |
| 1 | 커밋됨 | 3d5a8d0 | 백엔드 9 | 예금주·실제 통장 사본 복구 |
| 2 | 커밋됨 | b767bfd | 프런트 7 | 화면 열기 3회 생성 0건·새로고침 이어하기 |
| 3 | 커밋됨 | 3cf8b9b | 프런트 3 | 신청자 작은 결함 4종 |
| 4 | 커밋됨 | 97dd6d2 | 백엔드 10 | 다중 PDF·제출 서류·작성 중 저장 |
| 5 | 커밋됨 | 36c70d9 | 백엔드 12 | 모든 자동 칸은 담당자 확인 필요 |
| 6 | 커밋됨 | eebb349 | 백엔드 11 + 프런트 2 | 편집·확정·게시·취소·마감 |
| 7 | 커밋됨 | f1a1582 | 백엔드 29 + 프런트 4 | 확정 사본 신청·목록 연결; 범용 심사 상세는 미연결 |
| 8 | 커밋됨 | 876b00d | 백엔드 19 | 기본 none; 실제 JBAI 호출 없음 |
| 9 | 커밋됨 | 03c40e1 | 백엔드 5 | 번들·범위 통합·문서·필수값/제출서류 경계 보강 |
| 10 | 커밋됨 | 보고서 커밋(HEAD) | 브라우저 검증 17항목 | 12개 종단 화면·기존 목록/상세 픽셀 차이 0 |

0단계는 지시대로 준비 기록만 남겼으며 별도 커밋을 만들지 않았습니다. 10단계 해시는 자기 참조를 피하기 위해 `보고서 커밋(HEAD)`로 표시합니다. 기존 시험의 코드·기대값은 변경하지 않았습니다. 실패 패치·선행 실패 건너뜀은 없습니다.

## 3. 전체 시험 결과

| 전체 시험 | 기준선 | 최종 |
|---|---|---|
| 엔진 A | 1,267 통과·실패 0 | 1,267 통과·실패 0 |
| 백엔드 B | 1,317 통과·실패 0 | 1,412 통과·실패 0 |
| 시나리오 C | 18개 모듈 통과·실패 0 | 18개 모듈 통과·실패 0 |
| 프런트 단위 시험 D | 32 통과·실패 0 | 48 통과·실패 0 |
| TypeScript | 통과 | 통과 |
| lint 경고 | 0 | 0 |
| build 청크 경고 | 없음 | 없음 |

| 시나리오 모듈 | 기준선 | 최종 |
|---|---|---|
| run_p11_criteria_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p12_subsidy_criteria_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p13_household_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p14_pdf_forms_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p15_jbai_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p16_job_docs_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p17_own_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p18_applicant_precheck_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p19_nhis_history_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p20_nhis_continuation_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p2_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p3_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p4_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p5_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p6_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p7_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p8_localocr_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |
| run_p9_identity_scenarios | 통과 / 실패 0 | 통과 / 실패 0 |

Python 의존성 경고는 기준선과 같은 엔진 7개·백엔드 9개이며 lint 경고와 구분합니다. 각 단계의 최종 게이트는 `gate-stage1.json`~`gate-stage10.json`, 기준선은 `baseline.json`에 보관했습니다. 전체 로그는 각 JSON의 `/tmp` 경로에 있습니다.

### 검증 중 수정·재실행 기록

- 1단계 첫 검증은 예금주 검사가 다른 사업에도 적용되어 시나리오 3개가 실패했습니다. 취업지원패키지에 한정했고, 다음 검증의 소스 금칙어 검사 실패도 새 코드의 명칭·문구를 고쳐 해결했습니다. 기존 시험은 고치지 않았습니다.
- 첫 결과 판독 오류로 만든 임시 커밋은 즉시 취소했습니다. 이후 커밋 도구는 A/B/C/D 종료 코드·최소 통과 수·lint/build 경고·보호 파일·키 패턴을 자동 확인합니다. 최종 이력에는 검증된 단계 커밋만 있습니다.
- 4·6단계의 프런트 lint 경고는 의존성/편집 상태 갱신 방식을 고친 뒤 D 전체를 재실행했습니다. 8단계의 누락된 편집 핸들러도 타입 검사 중 복구했습니다. 모두 경고·오류 0으로 검증한 뒤 커밋했습니다.
- 7단계 병렬 엔진 시험에서 기존 합성 이미지 CLI 하위 프로세스가 `-9`로 끝났습니다. 자원 압박 가능성은 추정입니다. 엔진·시험을 수정하지 않고 단독 실행하여 1,267개가 통과했습니다. 이후 게이트는 엔진을 먼저 실행합니다.
- 최종 검토에서 공백 필수값, 제출 후 서류 삭제, 같은 이름 원본 덮어쓰기·변경 순서 경계를 보강하고 새 시험을 추가했습니다. 기존 엔진·규칙 판정은 바꾸지 않았습니다.

## 4. 자동 초안 정확도

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

모든 후보는 신뢰도와 관계없이 담당자가 확인해야 합니다. 이 수치는 원본 좌표와의 기하 비교이며 실서류 인식 정확도나 자동 게시 보증이 아닙니다. 기존 좌표 JSON은 변경하지 않았습니다. 재측정: `python -m demo.backend.tools.measure_form_drafts`.

## 5. 사람이 아침에 결정할 것

1. 범용 사업의 건별 심사 상세를 별도 구현할지 결정해 주세요. 기존 심사표·원본 뷰어를 보호하기 위해 현재는 연결하지 않았습니다.
2. 기존 직접 API(v0) 호환 계약을 유지할지, 운영 전 v1·통합 인증으로 전환할지 결정해 주세요. 신규 범용 신청은 소유자 쿠키를 강제하며 일반 신청 화면은 v1을 사용합니다.
3. JBAI 문장 초안이 필요하면 텍스트 엔드포인트·모델을 별도로 확인한 뒤 켜 주세요. 이번에는 가짜 공급자만 시험했고 기본값은 꺼짐입니다.

## 6. 현황·알려진 문제·남은 일

- 브랜치: `feat/renewal-master`. `git fetch origin` 후 `origin/main`이 `0fe1d27`을 포함함을 확인하여 `7472697`에서 만들었습니다. 이전 전달 번들을 지웠습니다.
- 기존 `postings.py`/`ProgramPosting`을 확장했습니다. `ProgramConfig`는 기존 사업 규칙을 유지합니다. 새 `ProgramForm`과 `ProgramApplicationSnapshot` 테이블은 기존 DB에서도 `create_all`로 추가됩니다. 실제 런타임 DB·저장소를 초기화하거나 지우지 않았습니다.
- `PdfFormsWorkspace`의 원본 PDF 좌표 오버레이와 기존 PDF 내보내기를 재사용합니다. `required_docs.py`의 슬롯과 기존 판독/FAIL 규칙을 유지합니다. `ApplicantApp`은 범용 신청 경로를, 담당자 목록은 기존 탭·사유 펼침을 재사용합니다. 구조·계약 분석은 `research/architecture.md`, `research/generic.md`에 있습니다.
- 기존 HTTP 응답과 시험을 유지하기 위해 신규 작성 화면은 `workflow_version=1` 관리형 API를 사용합니다. 기존 방식의 사업은 목록 계약만 유지하며 온라인 신청을 열지 않습니다. 기존 직접 신청 API의 데모 호환 경계는 운영 전 인증·전환 결정이 남아 있습니다.
- 신규 범용 신청의 입력값은 고정된 공개 필드 ID만 받아 저장하며 주민번호 텍스트 뒷자리를 가립니다. 소유자 쿠키와 입력/출력 허용 목록을 검증했습니다. 서식 사본·보관 PDF는 게시 변경/마감 이후에도 유지합니다.
- 범용 사업은 자격 규칙을 추정하지 않고 담당자에게 미설정 안내를 보여 줍니다. 기존 심사표를 숨기는 분기를 상세 바깥에서 만들 수 없어 범용 목록에서 심사 상세를 열지 않습니다.
- 자동 초안이 약한 서식(특히 자가진단 서식)은 직접 입력칸을 추가해야 합니다. 문서 종류는 기존 슬롯 목록 안에서 선택합니다.
- LLM은 기본 none입니다. 검증 중 실제 JBAI 호출·실서류 생성/열기/출력·다른 저장소 접근·push/PR/병합은 하지 않았습니다. 실제 .env 파일을 읽거나 변경하지 않았습니다. 예제 설정에만 비밀값 없는 옵션을 추가했습니다.
- 사용자 수정 `.trellis/tasks/11-14-renewal-applicant-design/task.json`과 루트 `logo.png`는 보존했고 커밋에서 제외했습니다.

### 0단계 보호 목록과 최종 확인

아래 파일은 초기 SHA-256과 일치합니다(`protected-files.json`). 엔진, 기존 규칙, 원본 좌표 및 기존 시험에도 커밋 차이가 없습니다.

- `demo/frontend/src/pages/officer/ReviewDetail.tsx`
- `demo/frontend/src/pages/officer/DocumentViewer.tsx`
- `demo/frontend/src/pages/officer/officer.css`
- `demo/frontend/src/components/StatusBadge.tsx`
- `demo/frontend/src/components/Skeleton.tsx`
- `demo/frontend/src/components/skeleton.css`
- `demo/frontend/src/components/FilePreview.tsx`
- `demo/frontend/src/components/file-preview.css`
- `demo/frontend/src/hooks/useDelayedFlag.ts`
- `demo/frontend/src/pages/officer/format.ts`

### 화면·번들 증거

- 합성 PDF·PNG와 독립 `/tmp` DB/저장소로 담당자 ①~④ 및 신청자 전체 단계·담당자 탭을 PC 940px에서 확인했습니다. 종단 17항목 통과·페이지 오류 0, 신청 생성 0→1, 담당자 확인 필요 1건, 보관 PDF 200, 다른 소유자 접근 403, 일괄 최종 선정 409입니다(`visual-e2e-result.json`).
- 기존 화면 1440px 비교: 신청 목록 0픽셀, 심사 상세 0픽셀 차이. 사업 목록은 읽기 전용 배지 추가로 621픽셀(0.043125%)만 다릅니다(`visual-pixel-comparison.json`).
- 스크린샷: [담당자 서식 틀](shots/officer-step2.png), [게시 미리보기](shots/officer-step4.png), [신청 서식](shots/applicant-forms.png), [접수증](shots/applicant-receipt.png), [확인 필요 목록](shots/officer-needs-check.png), [기존 심사 상세](shots/final-review.png). 모든 파일 경로는 영문입니다.
- Vite manifest의 신청자 정적 진입 그래프에서 담당자 화면·목업 정적 import는 0입니다. 해당 청크에 `DS-2026-`와 추가 목업 고유 문자열을 `rg`로 검색하여 0건을 확인했습니다(`bundle-proof.json`).
- 수동 서버는 8010/5183만 사용하고 종료했습니다. 사용자의 다른 서버는 건드리지 않았습니다. 화면 검증 재현 스크립트는 `visual_backend.py`, `visual-fixtures.py`, `visual-e2e.mjs`, `visual-officer.mjs`입니다.

## 7. 아침에 실행할 명령

아래 push·PR·병합은 실행하지 않았습니다. 보고서와 위 결정 사항을 확인한 뒤 선택해서 실행합니다.

```bash
git switch feat/renewal-master
git status --short
git push -u origin feat/renewal-master
gh pr create --base main --head feat/renewal-master --title "feat: program authoring and applicant renewal" --body-file .trellis/tasks/11-15-renewal-master/report.md
# PR 검토 후에만 실행
gh pr merge --merge
```

일반 실행(실제 런타임 저장소를 사용):

```bash
source .venv/bin/activate
python -m uvicorn demo.backend.main:app --host 127.0.0.1 --port 8010
```

```bash
cd demo/frontend
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

확인 주소: `http://127.0.0.1:5183/`, `/officer/programs/new`, `/officer/programs/<id>`, `/apply/programs/<id>/identity`, `/officer?mock=1`, `http://127.0.0.1:8010/docs`. LLM 설정 파일을 명시적으로 적용하려면 백엔드 명령에 `--env-file .env`를 더합니다. 이번 야간 검증에는 실제 설정 파일을 적용하지 않았습니다.

전체 게이트 재실행: `.venv/bin/python .trellis/tasks/11-15-renewal-master/run_gate.py morning`.
