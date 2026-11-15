# 서식 입력칸 초안 후속 작업 보고서

- 브랜치: `feat/form-draft-followup` (main c8161f4에서 분기). push·PR·병합 안 함. Co-Authored-By 없음.
- 측정: 저장소 공개 빈 서식 8종(`demo/fixtures/templates`) + 수작업 좌표(`demo/fixtures/form_coords`, 수정 안 함) + 측정 전용 보충(`demo/fixtures/form_draft_eval`). 규칙 시험은 모두 시험 안에서 PyMuPDF로 만든 합성 PDF.
- 원자료: `measure-baseline.*`, `measure-stage2.*`, `measure-stage3.*`, `measure-final.*`, `gate/gate-*.json`, `pixel/comparison.json`, `e2e-result-*.json`, `e2e-submitted-*.json`, `overfit-grep.txt`, `shots/`, `failed-stage1.patch`, `notes.md`.

## 1. 단계 표

| 단계 | 결과 | 커밋 | 새 시험 수 | 비고 |
|---|---|---|---:|---|
| 0 | O | – | 0 | df 여유 33Gi, 보호 해시 10/10, A1267·B1676·C18·D72 기준선 통과 |
| 1 선택어 radio·○ 표시 | **X (failed-stage1.patch)** | – | (patch 안: 백엔드 8, 프런트 4) | 구현·새 시험·픽셀·종단은 통과. 기존 시험 `test_form_draft_inline.py` 가 규칙 a 칸을 `field_type == "check"`로 찾아 3개 실패 → 기존 시험 수정 금지라 patch로 빼고 되돌림(3절 끝, 7절 1) |
| 2 탐지 보강 | O | 077ec95 | 11 | a 라벨 어휘, b 점 날짜, c 단어 안 상자, d 라벨 정리, e 칸 맞춤 쪽 범위 시험 |
| 3 측정 보충 | O | a6ed6e6 | 4 | `form_draft_eval/job_interview_confirmation.extra.json` 13칸, "보충 칸·보충 포함 일치율·보충 포함 정밀도" 열 추가 |
| 4 문서·종단 | O | 이 보고서가 포함된 문서 커밋(HEAD) | 0 | spec 문서 갱신, Playwright 종단 2회(커밋 코드 O, 1단계 patch 임시 적용 O) |

## 2. 서식별 재현율·정밀도·oversized (기준선 → 최종, 보충 포함 열 따로)

기준선 = main(c8161f4) 코드. 최종 = 2·3단계 커밋 코드(1단계 미적용). 1단계는 칸 위치를 바꾸지 않아 patch 적용 시에도 숫자는 같음(종류 일치는 렌더링 종류 `type` 기준이라 radio도 check).

| 서식 | 정답 칸 | 자동 칸 | 일치 | 재현율 | 정밀도 | oversized | 보충 칸 | 보충 포함 재현율 | 보충 포함 정밀도 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| job_application | 41 | 33 → 33 | 33 → 33 | 80.5% → 80.5% | 100.0% → 100.0% | 0 → 0 | 0 | 80.5% | 100.0% |
| job_consent | 8 | 8 → 8 | 7 → 7 | 87.5% → 87.5% | 87.5% → 87.5% | 0 → 0 | 0 | 87.5% | 87.5% |
| job_interview_confirmation | 5 | 14 → 14 | 5 → 5 | 100.0% → 100.0% | 35.7% → 35.7% | 0 → 0 | 13 | 77.8% | 100.0% |
| 서식1 | 69 | 60 → 67 | 58 → 66 | 84.1% → 95.7% | 96.7% → 98.5% | 0 → 0 | 0 | 95.7% | 98.5% |
| 서식2 | 16 | 16 → 16 | 16 → 16 | 100.0% → 100.0% | 100.0% → 100.0% | 0 → 0 | 0 | 100.0% | 100.0% |
| 서식3 | 7 | 7 → 7 | 7 → 7 | 100.0% → 100.0% | 100.0% → 100.0% | 0 → 0 | 0 | 100.0% | 100.0% |
| 서식4 | 5 | 5 → 5 | 5 → 5 | 100.0% → 100.0% | 100.0% → 100.0% | 0 → 0 | 0 | 100.0% | 100.0% |
| 서식5 | 8 | 8 → 8 | 8 → 8 | 100.0% → 100.0% | 100.0% → 100.0% | 0 → 0 | 0 | 100.0% | 100.0% |
| **전체 (micro)** | **159** | **151 → 158** | **139 → 147** | **87.4% → 92.5%** | **92.0% → 93.0%** | **0 → 0** | **13** | **90.7%** | **98.7%** |

