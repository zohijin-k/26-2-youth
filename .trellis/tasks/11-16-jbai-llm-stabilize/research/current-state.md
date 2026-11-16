# 현재 상태 조사 (2026-11-16, main 7802bd1 기준)

코드와 기록을 읽어 확인한 사실만 적는다. 실제 호출은 하지 않았다.

## 1. LLM이 연결된 곳

| 기능 | 진입점 | 구현 | 켜는 설정 |
|---|---|---|---|
| 공고문 분석: 안내문 초안 작성 + 기준 제안 | `POST /api/officer/programs/analyze` (`api/program_analysis.py:359`, 호출은 369줄) | `notice_llm.py` `enrich_notice` → `JbaiNoticeProvider.generate` | `LLM_PROVIDER=jbai`, `JBAI_BASE_URL`(https 필수), `JBAI_API_KEY`, `JBAI_TEXT_MODEL`, 선택 `JBAI_RESPONSE_FORMAT` |
| 안내 메시지 초안 버튼 | `POST …/workspace/guidance-draft` (`api/draft_messages.py:10`) | `llm_drafts.py` `draft_guidance` → `JbaiProvider.generate` | `PROGRAM_LLM_PROVIDER=jbai` + `PROGRAM_LLM_ENABLED=true`, 선택 `JBAI_LLM_MODEL` |
| 심사 사유 설명 | `GET …/reason-explanation` (`api/draft_messages.py:28`) | `llm_drafts.py` `draft_review` | 위와 같음 |

- 기본값은 모두 꺼짐. 꺼져 있으면 외부 호출 0. 실패하면 규칙 초안(또는 고정 문구)으로 돌아간다.
- 전북AI OCR(`ocr/jbai.py`, `engine_v2/pipeline/jbai_ocr.py`)은 `JBAI_API_KEY`와 `JBAI_ALLOW_REAL_DOCS`가 모두 있을 때만 켜진다. 이 태스크 범위 밖이며 `JBAI_ALLOW_REAL_DOCS`는 비워 둔다.
- 주소와 모델 이름의 출처: 기본 주소 `https://ai.jb.go.kr/open-api/v1`(`engine_v2/pipeline/jbai_ocr.py:36`, `.env.example` 4줄), 모델 `MainModel`(`docs/DEVELOPMENT.md:188` — 2026-11-16 `/open-api/v1/chat/completions` HTTP 200 확인 기록).

## 2. 실측 기록 (`.trellis/tasks/11-16-jbai-schema-check/report.md`, 실제 호출 11회)

- 요청 방식별: `json_schema` 3회 중 2회 시간 초과(당시 호출 제한 10초), `json_object` 7회 중 6회 정상(2.87~4.72초)·1회 시간 초과, `prompt` 1회 정상.
- 기준 제안: 받은 제안이 거의 전부 "값 불일치"로 버려짐. 공고문당 평균 통과 A 0.0 / B 0.0 / C 0.5. 인용 불일치 0, 종류 밖 0.
- 검증에서 탈락한 내용이 화면에 들어간 경우 0.
- 결론: "끄고 시연" 권고.
- 그 뒤 PR #13(25cb50a)에서 바뀐 것: 안내문을 LLM이 직접 작성(`ai_drafted`), 기본 방식 `json_object`, 호출 제한 30초. 이 경로는 가짜 공급자로만 검증됐고 실제 모델 실측 기록이 없다.

## 3. 코드에서 확인한 약점

