# Journal - hcw889 (Part 1)

> AI development session journal
> Started: 2026-09-14

---



## Session 1: 현황 대시보드 초안
<!-- trellis-session: v=2 fp=99580ec87009e60f -->

**Date**: 2026-09-15
**Task**: 현황 대시보드 초안
**Branch**: `main`

### Summary

두배적금 신청·심사 현황 대시보드 프론트엔드 초안 작성(Vite+React+TS+ECharts, '26년 규모 기반 목업 데이터, 전북 14개 시군 지도, 기준일 슬라이더). 피드백 반영: 작성 시작 데이터 제거, 배점·커트라인 정보를 하단 담당자용 영역으로 분리

### Git Commits

| Hash | Message |
|------|---------|
| `1ef266d` | 대시보드 데모 생성 (목업데이터) |

### Status

[OK] **Completed**


## Session 2: JBAI LLM 안정화
<!-- trellis-session: v=2 fp=6a679b6e5f438d21 -->

**Date**: 2026-11-17
**Task**: JBAI LLM 안정화
**Branch**: `feat/jbai-llm-stabilize`

### Summary

전북AI를 켠 공고문 분석을 안정화했다. 실패 원인을 고정 어휘로 기록하고, 분석 한 건의 대기를 40초로 묶고, 어긋난 응답을 부분만 버리고 읽으며, 기준 제안은 문장에 적힌 값만 비교한다. PR #18, #19로 main에 병합됐다.

### Main Changes

- 호출 기록 llm_call / llm_result (키·주소·본문 없음)
- 총 대기 상한 40초, 남은 시간 8초 미만이면 두 번째 호출 생략
- 응답 해석 완화, 문장에 적힌 값 비교(values_match), 전송 30,000자 상한

### Git Commits

| Hash | Message |
|------|---------|
| `eab7155` | feat(llm): stabilize the JBAI notice provider |
| `6a0072f` | docs(llm): record the JBAI stabilization contract and measurements |
| `90a6911` | docs(llm): record the screen check and real-notice measurements |

### Testing

- [OK] 합성 공고문 3종 x 4회: 기준 제안 통과 공고문당 0~0.5개에서 4, 2, 1개로 증가, 24회 모두 HTTP 200
- [OK] 공개된 실제 공고문 3종 x 3회: AI 안내문 9회 모두 채택, 기준 제안 0건
- [OK] 엔진·백엔드·시나리오 실패 목록이 변경 전과 동일(이 Windows PC 기준)

### Status

[OK] **Completed**


## Session 3: AI 참고 제안 (담당자 확인 항목)
<!-- trellis-session: v=2 fp=58b9baeb21e0f649 -->

**Date**: 2026-11-17
**Task**: AI 참고 제안 (담당자 확인 항목)
**Branch**: `feat/ai-reference-suggestions`

### Summary

규칙이 담당자 확인으로 남긴 조건 문장에 AI가 읽은 값을 표시 전용 참고 카드로 보여 준다. 값은 인용 문장에 그대로 적힌 것만 싣고, 기준 항목과 게시 조건은 바꾸지 않는다. PR #20으로 main에 병합됐다.

### Main Changes

- notice_llm.py: stated_values, reference_for, 기록 줄에 criteria_reference
- 담당자 화면 카드: AI 참고 칩과 AI가 읽은 조건 한 줄

### Git Commits

| Hash | Message |
|------|---------|
| `7cd16c9` | feat(llm): 담당자 확인 항목에 AI 참고 제안 추가 |
| `343b693` | feat(officer): 참고 제안 카드에 AI 참고 칩과 읽은 조건 표시 |
| `74b9054` | docs(llm): 참고 제안 규격과 실측 결과 기록 |

### Testing

- [OK] 공개된 실제 공고문 3종 x 3회: 참고 카드 매번 2~4개(이전 0), 받은 제안 31건 중 24건
- [OK] 합성 공고문 3종 x 2회: 자동 후보 제안 통과 유지(4, 2, 1), 화면 위반 0
- [OK] LLM 관련 백엔드 시험 315 통과, 프런트 단위 79 통과

### Status

[OK] **Completed**

### Next Steps

- 한 문장에 같은 종류의 조건이 둘인 경우(60% / 100%)는 하나만 표시됨
- 시연에서 LLM_PROVIDER=jbai를 켤지 팀 결정