- 서식1 +8칸: 라벨 어휘 5(사업명, 근무처 명, 은행명, 계좌번호, 예금주), 점 날짜 2(writtenMonth, writtenDay), 단어 안 상자 1(priorJoined.미참여, "여부□"). 기존 extra 였던 "여부□" 상자 오검출도 사라짐(extra 2 → 1).
- 보충 포함 열: job_interview_confirmation 의 정밀도 35.7% → 100%(자동 칸 14개가 모두 실제 빈칸으로 확인됨), 재현율은 보충 13칸 중 4칸 미탐지로 77.8%. 보충 좌표는 사람 확인 전이라 이 열은 참고값.
- 보충 13칸(**사람 확인 필요**, 캡처 `shots/stage3-job_interview_confirmation-supplement.png`): 기업 작성란 회사명·소재지·업태/업종·담당자·연락처·면접일시·면접장소·응시직군 8, "2026년 월 일" 월·일 2, 아래 서명줄 회사명·담당자·(서명/인) 3. 좌표는 서식의 괘선·인쇄 글자 위치에서 계산(`build_eval_supplement.py`, draft.py 출력 미사용). 캡처를 눈으로 확인한 결과 13칸 모두 실제 빈칸 위에 있음.

## 3. 남은 missed / extra 와 원인

| 서식 | 구분 | 필드 / 종류 | 원인 |
|---|---|---|---|
| job_application | missed | bankName, accountNo (text) | "계좌번호( ___ 은행) ___": 콜론·밑줄이 없고 괄호가 라벨에 붙음. 규칙 c 조건(콜론 또는 밑줄) 밖 |
| job_application | missed | job.interview.1/2.location, job.suit.1/2.location, job.certificate.1/2.organizer (text) ×6 | 값 칸에 안내 문구가 미리 인쇄됨(빈 칸이 아님). 규칙 대상 아님 |
| job_consent | missed + extra | name / "신청인" [397.3–514.3] | 탐지 칸은 콜론 뒤부터 (인) 앞까지, 정답은 397–445(IoU 0.41). "신청인"을 라벨로 넣어도 같은 칸 |
| job_interview_confirmation | extra (보충 포함 시 0) | 기업 작성란 7, 월·일 2 | 기존 좌표에 없을 뿐 실제 빈칸. 보충 포함 열에서는 모두 일치 |
| job_interview_confirmation | 보충 missed | supplement.datetime | "2026. 00. 00. 00:00~00:00" 예시 문구가 인쇄된 칸이라 빈 칸으로 보지 않음 |
| job_interview_confirmation | 보충 missed | supplement.sign.company, sign.manager | "회사명 :", "담당자 :" 는 라벨 어휘가 아님(허용 목록 밖) |
| job_interview_confirmation | 보충 missed | supplement.sign.seal | 표시 "(서명/인)"이 서명 표시 3종((서명), (인), (서명 또는 인))에 없음 |
| 서식1 | missed | priorPeriod, priorAmount (text) | "기간 : , 수령액 :" — 라벨 어휘가 아님(지시 목록 밖) |
| 서식1 | missed | householdSizeCount (text) | 규칙 대상 아님(분석하지 않음) |
| 서식1 | extra | check "✓(체크)표 하세요" [163.6–173.5] | 안내문 가운데 □. 줄 맨 앞 상자만 글머리로 봄(규칙 e(2)) |

