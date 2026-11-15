# 서식 입력칸 초안 탐지 보강 보고서

- 브랜치: `feat/form-draft-detection` (main 641db8d에서 분기). push·PR·병합 안 함.
- 측정: 저장소 공개 빈 서식 8종(`demo/fixtures/templates`) + 수작업 좌표(`demo/fixtures/form_coords`). 규칙 시험은 모두 시험 안에서 PyMuPDF로 만든 합성 PDF.
- 원자료: `measure-baseline.*`, `measure-final.*`, `page-timing.json`, `overfit-grep.txt`, `gate/gate-*.json`, `e2e-result.json`, `security-probes.json`, `shots/`.

## 1. 단계 표

| 단계 | 결과 | 커밋 | 새 시험 수 | 비고 |
|---|---|---|---:|---|
| 0 | O | – | 0 | df 여유 32Gi, 보호 해시 10/10, A·B·C·D 기준선 통과 |
| 1 측정 도구 | O | c9f8abe | 5 | precision·false_fields·oversized·missed·extra·전체 합계 줄 |
| 2 탐지 규칙 | O | 0349dad | 21 | 규칙 a~e, 중복 제거, 값 칸 양보 |
| 3 칸 맞춤 (선택) | O | 38d28c5 | 8 (백엔드 5, 프런트 3) | `POST …/workspace/forms/{form_id}/snap`, 편집기 "칸 추가" 클릭에만 연결 |
| 4 문서·종단 | O | 이 보고서가 포함된 문서 커밋(HEAD) | 0 | spec 문서, Playwright 종단 1회 통과 |

실패 단계 없음 → `failed-stageN.patch` 없음.

## 2. 서식별 표 (기준선 → 최종)

| 서식 | 정답 칸 | 자동 칸 | 일치 | 재현율 | 정밀도 | oversized | 종류 일치율 |
|---|---:|---:|---:|---:|---:|---:|---:|
| job_application | 41 | 30 → 33 | 29 → 33 | 70.7% → 80.5% | 96.7% → 100.0% | 0 → 0 | 100% → 100% |
| job_consent | 8 | 8 → 8 | 4 → 7 | 50.0% → 87.5% | 50.0% → 87.5% | 0 → 0 | 100% → 100% |
| job_interview_confirmation | 5 | 12 → 14 | 5 → 5 | 100.0% → 100.0% | 41.7% → 35.7% | 0 → 0 | 100% → 100% |
| 서식1 | 69 | 59 → 60 | 56 → 58 | 81.2% → 84.1% | 94.9% → 96.7% | 0 → 0 | 100% → 100% |
| 서식2 | 16 | 0 → 16 | 0 → 16 | 0.0% → 100.0% | 0.0% → 100.0% | 0 → 0 | 0% → 100% |
| 서식3 | 7 | 5 → 7 | 4 → 7 | 57.1% → 100.0% | 80.0% → 100.0% | 1 → 0 | 100% → 100% |
| 서식4 | 5 | 4 → 5 | 2 → 5 | 40.0% → 100.0% | 50.0% → 100.0% | 2 → 0 | 100% → 100% |
| 서식5 | 8 | 3 → 8 | 2 → 8 | 25.0% → 100.0% | 66.7% → 100.0% | 1 → 0 | 100% → 100% |
| **전체 (micro)** | **159** | **121 → 151** | **102 → 139** | **64.1% → 87.4%** | **84.3% → 92.0%** | **4 → 0** | **100% → 100%** |

목표 대비:

| 목표 | 결과 | 판정 |
|---|---|---|
| 전체 재현율 ≥ 80% | 87.4% | O |
| 서식2 ≥ 80% | 100.0% | O |
| 동의서류 4종 각각 ≥ 75% | job_consent 87.5%, 서식3·4·5 100% | O |
| job_application·서식1·job_interview_confirmation 기존 이상 | 80.5% / 84.1% / 100% | O |
| 전체 정밀도 ≥ 기준선 | 92.0% (지시문 기준 79%, 실측 기준 84.3% 모두 이상) | O |
| oversized 0 | 0 | O |

