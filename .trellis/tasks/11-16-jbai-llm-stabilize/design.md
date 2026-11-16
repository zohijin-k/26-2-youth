# 설계 — JBAI LLM 안정화

요구사항과 완료 기준은 `prd.md`, 현재 코드의 근거는 `research/current-state.md`에 있다.

## 1. 경계

| 구분 | 파일 |
|---|---|
| 바뀜 | `demo/backend/notice_llm.py`, `demo/backend/llm_drafts.py`(실패 분류 기록만), `demo/backend/tools/probe_jbai_notice.py`, 위 모듈의 시험, `docs/DEVELOPMENT.md`·`README.md`·`demo/README.md`의 해당 문단, `.env.example`, `.trellis/spec/backend/notice-drafts.md` |
| 안 바뀜 | `notice_analysis.py`(규칙 추출), `api/program_analysis.py`(호출 지점), `api/draft_messages.py`, 프런트 전체, DB 모델, 판정 규칙 |

분석 API의 응답 모양(`notice_draft`의 키)은 그대로라 프런트는 영향이 없다.

## 2. 호출 흐름

```
enrich_notice(draft, supplemental)
  payload = notice_payload(...)                 # 그대로: 공개 글자만, 20만 자 상한
  content = provider.generate('notice_analysis', payload)
      safe  = notice_payload(...)               # 그대로: 전송 경계에서 다시 투영
      sent  = _send_window(safe, 입력 상한)       # 새: 모델에 보내는 글자 상한
      deadline = clock() + 총 예산
      for mode in [기본 방식, 대체 방식]:          # 최대 2회 (현행 유지)
          remaining = deadline - clock()
          두 번째 호출인데 remaining < 최소 시간  → budget_exhausted 기록 후 중단
          outcome, content = _call(mode, timeout=min(30, remaining))
          기록(outcome)
          outcome == ok → content 반환
  body = _response(content)                     # 새: 관대 해석 + 정규화
  안내문: guidance_check → 채택 또는 탈락 사유
  기준:  values_match → 통과 또는 버림
  기록(검증 요약)
```

`enrich_notice`의 서명과 반환 모양, `DraftProvider` 프로토콜(`generate(purpose, payload) -> str | None`)은 바꾸지 않는다. 가짜 공급자를 쓰는 기존 시험이 그대로 동작해야 한다.

## 3. 계약

### 3.1 호출 결과 어휘

| 값 | 판단 근거 (예외 타입·상태 코드·응답 구조만 사용) |
|---|---|
| `ok` | 본문이 문자열이고 3.3의 해석에 성공 |
| `timeout` | `TimeoutError`, `socket.timeout`, 또는 `URLError.reason`이 그 둘 |
| `http_429` / `http_4xx` / `http_5xx` | `HTTPError.code` |
| `network` | 그 밖의 `URLError`, `OSError` |
| `bad_transport` | transport가 낸 `ValueError`(JSON 아님, 객체 아님, 응답 과대) |
| `no_content` | `choices[0].message.content`가 없거나 빈 문자열 |
| `truncated` | `choices[0].finish_reason == 'length'` |
| `too_large` | 본문이 `MAX_RESPONSE`(32,000자) 초과 |
| `bad_shape` | 3.3의 해석 실패 |
| `budget_exhausted` | 남은 예산이 부족해 두 번째 호출을 하지 않음 |

기록은 로거 `demo.backend.llm`에 한 줄씩 남긴다.

```
llm_call purpose=notice_analysis mode=json_object attempt=1 outcome=timeout seconds=30.0
llm_result purpose=notice_analysis guidance=accepted criteria_received=4 criteria_accepted=3
```

- `ok`와 `llm_result`는 INFO, 나머지는 WARNING. 앱 로거에 핸들러가 없어도 WARNING은 stderr에 보인다(W8).
- 줄에 들어가는 값은 위 어휘, 고정 문자열, 숫자뿐이다. `exc_info`, 예외 문구, 주소, 모델 이름, 키, 본문은 쓰지 않는다.
- `guidance` 값: `accepted`, `none`(모델이 안 줌), `shape`, `quote`, `number`, `promise`, `length`.
- `llm_drafts.JbaiProvider`는 같은 분류 함수로 `llm_call purpose=guidance|review …`만 남기고 동작은 그대로 둔다(제한 10초, 1회).

### 3.2 시간 예산

- 첫 호출 제한 30초는 유지한다(기존 시험이 고정).
- 총 예산 기본 40초, 두 번째 호출 최소 8초. 두 번째 호출의 제한은 `min(30, 남은 예산)`.
- 최악: 첫 호출이 30초에 시간 초과 → 남은 10초로 대체 방식 호출 → 합계 40초. 지금은 60초다.
- 설정 `JBAI_LLM_BUDGET_SEC`(선택, 5~120초, 벗어나면 기본값). 실측에서 정상 응답이 10초 안쪽이면 기본값을 25초로 낮춘다.
- 시계는 공급자의 `clock` 필드(`time.monotonic` 기본)로 주입해 가짜 시계로 시험한다.

