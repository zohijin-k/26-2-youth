# 작업 메모 (11-16-form-draft-followup)

- 시작: 2026-11-16, main c8161f4 → feat/form-draft-followup. `df -h /` 여유 33Gi(15GB 이상). `gate/disk-start.txt`.
- 커밋 제외 유지: .trellis/tasks/11-14-renewal-applicant-design/task.json, logo.png, 그리고 시작 시점부터 미커밋이던 신청자 화면 5개 파일(FinalCheck.tsx, MyPage.tsx, SubsidyItems.tsx, document-upload.css, subsidy-items.css). 모두 `git add` 대상에서 뺌.
- 게이트: 이전 작업 run_gate.py 복사, 임시 경로 접두사만 form-draft-followup, 백엔드 최소 통과 수 1676(이전 최종값).
- 기준선 게이트: A1267 / B1676 / C18 / D72 통과. 기준선 백엔드 수집 직후 1분 미만 동안 1단계 편집본(draft.py·render.py)이 작업 트리에 있었음 → 바로 patch로 빼고 되돌림. 기준선 B 1676 통과는 원래 코드 기준(편집본이었다면 inline 시험 3개가 실패했어야 함).
- 픽셀 비교: `pixel_render.py`로 서식2(radio_text)·서식1/job_consent/job_application(□ 체크)를 110dpi PNG로 렌더링해 sha256 비교. `pixel/before`(main) 기준.

## 1단계 실패 (failed-stage1.patch)

- 구현 완료: 규칙 a 칸 → `field_type "radio"`, 같은 group, `choice_mark: "circle"`; render.py 타원 표시; validate_layout 이 `choice_mark`("circle"만, check/radio에만) 보존; 신청자 layout 공개 속성에 `choice_mark`; PdfFormsWorkspace 타원 SVG, 토글·필수 판정을 `src/lib/form-choice.ts`로 분리.
- 새 시험: 백엔드 `test_form_choice_marks.py` 8개 통과(초안·렌더·필수 group 차단·바꾸기 시 다른 쪽 해제·제출 PDF 타원 1개), 프런트 `tests/form-choice.test.ts` 4개 통과, tsc·oxlint·build 경고 0.
- 픽셀: patch 적용 상태에서 4개 렌더 모두 main 과 sha256 동일(`pixel/stage1-patch`).
- 실패 원인: 기존 `test_form_draft_inline.py` 가 규칙 a 칸을 `field_type == "check"` 로 찾음. 지시(radio)와 정면 충돌.
  - 실패: `test_choice_word_pair_becomes_grouped_word_checks_without_comma`, `test_multi_word_choice_pairs_are_joined`, `test_dense_vector_page_drafts_under_two_seconds`.
  - 의미가 약해지는 것: `test_choice_word_inside_sentence_is_not_a_check`, `test_choice_header_split_by_cell_border_is_not_a_word_pair` (radio 로 바뀌면 빈 목록이 그냥 통과).
  - 필요한 수정(적용 안 함): 위 5개 시험의 찾는 조건 1줄씩만 `"check"` → `"radio"`(부정 시험 2개는 `in ("check", "radio")`). 라벨·group·쉼표 제외·신뢰도 0.6·type "check" 기대값은 그대로.
  - 기존 시험 수정이 금지되어 있고 자동 승인 분류기도 이 수정을 막음 → 지시대로 patch 로 빼고 되돌림. 사람 결정 필요(보고서 7절).
- patch 적용 방법: `git apply .trellis/tasks/11-16-form-draft-followup/failed-stage1.patch` + 위 5줄 시험 수정.

## 2단계

- 라벨 어휘 10개(지시 목록)만 추가, `_AUTOFILL` 은 그대로. 여는 괄호로 시작하는 라벨("(은행명 :")을 인정하도록 `_label_at` 에서 앞 괄호만 무시.
- 점 날짜: 2·4자리 숫자 토큰 + 맨 "." 토큰들, 모든 틈이 줄 높이 이상일 때만. 합성 글꼴(korea)은 글자 폭이 넓어 "2026." 이 55pt 를 차지함 → 시험 좌표를 그에 맞춤(규칙 수정 아님).
- 단어 안 상자: 단어 첫 글자가 상자면 기존 위치·폭 그대로, 그 밖의 상자 글자만 rawdict 글자 상자 위치로.
- docstring 의 "2026." 예시가 4자리 숫자 검사에 걸려 "YYYY." 로 바꿈(주석만, 관련 시험 47개 재확인 후 커밋).

## 3단계

- 보충 좌표는 `build_eval_supplement.py` 로 괘선·글자 위치에서 계산. 처음엔 기업 작성란·날짜 10칸이었으나 캡처에서 아래 서명줄(회사명/담당자/(서명/인))도 실제 빈칸이라 3칸 추가(13칸). 보충 포함 수치를 부풀리지 않으려는 것.
- "연락처"·"담당자" 가 서식 안에 두 번씩 나와, 라벨 찾기를 면접기업/면접현황 머리 칸 범위로 제한.

## 4단계

- 서버: `uvicorn e2e_backend:app --app-dir <task> --port 8031 --env-file .env` + `VITE_API_TARGET=http://127.0.0.1:8031 vite --port 5191`. DB·저장소는 /tmp/form-draft-followup-e2e, 담당자 비밀번호·세션 비밀은 합성값, API 키 제거.
- 종단 2회: 커밋 코드(현재 동작 기록), 1단계 patch 를 작업 트리에 잠시 적용(커밋 안 함) → 끝난 뒤 `git apply -R` 로 되돌리고 /tmp/form-draft-followup-e2e·로그 삭제, 포트 닫힘 확인.
- Playwright 는 /tmp/renewal-npm-cache 의 기존 패키지 사용(새 설치 없음).
