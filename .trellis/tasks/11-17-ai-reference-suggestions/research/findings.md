# 코드 조사 (2026-11-17, feat/jbai-llm-stabilize 90a6911 기준)

## 제안이 화면까지 가는 경로

1. `POST /api/officer/programs/analyze` (`api/program_analysis.py:359`) → `analyze_notice` → `enrich_notice` → 초안의 `suggestions`에 제안이 실린 채 `template_json['notice_draft']`로 저장된다.
2. 프런트 `ProgramPreviewEditor.tsx:220-229`가 `draft.suggestions`를 "추가 안내" 안의 카드로 그린다. 카드: 대상 항목 이름, 칩 `AI 제안 · 담당자 확인 필요`, 인용문, `공고문 N쪽 보기`, `항목 확인하기`(해당 항목으로 스크롤), `제안 제외`.
3. 담당자가 저장하면 `PUT /postings/{id}/analysis` → `validate_analysis` (`api/program_analysis.py:186-296`). 입력의 `suggestions` 키는 허용하지만 출력에 넣지 않는다. 그래서 저장 뒤에는 제안이 사라지고, 제안의 내부 모양은 서버에서 검증하지 않는다.
4. 게시 차단 사유(`analysis_blockers`, 299-327줄)는 제목·기간·안내문·서류·기준 항목의 `needs_review`만 센다. 제안은 세지 않는다.

## 지금의 제안 조건 (`notice_llm.py` `enrich_notice`)

- 인용이 원문과 일치(`_quote_valid`), 후보와 종류가 같음, 후보에 `engine_rule`이 있음, 쪽이 같음, 인용이 서로 포함 관계, `values_match`.
- 제안 객체: `target_id`, `type`, `values`(후보의 값 복사), `page`, `quote`, `source`, `confidence: 0.0`, `needs_review: True`.

## 담당자 확인 후보의 모양 (`notice_analysis.py` `_criterion`)

- `type: 'checklist'`, `engine_rule: None`, `candidate_type`은 추출기가 알아본 종류(`age`, `residence`, `issue_date`, `income`, `work_continuity`) 또는 `checklist`.
- `values`는 추출기가 읽은 만큼 들어 있다. 예: 나이 후보는 `min_age`·`max_age`가 있고 `basis_date`가 비어 있을 수 있다. 종류를 모르는 후보는 `{}`다.

## 실제 공고문에서 본 문장 모양 (측정 자료의 인용)

- `□ 모집대상 : 공고일 기준 전북특별자치도 내 주소지를 둔 청년(18~39세)` — 거주와 나이가 한 줄.
- `② 연 령 : 2025.12.31.기준 만 18~39세 청년(1986.1.1.~2007.12.31. 출생)` — 날짜가 여러 개.
- `m 모든 서류는 공고일(‘26. 3. 3.~) 이후 발급분만 인정하며, 접수한 서류` — 두 자리 연도.
- `‧ 소득요건 : 청년가구 기준 중위소득 60% 이하 / 원가구(청년+부모) 기준 중위소득 100% 이하` — 비율이 둘.

## 이 작업이 건드리는 시험

- `tests/test_notice_llm.py:145` `test_checklist_candidate_never_becomes_automatic_due_to_provider_confirmation` — 담당자 확인 후보에 제안이 붙지 않음을 `== value`로 확인한다. 이 시험의 응답은 계산값(`birth_start` 등)을 함께 보내므로 R2로 버려져 그대로 통과할 것으로 본다. 구현 뒤 확인한다.
- `tests/test_notice_llm_stability.py`의 `llm_result` 줄 비교 3곳 — 기록 줄에 참고 제안 수를 더하면 기대 문자열이 바뀐다.
- `tools/probe_jbai_notice.py`의 `screen_violations` — 제안의 대상 종류와 값이 후보와 같아야 한다고 본다. 참고 제안용 검증을 따로 넣어야 한다.
- 프런트: `tests/officer-modern.test.ts`에 표시 문구 시험을 더한다. 보호 파일 10개에는 `ProgramPreviewEditor.tsx`, `officer-modern-model.ts`, `notice-draft-api.ts`가 없다.
