# 실행 계획 — JBAI LLM 안정화

브랜치 `feat/jbai-llm-stabilize`(main 7802bd1에서 분기). 명령은 저장소 루트에서 실행한다. Windows Git Bash에서는 앞에 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`을 붙인다.

이 세션은 상위 폴더에서 시작해 Trellis 하위 에이전트(`trellis-implement`, `trellis-check`)가 없다. 그래서 인라인 흐름을 쓴다: `trellis-before-dev` → 구현 → `trellis-check` → `trellis-update-spec`.

## 검토 관문

- **G0** 이 계획 승인 → `task.py start 11-16-jbai-llm-stabilize`. 그 전에는 제품 코드를 고치지 않는다.
- **G1** 실제 호출은 매 묶음마다 팀장 승인 후 실행한다. 키는 팀장이 `.env`에 직접 넣고, 값은 읽거나 출력하지 않는다.
- **G2** 의도적으로 바꾸는 기대값은 시험을 고치기 전에 `changed-test-expectations.md`에 먼저 적는다.
- **G3** 커밋·push·PR은 팀장이 요청할 때만 한다.

## 순서

### 0. 준비
- [x] `trellis-before-dev`로 백엔드 규격 다시 읽기 (`notice-drafts.md` 포함)
- [x] 변경 전 기준 결과 잡기(이 PC): 관련 시험 6개 파일, 엔진 전체, 백엔드 전체, 시나리오 18개. 결과를 `gate-before.md`에 기록

### 1. 기준선 실측 (G1, 키 필요 — 늦어지면 2~6단계를 먼저 하고 main 작업 사본에서 잰다)
- [x] `python -m demo.backend.tools.probe_jbai_notice --mode json_object --repeats 4 --max-calls 12 --json` → `measure-before.json` (12회)
- [x] 작업 전 수치는 main 작업 사본(`git worktree`)에서 `--env-file <저장소>/.env`로 측정(3회 + 9회)

### 2. 실패 분류 기록 (R1)
- [x] 시험 먼저: 예외 종류별 어휘, 로그에 비밀값·예외 문구 없음, 정상 호출은 INFO
- [x] `llm_drafts.py`에 분류 함수와 기록 함수, `notice_llm.py`·`llm_drafts.py`의 호출부에 적용
- [x] `enrich_notice`에 검증 요약 기록, `guidance_text`의 탈락 사유 분리(기존 함수 서명 유지)

### 3. 응답 해석 관대화 (R3)
- [x] 시험 먼저: 코드 블록, 앞뒤 설명, `<think>`, 여분 키, 항목 하나 오류, `values_json` 객체, `{}`는 여전히 실패
- [x] `_response` 재작성(design 3.3)

### 4. 값 일치 규칙과 프롬프트 (R4, R5)
- [x] G2: `changed-test-expectations.md` 작성(2곳)
- [x] 시험 먼저: 종류별 통과·버림 표, 정규화, 충돌·모르는 키·핵심 값 누락
- [x] `values_match` 추가, `enrich_notice`와 확인 도구에 적용
- [x] 시스템 지시에 키 안내·계산값 금지·안내문 길이 추가. 프롬프트에 후보 값이 없다는 시험 유지

### 5. 시간 예산과 길이 (R2, R6)
- [x] 시험 먼저(가짜 시계): 최악 40초, 예산 부족 시 두 번째 호출 생략, 설정값 범위, 잘린 응답, 입력 상한
- [x] 예산·`_send_window`·`finish_reason` 구현, `.env.example`에 선택 설정 2개

### 6. 확인 도구 (design 3.7)
- [x] 판정 함수 통일, `--long` 옵션, 도구 시험 갱신

### 7. 전체 점검
- [x] 0단계와 같은 게이트 재실행 → `gate-after.md`. 차이는 `changed-test-expectations.md`의 목록과 같아야 한다
- [x] `git diff --stat main -- demo/frontend` 가 비어 있는지, 보호 파일 10개 해시 확인
- [x] `trellis-check`

### 8. 작업 후 실측 (G1)
- [x] 1단계와 같은 명령 → `measure-after.json` (12회), `--long` 1~2회
- [x] 전후 비교표와 AC1~AC5 판정을 `report.md`에 기록
- [x] 탈락 사유가 한쪽으로 몰리면 프롬프트 조정 — 해당 없음(완료 기준 충족, 재실측 안 함)

### 9. 문서와 규격 (R8)
- [x] `docs/DEVELOPMENT.md`, `README.md`, `demo/README.md`의 해당 문단, `.env.example`
- [x] `trellis-update-spec`: `.trellis/spec/backend/notice-drafts.md`(값 일치 규칙, 해석, 예산, 기록 어휘)
- [x] `report.md`에 시연 권고(켬/끔)와 근거

## 검증 명령

```bash
# 관련 시험
python -m pytest demo/backend/tests/test_notice_llm.py demo/backend/tests/test_notice_llm_formats.py \
  demo/backend/tests/test_probe_jbai_notice.py demo/backend/tests/test_llm_drafts.py \
  demo/backend/tests/test_draft_messages_api.py demo/backend/tests/test_program_analysis.py -q

# 전체 (백엔드 전체는 임시 파일 약 5GB)
python -m pytest engine_v2/tests -q
python -m pytest demo/backend/tests -q
for f in demo/backend/tests/run_p*_scenarios.py; do python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"; done
```

## 위험한 지점

- `tests/test_notice_llm_formats.py:85-102` — "대체는 정확히 한 번" 계약. 예산 로직이 호출 순서를 바꾸면 안 된다.
- `tests/test_notice_llm.py:107`, `test_notice_llm_formats.py:71` — 첫 호출 제한 30초 고정.
- `tools/probe_jbai_notice.py`의 `screen_violations` — 화면에 들어간 내용을 다시 검증하는 안전망. 판정 함수를 바꿔도 이 검사는 약해지면 안 된다.
- 실제 호출 한도: 도구 한 번에 최대 15회. 이 태스크 전체에서 약 24~30회(재실측 포함 최대 42회)로 잡는다.
- Windows에서 시나리오 모듈이 임시 폴더 정리(`WinError 32`)로 종료 코드 1을 낼 수 있다. 변경 전 기준 결과와 비교해 구분한다.
