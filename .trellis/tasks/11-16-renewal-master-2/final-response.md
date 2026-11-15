## 2. 단계별 결과

| 단계 | 결과 | 커밋 해시 | 새 시험 수 | 비고 |
|---|---|---|---|---|
| 0 | 준비 완료·커밋 없음 | — | 0 | origin/main 7dc87a9에서 시작, 2f7bb2b 포함 확인 |
| 1 | 커밋됨 | 2d3c9fe | 백엔드 72·프런트 2 | 익명200 기대값 2개 폐기; 기존 업무 기대값 유지; 명시적 합성 로그인/소유권 fixture |
| 2 | 커밋됨 | 61d4fe4 | 백엔드 16·프런트 0 | 사업별3탭·별도범용상세·원본확인fingerprint·기존단건/일괄승인우회차단 |
| 3 | 커밋됨 | d4d560f | 백엔드 38·프런트 0 | 합성공고문·근거인용·복합조건checklist·기존규칙연결; 템플릿공고PDF0개 |
| 4 | 커밋됨 | 3cf2623 | 백엔드 66·프런트 2 | 네칸예시편집·게시게이트·신청자허용목록·동일토큰범위이전·NaN등불확실값확인필요 |
| 5 | 커밋됨 | 6a92fba | 백엔드 41·프런트 0 | JBAI선택제안39개+원본PNG표시2개시험; P6기존1ms계측변동무수정단독재실행통과 |
| 6 | 커밋됨 | HEAD(문서 커밋) | 0 | 화면22확인·22캡처, 실제HTTP54행, 문서·보고서 |

실패 패치·선행 실패 건너뜀은 없습니다. 6단계는 자기 참조를 피하려고 `HEAD`로 표기합니다. 역할·지역 선택은 로그인 뒤 업무 화면 선택이며 인증 수단이 아닙니다.

## 3. 전체 시험 결과와 익명 기대값 폐기

| 전체 시험 | 기준선 | 최종 |
|---|---|---|
| 엔진 A | 1,267 통과·실패 0 | 1,267 통과·실패 0 |
| 백엔드 B | 1,412 통과·실패 0 | 1,645 통과·실패 0 |
| 시나리오 C | 18개 모듈 통과·실패 0 | 18개 모듈 통과·실패 0 |
| 프런트 단위 시험 D | 48 통과·실패 0 | 52 통과·실패 0 |
| TypeScript | 통과 | 통과 |
| lint 경고 | 0 | 0 |
| build 청크 경고 | 없음 | 없음 |

| 시나리오 모듈 | 기준선 | 최종 |
|---|---|---|
| run_p11_criteria_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p12_subsidy_criteria_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p13_household_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p14_pdf_forms_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p15_jbai_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p16_job_docs_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p17_own_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p18_applicant_precheck_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p19_nhis_history_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p20_nhis_continuation_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p2_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p3_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p4_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p5_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p6_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p7_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p8_localocr_scenarios | 통과·실패 0 | 통과·실패 0 |
| run_p9_identity_scenarios | 통과·실패 0 | 통과·실패 0 |

새 시험은 백엔드 233개·프런트 4개입니다. 기존 시험 삭제와 통과 수 감소는 없습니다. Python 의존성 경고는 기준선과 같은 엔진 7개·백엔드 9개이며 lint 경고와 구분합니다.

| 파일 | 함수 | 이전 기대값 | 이후 기대값 |
|---|---|---|---|
| `demo/backend/tests/test_generic_access.py` | `test_other_applicant_cannot_read_or_mutate_generic_application_or_files` | 200 | 401 |
| `demo/backend/tests/test_generic_access.py` | `test_integer_aliases_and_wrong_cookie_cannot_bypass_generic_owner_guard` | 200 | 403 |

위 두 익명 성공 기대값만 폐기했습니다. 1단계 커밋 본문에 `security: anonymous-access expectations retired`를 넣었습니다. 그 밖의 기존 업무 기대값은 수정하지 않았습니다. 기존 담당자 fixture는 실제 로그인 API로, 직접 DB에 만든 합성 신청 fixture는 명시적 시험 소유권으로 준비했습니다(`authenticated-test-fixtures.json`).

중간 검증에서 기존 P6 S2의 `slowest_upload_ms`가 0ms와 1ms로 달라 반복 비교가 한 번 실패했습니다. 시험·기대값·제품의 시간 측정은 수정하지 않았고 단독 재실행에서 261/0을 확인했습니다. 최종 A→B→C→D는 순서대로 다시 실행해 모두 통과했습니다. 초기 기준선 측정의 임시 공간 부족과 누락된 임시 작업 트리 자원은 별도 재측정으로 분리했습니다. 각 단계 JSON과 원인 기록은 `notes.md`에 남겼습니다.

## 4. 실제 HTTP 보안 확인 표

분리된 합성 서버에서 요청한 54개 행입니다. 숫자는 임시 합성 신청·서류 번호입니다. 공개 행은 세 요청 모두 200이며, 개인 신청은 두 비소유자 요청 모두 403, 담당자 경로는 두 무세션 요청 모두 401입니다. v0/v1·범용 경계와 토큰 없는 과거 신청·쿠키 이전·세션 만료·미설정 503은 추가 pytest로 검증했습니다.