| # | 내용 | 위치 |
|---|---|---|
| W1 | 모든 예외를 삼키고 원인을 남기지 않는다. 시간 초과·HTTP 오류·형식 오류·검증 탈락을 구분할 수 없다 | `notice_llm.py:159`, `notice_llm.py:277`, `llm_drafts.py:163` |
| W2 | 재시도는 "다음 방식으로 한 번"뿐이고 호출마다 30초라 분석 요청이 최악 60초 멈춘다. 전체 시간 상한이 없다 | `notice_llm.py:25`, `notice_llm.py:151-167`, `api/program_analysis.py:369` |
| W3 | 응답 해석이 엄격하다. 최상위·항목의 키 집합이 정확히 같아야 하고, 코드 블록이나 앞뒤 설명이 붙으면 전체를 버린다. 항목 하나가 틀려도 안내문까지 버린다 | `notice_llm.py:228-257` |
| W4 | 기준 제안의 값 비교가 전체 일치다. 모델은 추출기의 계산값(`basis_date`, `birth_start`, `birth_end`)과 키 이름을 알 수 없고, `140`과 `140.0`도 다르게 본다 | `notice_llm.py:294-306`, `notice_llm.py:236-240` |
| W5 | 공고문을 최대 20만 자까지 그대로 보낸다. 모델 문맥 한도 확인이 없다 | `notice_llm.py:21`, `notice_llm.py:67-89` |
| W6 | `max_tokens` 4000 고정이고 잘린 응답(`finish_reason`)을 확인하지 않는다. 안내문 길이를 프롬프트에서 제한하지 않는다(로컬 상한 4,000자) | `notice_llm.py:132`, `notice_llm.py:24` |
| W7 | 공급자 구현이 두 벌이다. 제한 시간(10초/30초), temperature(0.1/0), 설정 이름이 다르다 | `llm_drafts.py:121-169`, `notice_llm.py:113-170` |
| W8 | 앱 로거에 핸들러가 없어 INFO 기록은 기본 실행에서 보이지 않는다(경고 이상만 stderr) | `demo/backend` 전체에 `logging.basicConfig` 없음 |

## 4. 추출기가 만드는 기준 후보의 값 모양 (`notice_analysis.py:276-361`)

| 종류 | 값 | 문장에 직접 적힌 값 |
|---|---|---|
| age (세 표기) | `min_age`, `max_age`, `basis_date`, `birth_start`, `birth_end` | `min_age`, `max_age` |
| age (출생일 범위) | `birth_start`, `birth_end`, `basis_date` | `birth_start`, `birth_end` |
| residence | `province`(전북·전라북도 → 전북특별자치도로 정규화), `city`, `basis_date` | `province` |
| issue_date | `mode`, `date`, `basis_date` | `date` (문장에 날짜가 있을 때) |
| income | `percent`(float), `operator`, `household_table` | `percent`, `operator` |
| work_continuity | `months`, `basis_date` | `months` |

제안이 붙을 수 있는 후보는 `engine_rule`이 있는 자동 후보뿐이다(체크리스트 후보는 대상 아님).

## 5. 이 작업이 건드리는 기존 시험 계약

- `tests/test_notice_llm.py`(19), `test_notice_llm_formats.py`(9, 매개변수 전개 38), `test_probe_jbai_notice.py`(10), `test_llm_drafts.py`(11), `test_draft_messages_api.py`(2). 모두 가짜 transport.
- 유지해야 하는 계약: 첫 호출 제한 30초(`test_notice_llm.py:107`, `test_notice_llm_formats.py:71`), 대체는 정확히 한 번(`test_notice_llm_formats.py:85-102`), `{}`·코드 블록 속 `{}`는 쓸 수 없는 응답(`test_notice_llm.py:125`, `test_notice_llm_formats.py:81`), 충돌하는 값·모르는 키·무관한 인용은 제안 불가(`test_notice_llm.py:135-142`), 공급자에게 가는 것은 공고문 글자와 부가 설명문뿐(`test_notice_llm.py:79-92`), 예외 문구·키가 로그에 없음(`test_notice_llm.py:181-195`).
- 의도적으로 바뀌는 기대값(값 일치 규칙 변경의 직접 결과):
  1. `test_notice_llm_formats.py:114` — `{'min_age': 18, 'max_age': 39}`(직접 적힌 값만 보낸 제안)를 "버림"으로 기대. 새 규칙에서는 통과.
  2. `test_probe_jbai_notice.py:105-111` — `{'province': '전북'}` 제안을 값 불일치로 집계. 새 규칙에서는 정규화 후 일치.

## 6. 이 PC에서 확인되지 않은 것

- 저장소 문서의 전체 시험 수치는 macOS·WSL2 측정값이다. Windows 네이티브에서 전체 게이트가 통과하는지 기록이 없다. 변경 전에 같은 PC에서 기준 결과를 먼저 잡아야 한다.
- 시스템 Python 3.13에 `fastapi`, `pymupdf`, `python-dotenv`가 있어 확인 도구는 실행 가능하다.
- `.env`: `JBAI_BASE_URL`, `JBAI_TEXT_MODEL`은 채움(2026-11-16). `JBAI_API_KEY`는 비어 있다(팀장이 직접 입력).