**1단계 실패 상세**: 지시는 규칙 a 칸을 `field_type "radio"`로 만들라는 것이고, 기존 `test_form_draft_inline.py`는 규칙 a 칸을 `field_type == "check"`로 골라 확인함. 실패 3개(`test_choice_word_pair_becomes_grouped_word_checks_without_comma`, `test_multi_word_choice_pairs_are_joined`, `test_dense_vector_page_drafts_under_two_seconds`), 의미가 약해지는 2개(부정 시험 `…inside_sentence…`, `…split_by_cell_border…` 는 radio가 되면 빈 목록으로 그냥 통과). 필요한 수정은 시험 5개의 찾는 조건 1줄씩("check" → "radio", 부정 시험은 `in ("check", "radio")`)이며 다른 기대값(라벨, 같은 group, 쉼표 제외, 신뢰도 0.6, type "check")은 그대로. 기존 시험 수정 금지라 적용하지 않음(자동 승인 분류기도 막음).

## 4. 규칙별 합성 시험

2단계 `demo/backend/tests/test_form_draft_followup.py` (11개, 커밋됨)

| 규칙 | 잡아야 함 (O) | 잡으면 안 됨 (X) |
|---|---|---|
| a 라벨 어휘 | `test_general_labels_with_colons_yield_blanks_without_autofill` ("(은행명 : / 계좌번호 : / 예금주 : )", "근무처 명 :", "보호자:" → 5칸, autofill None, 다음 구분자 앞에서 끝남) · `test_existing_autofill_sources_are_not_widened` ("신청인 :" → None, "성명 :" → name) | `test_general_label_words_in_lists_filled_or_unmarked_are_not_blanks` ("성명, 은행명, 계좌번호 등", "소속: 합성기관", 콜론 없는 "확인자 직위", 문장 속 "사업명" → 0) |
| b 점 날짜 | `test_dotted_date_with_printed_century_yields_three_blanks` ("20 . . ." → 연·월·일, 오른쪽 끝 249/289/329) · `test_dotted_date_with_printed_year_yields_month_and_day` ("2026. . ." → 월·일) | `test_decimals_numbering_and_filled_dotted_dates_are_not_blanks` ("1. 신청 자격", "10. … 3.14", "2026. 11. 15.", "2026.11.15.", 틈 없는 점, 한 자리 "1. . ." → 날짜 0) |
| c 단어 안 상자 | `test_box_inside_word_is_placed_on_its_glyph` ("여부□", "동의□" → 상자 x0 가 단어 시작 + 15pt 뒤, 단어 안) | `test_leading_box_keeps_its_position_and_plain_text_has_none` ("□동의 □미동의" → 기존과 같은 위치·폭, 상자 없는 "여부 확인 후 동의" → 0) |
| d 라벨 정리 | `test_label_drops_trailing_colons_and_keeps_the_anchor` ("성명 :", "생년월일：", "주소:" → 라벨 콜론 제거, anchor 원문) | `test_label_without_trailing_colon_is_unchanged` ("연락처" 밑줄 → 라벨=anchor, 채워진 "구분: 내용" → 0) |
| e 칸 맞춤 쪽 | `test_snap_route_rejects_pages_outside_the_document` (쪽 0 → 200) | 같은 시험: 쪽 −1 → 422, 쪽 수(1) → 422 |

3단계 `demo/backend/tests/test_form_draft_eval_supplement.py` (4개, 커밋됨): 보충 열 분리·기존 값 불변, 보충 파일 없음/경로 탈출(`../form_coords/서식1`) → 보충 0, 보충 파일은 `supplement.` 키·"사람 확인 필요"·기존 좌표와 IoU < 0.5, 실제 측정에서 job_interview_confirmation 보충 13칸.

1단계 patch 안 시험(미커밋): 백엔드 `test_form_choice_marks.py` 8개(선택어 쌍 → radio·같은 group·circle / 인쇄 상자는 check 유지 / ○는 고른 단어만 감쌈·채운 사각형 0 / 기존 □ 체크는 채운 사각형 유지 / ○ 여백 공식이 화면과 같음 / 필수 group은 하나 고르기 전 제출 차단·둘 다 고르면 422·바꾸면 다른 쪽 false·제출 PDF ○ 1개 / 선택 group은 차단 안 함 / `choice_mark` 는 "circle"만 허용·check/radio에만 보존) 모두 통과. 프런트 `tests/form-choice.test.ts` 4개(한쪽 고르면 같은 group 다른 쪽 해제, 다른 group·일반 check 영향 없음, 필수 판정, ○ 여백) 통과.