기준선 자동 칸 수는 지시문의 129개가 아니라 실측 121개였음(정밀도 84.3%). 더 엄격한 실측값을 기준으로 판정함.
job_interview_confirmation 정밀도만 41.7% → 35.7%로 내려감: 새 날짜 빈칸 2개(월·일)가 정답 좌표에 없음(3절).

## 3. 남은 missed·extra와 원인

| 서식 | 구분 | 필드 이름 / 종류 | 원인 |
|---|---|---|---|
| job_application | missed | bankName, accountNo (text) | "계좌번호( ___ 은행) ___" 괄호 안 빈칸. 라벨이 허용 어휘가 아니고 콜론·밑줄 없음 |
| job_application | missed | job.interview.1/2.location, job.suit.1/2.location (text) | 칸에 "전북특별자치도 OO시/군" 문구가 미리 인쇄돼 있어 빈 값 칸이 아님 |
| job_application | missed | job.certificate.1/2.organizer (text) | 위와 같은 표 구조(인쇄 문구가 있는 값 칸). 규칙 a~e 대상 아님 |
| job_consent | missed + extra | name (text) / "신청인 :" (text) | 탐지 칸은 콜론 뒤부터 (인) 앞까지(397–514), 정답은 397–445. IoU 0.41 |
| job_interview_confirmation | extra | 회사명·소재지·업태/업종·담당자·연락처·면접장소·응시직군 (text) ×7 | 기업 작성란 표의 값 칸. 실제 빈칸이지만 정답 좌표는 신청자 칸만 포함 |
| job_interview_confirmation | extra | 월, 일 (date) | "2026년 월 일" 줄의 실제 빈칸. 정답 좌표에 없음 |
| 서식1 | missed | priorName, priorPeriod, priorAmount (text) | "(사업명 : , 기간 : , 수령액 : )". 라벨이 허용 어휘가 아님 |
| 서식1 | missed + extra | priorJoined.미참여 (check) / 상자 183.6–194.7 | "여부□" 단어 안의 □ 상자를 단어 시작 위치에 놓음(기존 상자 문자 처리) |
| 서식1 | missed | workplaceName (text) | "근무처 명 :" 라벨이 허용 어휘가 아님 |
| 서식1 | missed | householdSizeCount (text) | 규칙 a~e 대상 아님(분석하지 않음) |
| 서식1 | missed | bankName, accountNo, accountHolder (text, 2쪽) | "(은행명 : / 계좌번호 : / 예금주 : )". 허용 어휘가 아님 |
| 서식1 | missed | writtenMonth, writtenDay (text, 2쪽) | "2026.  .  ." 점 날짜 형식. 규칙 b는 년·월·일 토큰만 다룸 |
| 서식1 | extra | check / 163.6–173.5 | 안내문 중간의 "□ ✓(체크)표 하세요". 규칙 e(2)는 줄 맨 앞 상자만 다룸 |

## 4. 규칙별 합성 시험 (`demo/backend/tests/test_form_draft_inline.py`)