### 3.3 응답 해석 (`_response`)

1. 문자열이고 `MAX_RESPONSE` 이하.
2. 앞뒤 공백 제거. 맨 앞의 `<think>…</think>` 블록 제거. 전체를 감싼 코드 블록(```` ``` ```` 또는 ```` ```json ````) 한 겹 제거.
3. JSON으로 읽는다. 실패하면 첫 `{`부터 마지막 `}`까지를 한 번 더 시도한다. `NaN`·`Infinity`는 지금처럼 거부.
4. 객체여야 하고 `guidance`와 `criteria` 키가 둘 다 있어야 하며 `criteria`는 목록이어야 한다. 그 밖의 최상위 키는 무시한다. 따라서 `{}`는 지금처럼 쓸 수 없는 응답이다.
5. `guidance`: `null`이거나, `text`(문자열)·`page`·`quote`를 가진 객체. 세 키만 남긴다. 모양이 틀리면 안내문만 버린다.
6. `criteria`: 앞에서 50개까지. 항목은 `type`이 허용 종류, `quote`가 문자열, `page`가 정수 또는 `null`, `values_json`이 문자열 또는 객체(객체면 직렬화)여야 한다. 네 키만 남긴다. 틀린 항목은 그 항목만 버린다.

해석에 성공하면 안내문이나 제안이 하나도 남지 않아도 `ok`다(대체 호출 없음). 내용 검증(`_quote_valid`, 숫자·약속 검사, 3.4)은 해석과 별개로 그대로 적용한다.

### 3.4 기준 제안의 값 일치 (`values_match(candidate, values)`)

선행 조건은 지금과 같다: 종류가 같고, 후보에 `engine_rule`이 있고, 쪽이 같고, 인용이 서로 포함 관계다.

| 종류 | 핵심 값 묶음 (하나의 묶음이 빠짐없이 있어야 함) |
|---|---|
| age | `min_age`+`max_age`, 또는 `birth_start`+`birth_end` |
| residence | `province` |
| issue_date | `date` |
| income | `percent` |
| work_continuity | `months` |

규칙:

1. 모델이 쓴 키는 모두 후보의 `values`에 있어야 한다. 없는 키가 하나라도 있으면 불일치.
2. 모델이 쓴 값은 모두 후보의 같은 키 값과 같아야 한다(정규화 후 비교). 하나라도 다르면 불일치.
3. 그 종류의 핵심 값 묶음 중 하나가 빠짐없이 들어 있어야 한다.

정규화: 정수 키는 정수 또는 숫자 문자열(불리언 제외), `percent`는 수로 비교(140 = 140.0), 날짜 키는 `YYYY-MM-DD`와 `YYYY.M.D`·`YYYY년 M월 D일` 표기를 ISO로, `province`는 추출기와 같은 별칭 표(전북·전라북도 → 전북특별자치도), 그 밖의 문자열은 앞뒤 공백 제거.

결과:

| 모델의 값 (후보: 나이 18~39) | 지금 | 새 규칙 |
|---|---|---|
| 후보와 완전히 같은 값 | 통과 | 통과 |
| `{"min_age": 18, "max_age": 39}` | 버림 | **통과** |
| `{"min_age": 17, …}` (충돌) | 버림 | 버림 |
| 후보에 없는 키 포함 | 버림 | 버림 |
| `{"basis_date": …}`만 (핵심 값 없음) | 버림 | 버림 |

통과한 제안에 실리는 값은 지금처럼 후보의 값을 복사한 것이다. 모델의 값이 화면이나 규칙에 들어가지 않는다. 확인 도구의 `_value_matches`도 이 함수를 쓴다.

### 3.5 프롬프트

시스템 지시에 고정 문구를 더한다. 규칙 후보나 그 값은 넣지 않는다(공급자에게 가는 자료는 여전히 공고문 글자와 부가 설명문뿐).

- 종류별 `values_json` 키: age → `min_age`, `max_age`(정수) 또는 `birth_start`, `birth_end`(YYYY-MM-DD) / residence → `province` / issue_date → `date` / income → `percent`, `operator` / work_continuity → `months`(1년은 12).
- 문장에 직접 적힌 값만 쓰고 기준일처럼 계산이나 다른 줄 참조가 필요한 값은 쓰지 않는다.
- 안내문은 1,200자 이내(로컬 상한 4,000자는 유지).