## 5. job_package 서식2·기존 □ 렌더링 불변 확인

| 확인 | main | 1단계 patch 적용 | 최종 커밋 |
|---|---|---|---|
| 픽셀(110dpi PNG sha256): 서식2 radio_text 4문항 선택 | 기준 | O 동일 | O 동일 |
| 픽셀: 서식1 □ 체크 2개 | 기준 | O 동일 | O 동일 |
| 픽셀: job_consent □ 체크 2개 | 기준 | O 동일 | O 동일 |
| 픽셀: job_application □ 체크 2개 | 기준 | O 동일 | O 동일 |
| 시나리오 run_p14_pdf_forms(서식2 radio_text·□ 체크 포함) 외 18개 모듈 | 18/18 | (게이트 미실행: patch 단계 실패) | 18/18 |

종단 시험(Playwright, 격리 서버 `e2e_backend.py` + `--env-file .env` 값은 합성값으로 덮어씀, 합성 데이터, 영문 파일 이름 form2-self-check.pdf·form5-consent.pdf):

| 단계 | 커밋 코드 | 1단계 patch 임시 적용 |
|---|---|---|
| 담당자 로그인 → 2개 서식 올리기 → 자동 칸 | O 16(check 16)·8칸, 전부 확인 필요 | O 16(radio 16, circle 16)·8칸, 전부 확인 필요 |
| 칸 확인 → 서식 확정 2개 → 게시 | O | O |
| 신청자 1번 문항 "예" 고름 | 예 O / 아니오 X | 예 O / 아니오 X, 화면 ○ 1개 |
| "아니오"로 바꿈 | **예 O / 아니오 O (둘 다 체크, 해제 안 됨)** | **예 X / 아니오 O (다른 쪽 해제)**, 화면 ○ 1개 |
| 제출 | O | O |
| 제출 PDF 서식2 쪽 ○ | 0 (채운 □ 체크 8개) | **8** (1번 "아니오", 2~8번 "예"; 채운 □ 0) |
| 페이지 오류 | 0 | 0 |

캡처: `shots/committed-01…08`, `shots/stage1-patch-01…08` (08 = 제출 PDF 서식2 쪽). 서식5 쪽의 곡선 2개는 원본 서식 자체의 도형(원본에도 2개).

## 6. 전체 시험 표·보호 해시

| 묶음 | 기준선 | 1단계 | 2단계 | 3단계 | 최종 |
|---|---|---|---|---|---|
| A 엔진 | 1267 통과 | – (patch) | 1267 | 1267 | 1267 통과 |
| B 백엔드 | 1676 통과 | – (patch; 관련 시험만: 새 8 통과, 기존 inline 3 실패) | 1687 | 1691 | 1691 통과 |
| C 시나리오 18개 모듈 | 18/18 | – | 18/18 | 18/18 | 18/18 |
| D 프런트 tsc·oxlint·build·단위 | 72 통과, 경고 0 | – (patch; tsc·oxlint 0·build 경고 0·새 단위 4 통과) | 72, 0 | 72, 0 | 72 통과, lint 경고 0, build 청크 경고 0 |

- 보호 파일 10개 sha256: 시작 O(10/10), 각 커밋 전 O(`check_staged.py`), 끝 O(10/10). 디스크 여유 시작 33Gi → 끝 31Gi.
- 커밋 전 검사: sk- 형태 값·비공개 원본 폴더 참조·.env·설정 비밀값·공백 오류 0, 사용자 미커밋 파일(task.json, logo.png, 신청자 화면 5개 파일) 스테이지 0.
- 과적합 검사(`overfit-grep.txt`): 2단계에서 draft.py 에 추가한 줄 중 서식 이름·form_no·4자리 이상 숫자·특정 서식 문장 0건.
- 저장된 `layout_json` 일괄 갱신 코드 없음, OCR·외부 서비스·LLM 없음, 모든 자동 칸 needs_review=True.

