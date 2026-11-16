# 담당자 사업 화면 수정 7건

Source: owner feedback 2026-11-16.

1. 사업 삭제 — any status, from the editor menu and the list card menu, while no application (incl. applicant drafts) exists; otherwise the server refuses and asks to close it.
2. 사업 수정 — published/closed programs show a visible outlined 수정하기 button (confirm → unpublish → editable). List menu item renamed to 수정하기.
3. Remove the "근거 없음·직접 입력" chip and the empty 근거 toggle on officer-entered items; 확인/확인함 → 작성완료.
4. Guidance preview: every typed line break is a paragraph (officer preview and applicant page). LLM guidance was never written into the field (extractive ≤240-char excerpt, only as a collapsed suggestion) — now it is.
5. LLM writes the guidance from the notice's 모집 개요; local fallback extracts that section without a provider. Guards: verbatim citation, no numbers absent from the notice, no selection promises. Still needs officer 작성완료 before publish.
6. ④ 제출 서류와 기준 → ④ 업로드 서류 with 필수 업로드 서류 / 추가 업로드 서류 groups (by required flag; owner chose this over a pure rename) and a separate ⑤ 신청 자격 기준.
7. 기타 서류 wording → 추가 업로드 서류 group / "목록에 없는 서류 · 담당자 확인".

Also: default JBAI_RESPONSE_FORMAT json_object (measured more reliable), per-call timeout 30s.

Verification: backend pytest full suite, frontend tsc/oxlint/build/unit, Playwright run (e2e_backend.py + e2e.mjs, fake provider, isolated DB) — 8/8 assertions.