실측에서 탈락 사유가 한쪽으로 몰리면 그 사유에 맞춰 문구를 조정한다. 조정은 실측 근거와 함께 기록한다.

### 3.6 입력·출력 길이

- 보내는 공고문 글자 상한을 공급자 쪽에 둔다(`_send_window`). 쪽 순서대로 채우다가 상한에서 자른다. 초안 30,000자, 설정 `JBAI_LLM_MAX_INPUT_CHARS`(선택). 최종 기본값은 긴 합성 공고문 실측 1~2회로 정한다.
- 로컬 검증은 전체 공고문 글자를 기준으로 하므로, 보낸 범위 안의 인용은 그대로 유효하다. `notice_payload`의 20만 자 상한과 그 시험은 그대로 둔다.
- `finish_reason == 'length'`는 `truncated`로 분류하고 대체 방식으로 넘어간다.

### 3.7 확인 도구 (`probe_jbai_notice.py`)

- 값 판정과 항목 모양 판정을 `notice_llm`의 함수로 통일한다.
- 선택 옵션 `--long`: 긴 합성 공고문 1건을 한 번 보내 상태와 시간만 기록한다(입력 상한 확인용).
- 출력에 키·주소·모델 이름·본문이 없다는 기존 보장과 시험은 유지한다.

## 4. 호환성

- 새 설정 두 개는 모두 선택이고 비우면 기본값이다. 기존 설정 이름과 의미는 그대로다.
- 의도적으로 바뀌는 시험 기대값은 두 곳이다(`research/current-state.md` 5절). 구현 전에 `changed-test-expectations.md`에 이유와 함께 적고, 그 밖의 기존 기대값은 건드리지 않는다.
- 저장된 과거 초안(`notice_draft`)의 모양은 바뀌지 않는다.

## 5. 선택과 이유

- **항목별로 버리기** — 한 항목의 오류로 안내문까지 버리던 것을 없앤다. 내용 검증은 그대로라 화면에 들어가는 내용의 기준은 낮아지지 않는다.
- **같은 방식 재시도 없음** — 지금도 실패하면 다른 방식으로 한 번 더 묻는다. 여기에 재시도를 더하면 호출 수와 대기 시간만 늘어난다. 대신 총 예산으로 최악 대기를 줄인다.
- **값은 "직접 적힌 값"만 비교** — 모델이 계산값을 맞출 수 없다는 것이 기존 실패의 원인이다. 인용만으로 연결하는 대안은 값이 충돌해도 통과시킬 수 있어 택하지 않는다.
- **실패 기록은 WARNING** — 로그 설정을 새로 넣지 않고도 기본 실행에서 원인이 보인다.

## 6. 구현 후 달라진 점 (2026-11-16)

- **총 예산 기본값은 40초로 유지했다.** 3.2에서는 정상 응답이 10초 안쪽이면 25초로 낮춘다고 적었고 실측은 그 조건을 충족했다(최대 8.7초). 그런데 기본값을 25초로 낮추면 첫 호출 제한이 25초가 되어 "첫 호출 30초"를 고정한 기존 시험 두 곳을 바꿔야 한다. 기존 기대값은 필요한 곳만 바꾼다는 원칙을 따라 기본값은 뒀다. 이후 실제 공고문 측정(2026-11-17)에서 응답이 최대 21.6초였으므로 40초가 맞는 값이다. 시연 설정으로 25초를 권고했던 것은 철회한다.
- **의도적으로 바꾼 기존 시험은 3곳이다.** 계획의 2곳에 더해, 확인 도구 시험이 "코드 블록으로 감싼 정상 응답"을 쓸 수 없는 응답의 예로 쓰던 곳이 3.3의 직접 결과로 바뀌었다(`changed-test-expectations.md`).
- **배열로 감싼 응답(`[ {...} ]`)도 읽힌다.** 3.3의 "첫 `{`부터 마지막 `}`까지" 규칙의 결과다. 내용 검증은 같다.
- **작업 전 수치는 안내문과 기준 제안을 나눠 세지 못한다.** 바꾸기 전 확인 도구에는 구분이 없다. 작업 후 수치는 새 기록 줄(`llm_result`)로 나눠 셌다.
- **실패 기록의 `seconds`는 그 호출 한 번의 시간이다.** `budget_exhausted`는 호출하지 않았으므로 0.0이다.

## 7. 되돌리기

- 단계마다 커밋을 나눈다(기록 / 해석 / 값 일치·프롬프트 / 예산·길이 / 도구 / 문서). 문제가 생긴 단계만 되돌릴 수 있다.
- 운영 중 문제는 `LLM_PROVIDER=none`으로 즉시 끈다. 꺼진 상태의 동작은 이 작업으로 바뀌지 않는다.