## 7. 사람이 결정할 것

1. **1단계 적용 여부**: `failed-stage1.patch`(10개 파일)는 HEAD에 깨끗이 적용되고 종단·픽셀·새 시험 모두 통과. 적용하려면 `test_form_draft_inline.py` 시험 5개의 찾는 조건 1줄씩 수정 허락이 필요(3절 끝). 대안: 초안은 `field_type "check"` + `choice_mark` 로 두고 담당자 저장 시 radio로 바꾸는 방식(기존 시험 그대로, 다만 "규칙 a 칸은 radio" 지시와 다름).
2. 보충 정답 13칸 확정: 캡처로 확인 필요. 특히 면접일시 칸(예시 문구가 인쇄된 칸)을 빈칸으로 볼지, 아래 서명줄 3칸을 포함할지.
3. 라벨 어휘 추가 여부: "기간", "수령액", "회사명", "담당자" 를 넣으면 서식1 2칸, job_interview_confirmation 보충 2칸이 잡힐 가능성. 서명 표시에 "(서명/인)" 추가 여부.
4. "계좌번호( ___ 은행)" 처럼 괄호가 붙은 라벨(콜론 없음)을 빈칸으로 볼 규칙을 만들지(job_application 2칸).
5. 라벨 앞 괄호: 지금 라벨은 "(사업명", "(은행명" 처럼 여는 괄호를 남김(지시 d는 끝 콜론·공백만 지움). 여는 괄호도 지울지.
6. 사용자 미커밋 변경(신청자 화면 5개 파일)은 이번 작업 시작 전부터 있던 것으로, 게이트 D는 이 변경이 있는 작업 트리에서 통과함. 커밋하지 않고 그대로 둠.

## 8. 후속 결정 반영 (2026-11-16, 9b2e581 이후)

사람 결정(1단계 적용·보충 정답 정리·라벨 어휘/정리)을 반영한 결과. 금지 사항은 그대로이고, 예외는 `test_form_draft_inline.py` 규칙 a 칸 고르는 조건 5줄뿐.

### 8.1 결과 표

| 항목 | 결과 | 커밋 | 새 시험 | 비고 |
|---|---|---|---:|---|
| 1. 1단계 적용(radio + ○) | O | b532bb1 | 백엔드 8, 프런트 4 | `failed-stage1.patch` 적용 + 허락된 시험 5줄 수정 |
| 3-1. 라벨 어휘 기간·수령액·회사명·담당자 | O | 6e3fd63 | 3 | `autofill_source` None, `_AUTOFILL` 그대로 |
| 3-2. 서명 표시 "(서명/인)" | O | 6e3fd63 | 3 | |
| 3-3. 짝 없는 앞 여는 괄호 지우기 | **X (failed-decision3-bracket.patch)** | – | (patch 안: 2) | 기존 시험이 라벨 "(은행명"을 고정 → 8.3 |
| 2. 보충 정답에서 면접일시 칸 빼기 | **X (failed-decision2-supplement.patch)** | – | 0 | 기존 시험이 보충 13칸·18칸을 고정 → 8.3 |
| 4. 문서·종단·측정 | O | 문서 커밋(HEAD) | 0 | spec 갱신, Playwright 종단 1회 O |

- 커밋 이름: 2·3을 한 커밋(`feat(forms): refine draft labels and evaluation supplements`)으로 하라는 지시였으나, 보충 정답 정리가 실패 patch로 빠져 커밋 내용과 맞도록 `feat(forms): refine draft labels`로 커밋함.

### 8.2 수정한 기존 시험 5줄 (`demo/backend/tests/test_form_draft_inline.py`)

