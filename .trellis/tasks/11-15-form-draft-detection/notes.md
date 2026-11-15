# 작업 메모 (11-15-form-draft-detection)

- 시작: 2026-11-15, main 641db8d → feat/form-draft-detection. `df -h /` 여유 32Gi(15GB 이상).
- 커밋 제외 유지: .trellis/tasks/11-14-renewal-applicant-design/task.json, logo.png.
- 기준선 정밀도: 지시문은 102/129≈79%였으나 실측 자동 칸 121개, 102/121=84.3%. 목표는 더 엄격한 실측값(84.3%) 이상으로 판정.
- 기준선 게이트는 1단계 측정 도구 수정 도중 시작됨. 백엔드 수집 수 1645는 이전 작업 최솟값과 같아 새 시험 파일은 포함되지 않았음. draft.py는 기준선 동안 바뀌지 않았음.
- 1단계 커밋을 깨끗하게 하려고 2단계 draft.py를 잠시 scratchpad로 빼고 1단계만으로 게이트를 돌림. 2단계 시험은 scratchpad의 conftest 대리 모듈로 미리 검증.
- 합성 PDF의 내장 korea 글꼴에는 ☐/▢가 없어(□만 있음) 시험에서는 □와 그린 사각형을 사용.
- 어휘 제한 때문에 "신청인", "근무처 명", "사업명", "은행명", "예금주" 라벨은 규칙 c 대상이 아님. "신청인 : ____ (인)"은 규칙 d(콜론 라벨 + 서명 표시)로 처리.
- 3단계 경로는 기존 경로 이름에 맞춰 `/workspace/forms/{form_id}/snap` 사용(지시문의 경로는 "예"였음).
- 종단 시험 서버는 지시대로 uvicorn + `--env-file .env`로 띄웠으나, 실DB·저장소를 열지 않도록 이전 작업과 같은 격리 래퍼(e2e_backend.py, /tmp/form-draft-detection-e2e)를 앱으로 사용. 담당자 비밀번호·세션 비밀은 합성값으로 덮어쓰고 API 키는 제거. 끝난 뒤 그 폴더와 로그만 삭제.
- Playwright는 /tmp/renewal-npm-cache 의 기존 패키지를 사용(새 설치 없음).