| 규칙 | 잡아야 함 (O) | 잡으면 안 됨 (X) |
|---|---|---|
| a 선택어 | `test_choice_word_pair_becomes_grouped_word_checks_without_comma` ("예," 상자에서 쉼표 제외, 같은 group, 0.6) · `test_multi_word_choice_pairs_are_joined` (동의함/동의하지 않음, 해당/해당 없음) | `test_choice_word_inside_sentence_is_not_a_check` ("예시를 참고하세요" → 0) · `test_choice_header_split_by_cell_border_is_not_a_word_pair` (칸 경계로 나뉜 "예 \| 아니오" 머리글 → 0) · `test_choice_words_next_to_printed_boxes_use_the_boxes_only` (□ 2개만, 중복 0) |
| b 줄 안 날짜 | `test_printed_century_and_spaced_date_tokens_yield_three_blanks` ("20 년 월 일" → 연·월·일 3칸) | `test_filled_or_tight_dates_do_not_yield_blanks` ("2026년 11월 15일" → 0, "2026 년" 붙은 연도 → 월·일만) |
| c 라벨 뒤 빈칸 | `test_colon_label_blank_runs_to_cell_border_with_autofill` (성명→name, 생년월일→birth·date, 칸 경계 −3pt) · `test_underlined_label_without_colon_is_a_blank` (연락처 + 밑줄 → mobile) | `test_filled_or_unmarked_labels_do_not_yield_blanks` ("성명: 홍길동", 콜론 없는 "주소", "수집 항목: 성명, …" → 0) · `test_label_blank_inside_label_cell_yields_to_value_cell` |
| d 서명 표시 | `test_name_blank_and_seal_mark_are_split_without_overlap` ("성 명: ___ (서명 또는 인)" → 이름 칸 + 서명 칸, 겹침 0) · `test_seal_mark_after_plain_blank_includes_the_blank` | `test_signature_word_in_sentence_or_attached_text_is_not_a_mark` ("서명합니다", "홍길동(인)" → 0) |
| e(1) 큰 칸 | `test_short_date_cell_still_yields_cell_hint` (한 줄 "신청일" 칸 → 칸 전체 date 0.52 유지) | `test_large_notice_cell_with_date_keeps_only_inline_blanks` (큰 안내문 칸 안 "20 년 월 일" → 칸 전체 0, 줄 안 3칸만, 15% 초과 0) |
| e(2) 글머리 | `test_boxes_with_choices_or_stacked_options_are_kept` (선택어가 있는 줄, 같은 열에 쌓인 선택지 → 4칸) | `test_leading_box_before_sentence_is_a_bullet_not_a_check` (□ 글자 + 그린 상자 뒤 긴 문장 → 0) |
| 순서·중복·성능 | `test_acroform_widgets_still_suppress_inline_rules` · `test_overlapping_candidates_keep_the_more_confident_one_in_order` · `test_dense_vector_page_drafts_under_two_seconds` (선 4,000개 쪽) | — |

기존 `test_form_draft.py` 10개는 고치지 않고 통과함(라벨 없는 빈 사각형 0칸, AcroForm 우선, 빈·이미지 PDF manual_required 포함).

## 5. 쪽별 초안 생성 시간 (`_vector_fields`, 5회 중 최댓값, 이 맥)

| 서식 | 쪽 | 도형 수 | 자동 칸 | 최대 시간 |
|---|---:|---:|---:|---:|
| job_application | 1 | 147 | 33 | 0.016s |
| job_consent | 1 | 57 | 8 | 0.009s |
| job_interview_confirmation | 1 | 37 | 14 | 0.003s |
| 서식1 | 1 | 94 | 52 | 0.039s |
| 서식1 | 2 | 28 | 8 | 0.005s |
| 서식2 | 1 | 3759 | 16 | 0.072s |
| 서식3 | 1 | 50 | 7 | 0.015s |
| 서식4 | 1 | 48 | 5 | 0.008s |
| 서식5 | 1 | 61 | 8 | 0.009s |

모든 쪽 2초 미만 O.

## 6. 과적합 점검 (`overfit-grep.txt`)

| 검사 (draft.py) | 결과 |
|---|---|
| fixture 이름 (`job_application\|job_consent\|job_interview\|서식[0-9]\|form_coords\|templates/`) | 1건: 3행 모듈 설명문의 "form_coords" 단어(main부터 있던 줄) |
| form_no 값 | 1건: `draft_layout(..., form_no: str = "form_1")` 기본 인자(main부터 있던 줄) |
| 4자리 이상 숫자 `[0-9]{4,}` | 0 |
| 특정 서식 문장 (`전북\|두배적금\|취업\|청년\|농협`) | 0 |
| 이 작업에서 추가한 줄 중 위 패턴 | 0 |

어휘: 선택어 5쌍, 라벨은 기존 `_AUTOFILL` 키, 서명 표시 3종만 씀.

## 7. 전체 시험, 보호 파일, 화면 변경