| 줄 | 시험 이름 | 이전 조건 | 이후 조건 | 빈 목록 아님 확인 |
|---:|---|---|---|---|
| 43 | `test_choice_word_pair_becomes_grouped_word_checks_without_comma` | `field["field_type"] == "check"` | `field["field_type"] == "radio" and field.get("choice_mark") == "circle"` | 기존 assert 라벨 목록 `["예", "아니오"]` (2개) |
| 57 | `test_multi_word_choice_pairs_are_joined` | `field["field_type"] == "check"` | `field["field_type"] == "radio" and field.get("choice_mark") == "circle"` | 기존 assert 라벨 4개 목록 |
| 65 | `test_choice_word_inside_sentence_is_not_a_check` | `field["field_type"] == "check"` | `field["field_type"] in ("check", "radio")` | 부정 시험(0개) |
| 74 | `test_choice_header_split_by_cell_border_is_not_a_word_pair` | `field["field_type"] == "check"` | `field["field_type"] in ("check", "radio")` | 부정 시험(0개) |
| 269 | `test_dense_vector_page_drafts_under_two_seconds` | `field["field_type"] == "check"` | `field["field_type"] == "radio" and field.get("choice_mark") == "circle"` | 기존 assert `len(...) == 2` |

- 양성 시험 3개는 모두 개수를 고정하는 기존 assert가 있어 새 개수 assert를 더하지 않음. 다른 assert·기대값(라벨·group·쉼표 제외·신뢰도 0.6·`type == "check"`)·시험 이름은 그대로.

### 8.3 실패 처리한 두 항목 (사람 결정 필요)

| patch | 내용 | 충돌한 기존 시험(이전 커밋에서 이 작업이 만든 시험) | 적용에 필요한 시험 수정 |
|---|---|---|---|
| `failed-decision3-bracket.patch` | draft.py `_clean_label`: 끝 콜론·공백 + 짝 없는 앞 `(`·`（`·`[` 제거, anchor 원문 유지. 새 시험 2개(잡을 것 `(은행명 :`→`은행명`, `[소속 :`→`소속` / 잡지 말 것 `(서명)`·`(인)` 그대로) | `test_form_draft_followup.py::test_general_labels_with_colons_yield_blanks_without_autofill` (46·49줄 라벨 `"(은행명"`) | 46·49줄 `"(은행명"` → `"은행명"` |
| `failed-decision2-supplement.patch` | `job_interview_confirmation.extra.json` 에서 `supplement.datetime` 제거(13→12칸, "사람 확인 필요" 유지), `build_eval_supplement.py` 에서 면접일시 제외 | `test_form_draft_eval_supplement.py::test_measure_reports_the_supplemented_interview_confirmation` (`supplement_fields == 13`, 보충 포함 `reference_fields == 18`) | `13` → `12`, `18` → `17` |

- 두 patch 모두 HEAD에 `git apply --check` O. 각각 적용하면 해당 시험 1개만 실패하고 나머지는 통과함을 확인함(B 묶음 해당 파일 기준).
- 보충 patch 적용 시 캡처는 `python build_eval_supplement.py --write` 로 다시 만든다(현재 캡처 `shots/stage3-…png` 는 13칸 기준).

### 8.4 측정 (기준선 9b2e581 → 최종)

| 서식 | 일치율 | 정밀도 | 오검출 | 과대 칸 | 보충 포함 일치율(13칸) | 보충 포함 정밀도(13칸) | 참고: 보충 12칸(patch) 일치율·정밀도 |
|---|---|---|---|---|---|---|---|
| job_application | 80.5% → 80.5% | 100.0% → 100.0% | 0 → 0 | 0 → 0 | 80.5% → 80.5% | 100.0% → 100.0% | 80.5%, 100.0% |
| job_consent | 87.5% → 87.5% | 87.5% → 87.5% | 1 → 1 | 0 → 0 | 87.5% → 87.5% | 87.5% → 87.5% | 87.5%, 87.5% |
| job_interview_confirmation | 100.0% → 100.0% | 35.7% → 29.4% | 9 → 12 | 0 → 0 | 77.8% → 94.4% | 100.0% → 100.0% | 100.0%, 100.0% |
| 서식1 | 95.7% → 98.6% | 98.5% → 98.6% | 1 → 1 | 0 → 0 | 95.7% → 98.6% | 98.5% → 98.6% | 98.6%, 98.6% |
| 서식2·3·4·5 | 100.0% → 100.0% | 100.0% → 100.0% | 0 → 0 | 0 → 0 | 100.0% | 100.0% | 100.0%, 100.0% |
| **전체(micro)** | **92.5% → 93.7%** | **93.0% → 91.4%** | 11 → 14 | 0 → 0 | **90.7% → 93.6%** | **98.7% → 98.8%** | 94.2%, 98.8% |