| 경로 | 무쿠키 | 남의 쿠키 | 본인/담당자 |
|---|---:|---:|---:|
| `GET /api/applications/4` | 403 | 403 | 200 |
| `PATCH /api/applications/4` | 403 | 403 | 200 |
| `GET /api/applications/4/documents` | 403 | 403 | 200 |
| `GET /api/applications/4/required-documents` | 403 | 403 | 200 |
| `GET /api/applications/4/final-check` | 403 | 403 | 200 |
| `GET /api/applications/4/status` | 403 | 403 | 200 |
| `GET /api/applications/4/consents` | 403 | 403 | 200 |
| `GET /api/applications/4/subsidy-items` | 403 | 403 | 200 |
| `GET /api/applications/4/forms` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/job_application.pdf` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/job_consent.pdf` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/files/written.pdf` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/files/job_application/filled.pdf` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/files/job_consent/filled.pdf` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/job_application/pages/1.png?preview=true` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/job_consent/pages/1.png?preview=true` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/interview-confirmation/filled.pdf` | 403 | 403 | 200 |
| `GET /api/applications/4/forms/signature-scan.png` | 403 | 403 | 200 |
| `GET /api/applications/4/identity-pledge.png` | 403 | 403 | 200 |
| `GET /api/files/6` | 403 | 403 | 200 |
| `GET /api/files/7` | 403 | 403 | 200 |
| `GET /api/files/8` | 403 | 403 | 200 |
| `GET /api/officer/session` | 401 | 401 | 200 |
| `GET /api/officer/roles` | 401 | 401 | 200 |
| `GET /api/officer/applications` | 401 | 401 | 200 |
| `GET /api/officer/postings` | 401 | 401 | 200 |
| `GET /api/programs` | 200 | 200 | 200 |
| `GET /api/programs/job_package` | 200 | 200 | 200 |
| `GET /api/programs/job_package/criteria` | 200 | 200 | 200 |
| `GET /api/postings` | 200 | 200 | 200 |
| `GET /api/applications/4/forms/layouts/job_application` | 200 | 200 | 200 |
| `GET /api/applications/4/forms/templates/job_application.pdf` | 200 | 200 | 200 |
| `GET /api/applications/4/forms/job_application/pages/1.png?preview=false` | 200 | 200 | 200 |
| `GET /api/applications/4/forms/files/job_application/blank.pdf` | 200 | 200 | 200 |
| `GET /api/applications/4/forms/files/job_application/source.hwp` | 200 | 200 | 200 |
| `GET /api/applications/4/forms/files/original-hwp/options` | 200 | 200 | 200 |
| `GET /api/applications/4/forms/files/original-hwp` | 200 | 200 | 200 |
| `GET /api/postings/4/files/notice.pdf` | 200 | 200 | 200 |
| `GET /api/postings/3/files/notice.pdf` | 200 | 200 | 200 |
| `POST /api/applications/6/identity` | 403 | 403 | 200 |
| `POST /api/applications/4/self-check` | 403 | 403 | 200 |
| `POST /api/applications/4/consents` | 403 | 403 | 200 |
| `POST /api/applications/4/subsidy-items` | 403 | 403 | 200 |
| `PUT /api/applications/4/doc-context` | 403 | 403 | 200 |
| `POST /api/applications/4/documents` | 403 | 403 | 200 |
| `DELETE /api/applications/4/documents/8` | 403 | 403 | 200 |
| `POST /api/applications/4/documents` | 403 | 403 | 200 |
| `POST /api/applications/4/forms/signature-scan` | 403 | 403 | 200 |
| `DELETE /api/applications/4/forms/signature-scan` | 403 | 403 | 200 |
| `POST /api/applications/4/forms/signature-scan` | 403 | 403 | 200 |
| `POST /api/applications/4/submit` | 403 | 403 | 200 |
| `GET /api/officer/applications/4` | 401 | 401 | 200 |
| `GET /api/officer/applications/4/reasons` | 401 | 401 | 200 |
| `POST /api/officer/applications/4/decision` | 401 | 401 | 200 |

## 6. JBAI 연결 결과

| 항목 | 결과 |
|---|---|
| 연결 | 성공·HTTP 200 |
| 엔드포인트 경로 | `/open-api/v1/chat/completions` |
| 모델 | `MainModel` |
| 확인 호출 | 시도 2회·실제 전송 1회, 허용된 합성 요약 문장만 사용 |
| 첫 시도 | 샌드박스 DNS `URLError:gaierror`·HTTP 전송 없음 |
| 기본 상태 | `none`·설정 파일 변경 없음 |
| 켜는 방법 | `LLM_PROVIDER=jbai`, `JBAI_TEXT_MODEL=MainModel`, 기존 BASE_URL/API_KEY 설정 사용 |

실제 strict JSON schema 호출은 추가하지 않았고 가짜 공급자로 검증했습니다. 신청자 정보·판독값 전송, AI 판정, 키·호스트·응답 본문 출력은 하지 않았습니다. JSON·인용·기준 불일치와 시간 초과는 규칙 초안으로 복귀합니다.

## 7. 사람이 아침에 결정할 것

1. 기존 보호 뷰어의 단일 페이지 PDF 최초 표시 문제를 다음 작업에서 수정할지 결정해 주세요. 현재 기존 상세는 확대·축소 후 확인 가능하며 범용 상세는 원본 페이지 이미지로 첫 표시를 보완했습니다.
2. JBAI 공고문 제안을 켤지 결정해 주세요. 기본은 none이며, 켜기 전 실제 JSON schema 호환 여부를 추가 확인할 수 있습니다.
3. 실제 사업의 서식 틀·인용·기준을 담당자가 확인하고, 자동 연결되지 않은 기준의 체크리스트 운영 방식을 확정해 주세요.
