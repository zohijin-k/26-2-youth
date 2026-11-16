# 설계 — AI 참고 제안

요구사항은 `prd.md`, 코드 근거는 `research/findings.md`에 있다.

## 1. 경계

| 구분 | 파일 |
|---|---|
| 바뀜 (백엔드) | `demo/backend/notice_llm.py`, `demo/backend/tools/probe_jbai_notice.py`, 두 모듈의 시험 |
| 바뀜 (프런트) | `demo/frontend/src/notice-draft-api.ts`(제안 타입), `src/pages/officer/officer-modern-model.ts`(표시 문구), `src/pages/officer/ProgramPreviewEditor.tsx`(카드 한 곳), `tests/officer-modern.test.ts` |
| 바뀜 (문서) | `.trellis/spec/backend/notice-drafts.md`, `docs/DEVELOPMENT.md` |
| 안 바뀜 | `notice_analysis.py`, `api/program_analysis.py`(저장·검증·게시 조건), DB, 신청자 화면, 보호 파일 10개 |

## 2. 흐름

```
enrich_notice
  for proposal in body['criteria']:
      인용 검증 실패 → 버림                                   (그대로)
      같은 문장의 자동 후보와 값 일치 → 제안                    (그대로)
      같은 문장에 같은 종류의 자동 후보가 있음 → 버림            (그대로: 충돌이거나 값 누락)
      그 밖 → reference_for(proposal, draft)                  (새로)
              대상 후보와 읽은 값이 모두 성립하면 참고 제안
```

## 3. 계약

### 3.1 참고 제안 객체

```json
{"target_id": "<담당자 확인 후보의 id>", "type": "age", "reference": true,
 "read": "18~39세", "read_values": {"min_age": 18, "max_age": 39},
 "page": 1, "quote": "<모델이 인용한 문장>", "source": "jbai",
 "confidence": 0.0, "needs_review": true}
```

- 기존 제안과 달리 `values`(후보의 값)가 없고 `reference`, `read`, `read_values`가 있다. 프런트는 `reference`로 두 종류를 구분한다.
- `read`는 서버가 검증된 값으로 만든 짧은 표시 문자열이다. 모델이 쓴 글을 그대로 싣지 않는다.

### 3.2 읽은 값의 조건 (`stated_values(kind, values, quote)`)

1. 종류별 직접 값만 남긴다. 나머지 키(`basis_date`, `mode`, `city`, `household_table` 등)는 보지 않고 싣지도 않는다.

   | 종류 | 직접 값 (묶음 하나가 빠짐없이 있어야 함) | 선택 값 |
   |---|---|---|
   | age | `min_age`+`max_age`, 또는 `birth_start`+`birth_end` | |
   | residence | `province` | |
   | issue_date | `date` | |
   | income | `percent` | `operator` |
   | work_continuity | `months` | |

2. 남긴 값이 **모두** 인용 문장에서 확인되어야 한다. 하나라도 확인되지 않으면 제안 전체를 버린다.

   | 값 | 문장에서 확인하는 방법 |
   |---|---|
   | 정수(`min_age`, `max_age`, `months`), `percent` | 같은 수가 문장에 독립된 숫자로 있음. `months`는 `N년`(N×12)도 인정 |
   | 날짜(`birth_start`, `birth_end`, `date`) | 문장의 날짜 표기(`2026.3.3`, `2026년 3월 3일`, `2026-03-03`, `'26. 3. 3.`)를 날짜로 읽은 것 중에 같은 날이 있음 |
   | `province` | 그 시·도 이름이나 추출기가 쓰는 별칭이 문장에 있음 |
   | `operator` | `이하` 또는 `미만`이 문장에 있음 |

3. `read` 형식: age `18~39세` 또는 `1987-01-01 ~ 2008-12-31 출생`, residence `전북특별자치도`, issue_date `2026-03-03`, income `140%` 또는 `140% 이하`, work_continuity `5개월`. 종류 이름은 프런트가 기존 표시 이름으로 붙인다.

### 3.3 대상 후보 고르기