- 원자료: `measure-final.*`(9b2e581), `measure-decision.*`(HEAD), `measure-decision-supplement-patch.md`(보충 12칸 patch 기준, 참고용).
- 늘어난 칸: 서식1 +2(기간·수령액 계열 라벨), job_interview_confirmation +3(아래 서명줄 회사명·담당자 빈칸, "(서명/인)"). job_interview_confirmation 의 +3 은 수작업 좌표에 없어 원래 열에선 오검출(정밀도 35.7%→29.4%)이지만, 보충 정답 서명줄 3칸과 모두 일치(보충 포함 정밀도 100%).
- 면접일시 칸은 자동 초안이 잡지 않음 → 보충에서 빼면 job_interview_confirmation 보충 포함 일치율 100%.

### 8.5 불변 확인

- 픽셀(110dpi sha256, main 기준): 서식2 radio_text, 서식1·job_consent·job_application □ 체크 4개 모두 O — b532bb1 상태(`pixel/decision1`), HEAD 상태(`pixel/decision2`). `pixel/comparison.json`.
- 종단(Playwright, 격리 서버 `e2e_backend.py --env-file .env`(합성값 덮어씀), 합성 데이터, 영문 파일 이름), `e2e-result-decision.json`·`e2e-submitted-decision.json`:

| 확인 | 결과 |
|---|---|
| 서식2 자동 칸 | 16칸 모두 radio, needs_review 16 |
| 서식5 자동 칸 | check 2·date 3·text 2·signature 1 |
| 확인·공개 | O |
| 1번 "예" 선택 | [예 O, 아니오 X], 화면 ○ 1개 |
| "아니오"로 바꿈 | [예 X, 아니오 O] — "예" 해제, 화면 ○ 1개 |
| 제출 | O |
| 제출 PDF ○ | 서식2 쪽 8개(1번 아니오, 2–8번 예), 채운 □ 0개. 서식5 쪽은 이전 실행들과 같음(곡선 2·채운 표시 34) |
| 캡처 | `shots/decision-04-applicant-picked-first.png`, `shots/decision-05-applicant-switched.png`, `shots/decision-08-submitted-form2.png` |

### 8.6 시험·보호 해시

| 묶음 | 9b2e581 | b532bb1 커밋 전 | 6e3fd63 커밋 전 | 문서 커밋 전 |
|---|---:|---:|---:|---:|
| A 엔진 | 1267 | 1267 | 1267 | 1267 |
| B 백엔드 | 1691 | 1699 | 1705 | 1705 |
| C 시나리오 18개 모듈 | 18/18 | 18/18 | 18/18 | 18/18 |
| D 프런트 tsc·oxlint·build·단위 | 72, 경고 0 | 76, 경고 0 | 76, 경고 0 | 76, 경고 0 |

- 보호 파일 10개 sha256: 각 커밋 전 O(`check_staged.py`). 비밀값 검사 정규식을 지시대로 `sk-[A-Za-z0-9_-]{16,}` 로 바꿈. 사용자 미커밋 파일(task.json, logo.png, 신청자 화면 5개 파일) 스테이지 0.
- 과적합 검사: 9b2e581 이후 draft.py 에 추가한 줄 중 서식 이름·form_no·4자리 이상 숫자 0건.

### 8.7 남은 사람 결정

1. `failed-decision3-bracket.patch` 적용: `test_form_draft_followup.py` 46·49줄 `"(은행명"` → `"은행명"` 수정 허락 여부.
2. `failed-decision2-supplement.patch` 적용: `test_form_draft_eval_supplement.py` 의 `13`→`12`, `18`→`17` 수정 허락 여부, 그리고 보충 12칸 캡처 확인.
3. job_interview_confirmation 아래 서명줄 3칸(회사명·담당자·(서명/인))을 수작업 좌표에 넣을지(지금은 원래 열에서 오검출로 셈).
