# 실행 계획 — AI 참고 제안

브랜치 `feat/ai-reference-suggestions`(`feat/jbai-llm-stabilize` 90a6911에서 분기). 명령은 저장소 루트에서 실행하고, Windows Git Bash에서는 앞에 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`을 붙인다. 이 세션에는 Trellis 하위 에이전트가 없어 인라인 흐름(`trellis-before-dev` → 구현 → `trellis-check` → `trellis-update-spec`)을 쓴다.

## 검토 관문

- **G0** 이 계획 승인 → `task.py start 11-17-ai-reference-suggestions`. 그 전에는 제품 코드를 고치지 않는다.
- **G1** 실제 호출은 묶음마다 팀장 승인 후 실행한다(실제 공고문 9회, 합성 6회, 화면 확인 1회).
- **G2** 의도적으로 바꾸는 기대값은 시험을 고치기 전에 `changed-test-expectations.md`에 적는다.
- **G3** 커밋·push·PR은 팀장이 한다.

## 순서

### 0. 준비
- [x] `trellis-before-dev`: 백엔드 `notice-drafts.md`, 프런트 `index.md`·`program-authoring.md`·`officer-modern-design.md`
- [x] 변경 전 기준: LLM 관련 시험 7개 파일(264 통과가 기준), 프런트 `tsc`·`oxlint`·빌드·단위 시험

### 1. 백엔드: 참고 제안 (R1~R4, R6)
- [x] G2: `changed-test-expectations.md`
- [x] 시험 먼저: 종류별 `stated_values` 통과·버림 표, 대상 후보 고르기, 자동 후보가 있는 문장, 추출기 값과 충돌, 후보 없는 문장, `criteria` 불변, 중복 제거, 기록 줄
- [x] `notice_llm.py`: `stated_values`, `reference_for`, `enrich_notice` 연결, `llm_result` 줄에 `criteria_reference`
- [x] 실제 공고문에서 본 문장 모양 4개(`research/findings.md`)를 시험 자료로 사용(공개 공고문의 문장)

### 2. 확인 도구 (R6)
- [x] 시험 먼저: 참고 제안이 통과로 집계됨, 화면 위반 검사가 조작된 참고 제안을 잡음
- [x] `probe_jbai_notice.py`: `classify`, `run_once`, `screen_violations`

### 3. 프런트 (R5)
- [x] 단위 시험 먼저: `suggestionPresentation`의 두 경우
- [x] 타입, 표시 함수, 카드 수정
- [x] `npx tsc -b && npx oxlint && npx vite build`, 단위 시험

### 4. 전체 점검
- [x] LLM 관련 시험, 엔진·백엔드·시나리오 게이트(이 PC의 변경 전 기준과 실패 목록 비교)
- [x] `git diff --stat` 로 보호 파일 10개 변경 0 확인
- [x] `trellis-check`

### 5. 실측 (G1)
- [x] 실제 공고문 3종 × 3회 → `measure-real-notices.json`
- [x] 합성 공고문 3종 × 2회(`probe_jbai_notice --mode json_object --repeats 2 --max-calls 6`) → 기준 제안 통과 유지 확인
- [x] 격리 서버에서 실제 공고문 1건을 올려 화면 확인

### 6. 문서와 규격 (R8)
- [x] `trellis-update-spec`: `notice-drafts.md`의 "notice provider stability" 장면에 참고 제안 계약 추가
- [x] `docs/DEVELOPMENT.md`의 실제 공고문 문단 갱신
- [x] `report.md`: 실측 표, 완료 기준 판정, 계획과 달라진 점

## 검증 명령

```bash
python -m pytest demo/backend/tests/test_notice_llm_stability.py demo/backend/tests/test_notice_llm.py \
  demo/backend/tests/test_notice_llm_formats.py demo/backend/tests/test_probe_jbai_notice.py \
  demo/backend/tests/test_llm_drafts.py demo/backend/tests/test_draft_messages_api.py \
  demo/backend/tests/test_program_analysis.py -q

cd demo/frontend && npx tsc -b && npx oxlint && npx vite build
node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts
```

## 위험한 지점

- `enrich_notice`의 제안 루프: 자동 후보 경로의 결과가 한 건도 달라지면 안 된다. 기존 시험 264개가 안전망이다.
- 숫자 확인: `18`이 `2018`이나 `180`의 일부로 잡히면 안 된다(독립된 숫자만).
- 날짜 확인: 두 자리 연도(`'26. 3. 3.`)는 2000년대로만 읽는다.
- 프런트 카드: `text`가 있는 옛 안내문 제안 경로를 건드리지 않는다.
