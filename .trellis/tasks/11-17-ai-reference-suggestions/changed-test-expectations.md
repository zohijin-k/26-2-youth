# 의도적으로 바꾼 기존 시험 (2026-11-17)

승인된 동작 변경(prd R6: 검증 요약에 참고 제안 수 추가)의 직접 결과다. 아래 외의 기존 기대값은 건드리지 않는다.

| # | 시험 | 바꾸기 전 | 바꾼 뒤 | 이유 |
|---|---|---|---|---|
| 1 | `test_notice_llm_stability.py::test_each_failure_is_recorded_and_then_the_single_fallback_answers` 의 기록 줄 | `llm_result … criteria_received=1 criteria_accepted=1` | 같은 줄 끝에 ` criteria_reference=0` | 기록 줄에 참고 제안 수가 붙는다. 다른 값은 같다 |
| 2 | `test_notice_llm_stability.py::test_validation_summary_names_why_a_guidance_was_dropped` 의 기록 줄 | `llm_result … criteria_received=0 criteria_accepted=0` | 같은 줄 끝에 ` criteria_reference=0` | 위와 같음 |

기대값을 바꾸지 않고 그대로 통과해야 하는 시험: `test_notice_llm.py::test_checklist_candidate_never_becomes_automatic_due_to_provider_confirmation`(응답의 출생일 값이 인용 문장에 없어 참고 제안이 되지 않는다), 충돌하는 값·모르는 키·무관한 인용·존재하지 않는 쪽을 버리는 시험 전부, 확인 도구의 집계 시험 전부.