| 묶음 | 기준선 | 1단계 | 2단계 | 3단계 | 최종 |
|---|---|---|---|---|---|
| A 엔진 | 1267 통과 | 1267 | 1267 | 1267 | 1267 통과 |
| B 백엔드 | 1645 통과 | 1650 | 1671 | 1676 | 1676 통과 |
| C 시나리오 18개 모듈 | 18/18 | 18/18 | 18/18 | 18/18 | 18/18 |
| D 프런트 tsc·oxlint·build·단위 | 69 통과, 경고 0 | 69, 0 | 69, 0 | 72, 0 | 72 통과, lint 경고 0, build 청크 경고 0 |

- 보호 파일 10개 sha256: 시작 O, 각 커밋 전 O (`check_staged.py`), 끝 O (10/10).
- 신청자 화면·job_package 기존 화면 변경 0: main 대비 바뀐 프런트 파일은 `ProgramTemplateEditor.tsx`(담당자 서식 편집기), `program-workspace-api.ts`(담당자 API 함수 1개 추가), 새 파일 `lib/form-snap.ts`, `tests/form-snap.test.ts`뿐. `src/forms/*`, 신청자 페이지, job_package 페이지 diff 0.
- 저장된 `layout_json` 일괄 갱신 코드 없음: `draft_layout` 호출 위치는 업로드(`posting_workspace`)와 "자동 초안 다시 만들기"(`posting_draft`) 그대로.
- 종단 시험(Playwright, 격리 서버, 합성 데이터만): O. 담당자 로그인 → 새 사업 올리기(form2-self-check.pdf, form5-consent.pdf) → 자동 칸 16·8개(전부 확인 필요) → 칸 추가 클릭 맞춤 1회(점 150,156 → 상자 [59.61, 151.27, 240.95, 160.72], text) → 17·8칸 확인, 서식 2개 확정 → 게시 → 신청자 본인인증 → 서식2 선택칸 8개, 서식5 선택칸 1개 체크와 서명 1개 → 사진 업로드 → 제출 접수. 페이지 오류 0. 캡처 9장 `shots/01…09`.

## 8. 보안 확인 표 (3단계)

| 방법 | 경로 | 무쿠키 | 담당자 |
|---|---|---:|---:|
| POST | /api/officer/postings/{id}/workspace/forms/{form_id}/snap | 401 | 200 |

백엔드 시험: 세션 없음 401, 다른 사업의 서식 404, 없는 서식 404, 없는 사업 404, 잘못된 쪽 422. 응답 키는 `box`, `field_type`, `label`(200자 이하)뿐.

## 9. 사람이 결정할 것

1. 선택어 칸 표시 방식: 서식2처럼 단어 자체가 칸이면 신청자 화면에서 체크 표시가 단어를 덮음(캡처 06). 기존 수작업 서식2는 `radio_text` 전용 표시를 씀. 자동 칸에도 동그라미나 단어 옆 표시를 쓸지 결정 필요.
2. 라벨 어휘 확대 여부: "신청인", "근무처 명", "사업명", "은행명", "계좌번호", "예금주"를 규칙 c 어휘에 넣으면 서식1·job_application 누락 6~8칸이 잡힐 가능성이 있음. 지금은 허용 어휘 제한 때문에 넣지 않음.
3. 점 날짜("2026.  .  .")를 규칙 b에 포함할지 결정 필요(서식1 2쪽 2칸).
4. 단어 안 상자 문자 위치("여부□")를 글자 위치로 옮길지 결정 필요. 기존 상자 문자 처리의 위치 오류이며 이번 범위 밖이라 그대로 둠.
5. job_interview_confirmation 기업 작성란 7칸과 날짜 2칸: 실제 빈칸이지만 정답 좌표에는 없음. 정답 좌표에 추가할지, 신청자 칸만 남길지 결정 필요.
6. 칸 맞춤 경로 이름: 지시문의 예시 `/forms/{form_id}/snap` 대신 기존 경로와 같은 `/workspace/forms/{form_id}/snap`을 씀.
