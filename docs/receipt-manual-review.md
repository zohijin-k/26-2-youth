# 결제영수증 담당자 확인

2026-11-23 사용자 확정 정책. PRODUCTION_NOT_READY. 운영 DB migration·배포는 수행하지 않습니다.

정장비 `suit_<회차>_receipt`, 사진비 `photo_1_receipt`, 자격증 응시료 `certificate_<회차>_receipt`는 결제영수증 필수 슬롯입니다. 면접비는 정액 지원이므로 영수증 슬롯이 없습니다. 신청자가 입력한 금액에 따른 기존 지원금 예상 계산과 한도는 바꾸지 않습니다. 예상 계산이 영수증의 사실 확인이나 지급 승인을 의미하지 않습니다.

공유 업로드 평가에서 체크리스트의 결제영수증 타입을 확인한 뒤, PDF·JPG·PNG 파일을 열 수 있는지만 검사합니다. OCR 공급자 호출·텍스트 추출·서류 분류·신뢰도·화질 평가·자동 PASS/FAIL은 실행하지 않습니다. 영수증 내용이 맞는지, 금액·결제일·지원 항목이 적절한지는 담당자가 원본으로 검토합니다. 잘못된 종류의 내용을 올렸는지는 자동 판정하지 않습니다. 빈 파일·손상·확장자/내용 불일치·암호 파일은 요청 오류로 거절하며, 이는 서류 자동 부적합 판정이 아닙니다.

정상 파일은 기존 저장소·인증 경로에 원본 바이트 그대로 보관하고 `NEEDS_REVIEW` / `RECEIPT_MANUAL_REVIEW`로 표시합니다. 필수 슬롯이 없거나 원본 파일이 사라졌으면 제출할 수 없습니다. 제출 후 업로드·삭제는 기존 409 차단을 유지합니다.

담당자 상세에서 기존 PDF·이미지 인라인 뷰어로 원본을 엽니다. 판독 신뢰도 대신 ‘담당자 확인 대상’을 보여주며, 기존 담당자 메모와 신청 단위 심사 처리를 사용합니다. 별도의 영수증 승인 기능은 만들지 않습니다. 기존 역할 권한·Review revision/CAS와 감사 기록을 유지합니다. 과거 저장된 OCR·Review·결정은 일괄 수정하지 않습니다.

자동 분할 업로드는 기존처럼 거절합니다. 합본 PDF를 영수증 슬롯에 올리면 그 슬롯 하나에만 저장됩니다. 면접확인서·초본 등 다른 필수 슬롯은 별도 제출해야 하며, 같은 합본을 다른 슬롯에 올려도 해당 슬롯에서는 기존 OCR이 실행됩니다. 원본 전체는 보존합니다.

## 합성 검증

저장소 루트에서 기존 개발 의존성을 설치한 가상환경으로 실행합니다. 외부 OCR/LLM은 비활성화합니다.

```bash
python -m pytest demo/backend/tests/test_receipt_manual_review.py demo/backend/tests/test_quality_failure_policy.py -q
python -m pytest demo/backend/tests/test_review_revision.py demo/backend/tests/test_review_bulk_revision_contract.py demo/backend/tests/test_review_write_guard.py demo/backend/tests/test_integrity_closure.py -q
python -m pytest demo/backend/tests engine_v2/tests -q
cd demo/frontend
npx tsc -b
npm run build
npm run lint
node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts
```

실행 결과와 환경은 해당 Trellis 작업의 `research/validation.md`에 기록합니다. Phase 7의 다른 엔진 정책 19행과 README 정책 8건은 그대로 보류합니다.

정상 영수증의 담당자 확인만 남은 상태는 서류 미비로 취급하지 않으며 자동으로 보완 기한을 시작하지 않습니다. 다른 서류·자격 미비에 대한 기존 보완 규칙은 유지합니다.
