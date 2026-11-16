# 의도적으로 바꾼 기존 시험 (2026-11-16)

기존 시험을 통과시키려고 고친 것이 아니라, 승인된 동작 변경(prd R3, R4)이 기존 계약과 직접 충돌하는 곳이다. 아래 3곳 외의 기존 기대값은 건드리지 않는다.

계획서에는 2곳으로 적었다. 구현 중 3번(R3의 직접 결과)을 추가로 확인했다.

| # | 시험 | 바꾸기 전 | 바꾼 뒤 | 이유 |
|---|---|---|---|---|
| 1 | `test_notice_llm_formats.py::test_each_mode_discards_bad_quote_value_or_type_and_keeps_the_rule_draft` 의 매개변수 `{'values': {'min_age': 18, 'max_age': 39}}` (3개 방식) | 직접 적힌 값만 보낸 제안은 버림(규칙 초안 그대로) | 이 매개변수를 목록에서 빼고, 같은 입력이 통과하는 새 시험 `test_each_mode_accepts_a_proposal_with_only_the_stated_values` 로 옮김 | R4. 모델은 `basis_date`·`birth_start`·`birth_end` 같은 계산값을 맞출 수 없어 실측에서 제안이 전부 버려졌다. 충돌하는 값(`min_age: 17`)과 무관한 인용을 버리는 나머지 매개변수는 그대로다 |
| 2 | `test_probe_jbai_notice.py::test_discard_reasons_are_classified_and_only_verified_items_pass` 의 집계 | `passed 1, value 3` | `passed 2, value 2` | R4. `{'province': '전북'}` 제안은 추출기와 같은 별칭 표로 정규화하면 후보(`전북특별자치도`)와 같다. 인용 불일치 1건, 선정 약속 안내문 1건, JSON이 아닌 값 1건은 여전히 버려진다 |
| 3 | `test_probe_jbai_notice.py::test_modes_fall_back_in_order_and_stop_at_first_schema_valid_mode` 의 `json_object` 가짜 응답 | 코드 블록으로 감싼 정상 본문을 "쓸 수 없는 응답"의 예로 사용 | 가짜 응답을 JSON이 아닌 글로 바꿈(기대값 줄은 그대로). 코드 블록으로 감싼 정상 본문이 읽힌다는 새 시험 `test_fenced_valid_answer_is_readable_and_chosen` 추가 | R3. 코드 블록으로 감싼 정상 본문은 이제 읽을 수 있는 응답이다. 시험의 원래 의도(방식을 순서대로 시도하고 첫 유효 방식에서 멈춤)는 그대로 검증한다 |

유지한 계약(변경 없음): `{}` 와 코드 블록 속 `{}` 는 쓸 수 없는 응답, 대체는 정확히 한 번, 첫 호출 제한 30초, 충돌하는 값·후보에 없는 키·무관한 인용·존재하지 않는 쪽·허용 종류 밖은 제안 불가, 공급자에게 가는 것은 공고문 글자와 부가 설명문뿐, 로그와 출력에 키·예외 문구 없음.
