# 작업 메모 (11-16-jbai-schema-check)

- 시작: main f258d2b, 브랜치 feat/jbai-schema-check. df 여유 32Gi(15GB 이상). 보호 해시 10/10.
- 미커밋 사용자 파일(task.json, logo.png) 스테이지 안 함. .env 는 읽기만(키 이름·존재 여부·DNS 확인, 값 출력 없음).
- 네트워크: 샌드박스에서 DNS 해석 O → 실제 호출 진행.

## 실제 JBAI 호출 기록 (한도 15회)

| 순번 | 명령 | 호출 | 누적 | 결과 파일 |
|---:|---|---:|---:|---|
| 1 | `probe_jbai_notice --all-modes --max-calls 9 --json` | 9 | 9 | probe-run1.json |
| 2 | `probe_jbai_notice --mode json_schema --repeats 1 --max-calls 1 --json` | 1 | 10 | probe-run2-json-schema-retry.json |
| 3 | `verify_fallback.py` (3단계 코드, 기본 json_schema + 대체 1회, 최대 2회) | 1 | 11 | probe-run3-default-fallback.json |

- 결과 파일에는 상태 코드·모드·개수·초만 있음(응답 본문·키·호스트·모델 이름 없음). 저장 직후 .env 값·호스트 포함 여부 검사 0.
- json_schema: 3회 중 2회 시간 초과(제공자 제한 10초), 1회 200·스키마 O(5.67초, 통과 1). 거절(4xx)은 없음 → 거절이 아니라 느리고 불안정. json_object: 7회 중 6회 200·스키마 O, 1회 시간 초과. prompt: 1/1 200·스키마 O.
- 버린 제안 사유는 대부분 값 불일치: 모델 입력(notice_payload)에는 규칙 후보가 없어서, 모델이 values_json 에 추출기 키(birth_start·birth_end·basis_date 등 계산값)를 그대로 맞추기 어렵다. 프롬프트·경계는 이 작업 범위 밖이라 바꾸지 않음.

## 3단계 판단

- 지시 조건은 "json_schema 가 거절·무시되고 다른 모드만 동작". 실측은 거절이 아니라 시간 초과 2/3. 시간 초과도 규칙 초안으로 돌아가는 실패라 대체 경로(실패·형식 오류 시 json_object 로 1회)를 넣었다. 기본값은 json_schema 그대로.
- 남은 호출 예산 4회는 쓰지 않음.

## 커밋 전 검사 기록

- 3단계(ffe2097): `check_staged.py` 의 ".env 값이 diff 에 있음" 검사가 docs/DEVELOPMENT.md 의 기존 문맥 줄(모델 이름 공개 표기)에 걸림 → 이번 작업 검사를 "추가 줄만 대조"로 좁히고, 추가 줄의 `JBAI_API_KEY` 뒤에 값이 붙은 줄 검사를 따로 넣음.
- 같은 커밋에서 지시된 grep (키 이름 뒤 값 줄 grep) 는 1건이었음: 기존 문맥 줄의 자리표시자 `JBAI_API_KEY` 자리표시자 `<API 키>`(추가 줄 아님, 값 아님). 명령 연결이 이 숫자로 커밋을 막지 않아 확인 전 커밋됨. amend 금지라 그대로 두고 보고서에 기록. 이후 커밋은 숫자가 0이 아니면 멈추도록 함.