- 범위: 같은 쪽이고 인용이 서로 포함 관계인 후보(지금의 조건과 같다).
- 그 범위에 **같은 종류의 자동 후보**가 있으면 참고 제안을 만들지 않는다.
- 자동이 아닌 후보 가운데 `candidate_type`이 제안 종류와 같은 것을 먼저, 없으면 종류를 모르는 후보(`checklist`), 그것도 없으면 다른 종류의 후보를 고른다. 후보가 하나도 없으면 만들지 않는다.
- 고른 후보의 `values`에 같은 키가 비어 있지 않게 들어 있으면 읽은 값과 같아야 한다(`values_match`와 같은 정규화). 다르면 만들지 않는다.
- 같은 대상과 같은 종류의 참고 제안은 하나만 남긴다.

### 3.4 바뀌지 않는 것

- `criteria`의 모든 항목, 자동 규칙 연결, `needs_review`, 게시 차단 사유.
- 제안의 보존 방식: 저장하면 사라진다. 서버는 제안 내부를 저장하지 않으므로 새 필드로 인한 저장 형식 변화가 없다.
- 공급자에게 가는 자료: 공고문 글자와 부가 설명문뿐이다. 프롬프트도 그대로다.

### 3.5 기록

```
llm_result purpose=notice_analysis guidance=accepted criteria_received=4 criteria_accepted=0 criteria_reference=3
```

`criteria_accepted`는 자동 후보에 붙은 제안 수(지금과 같은 뜻), `criteria_reference`는 참고 제안 수다.

### 3.6 확인 도구

- `classify`: 참고 제안이 된 제안은 버림 사유가 아니라 통과로 센다. 집계 사전의 키는 늘리지 않는다(기존 시험의 비교를 유지).
- `run_once` 행에 `references`(참고 제안 수)를 더한다.
- `screen_violations`: 참고 제안은 대상이 자동이 아닌 후보이고, `stated_values`를 다시 돌린 결과가 `read_values`와 같아야 위반이 아니다.

### 3.7 프런트

- `notice-draft-api.ts`: 제안 타입에 `reference?: boolean`, `read?: string`.
- `officer-modern-model.ts`: `suggestionPresentation(suggestion)` → `{ chip, read }`. 참고 제안이면 칩은 `AI 참고 · 담당자가 직접 확인`, `read`는 `나이 범위 · 18~39세`처럼 종류 이름과 값. 기존 제안이면 칩은 지금 문구, `read`는 없음.
- `ProgramPreviewEditor.tsx`: 카드의 칩 문구를 위 함수에서 받고, `read`가 있으면 인용문 위에 `AI가 읽은 조건: …` 한 줄을 더한다. 버튼과 동작은 그대로다.

## 4. 호환성과 의도적 변경

- 기존 제안 객체, 저장 형식, API 응답의 다른 부분은 그대로다. 프런트가 옛 서버 응답(새 필드 없음)을 받아도 지금처럼 동작한다.
- 의도적으로 바뀌는 기대값: `test_notice_llm_stability.py`의 `llm_result` 줄 비교 3곳(줄 끝에 `criteria_reference=N` 추가). 구현 전에 `changed-test-expectations.md`에 적는다.
- `test_checklist_candidate_never_becomes_automatic_due_to_provider_confirmation`은 그대로 통과해야 한다(응답의 출생일 값이 문장에 없어 3.2로 버려진다). 같은 상황에서 직접 값만 보낸 응답은 참고 제안이 되고 후보는 담당자 확인 그대로라는 새 시험을 더한다.

## 5. 선택과 이유

- **문장에 적힌 값만 보여 준다** — 참고라도 화면에 나온 숫자는 근거가 된다. 담당자가 인용문과 값을 한눈에 대조할 수 있어야 한다. 계산이나 다른 줄 참조가 필요한 값(기준일)은 싣지 않는다.
- **모델의 글이 아니라 서버가 만든 표시 문자열** — 모델 출력이 그대로 화면에 나가는 길을 만들지 않는다.
- **자동 후보가 있는 문장은 건드리지 않는다** — 규칙이 계산할 수 있는 곳에서 AI의 다른 읽기를 나란히 보여 주면 어느 쪽이 맞는지 혼란만 준다.
- **자동 반영 없음** — "판정은 규칙이 한다"와 "공급자 제안은 판정 규칙을 만들지 못한다"는 원칙을 유지한다. 담당자가 `고치기`로 직접 값을 넣는다.

## 6. 되돌리기

- 백엔드, 프런트, 문서를 따로 커밋한다. 백엔드 커밋만 되돌리면 참고 제안이 생기지 않고 프런트는 옛 응답 그대로 동작한다.
- 운영 중에는 `LLM_PROVIDER=none`으로 끈다.
