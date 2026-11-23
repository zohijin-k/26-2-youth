# 사업 등록·신청·서류 검토 서비스

청년 취업지원패키지 **신청자 화면과 담당자 화면을 함께 담은 데모 저장소**입니다. 신청자는 본인인증, 서식 작성·서명, 지원 항목 선택, 서류 업로드, 확인·제출과 신청 현황 조회를 진행하고, 담당자는 신청 목록과 제출 서류, 판독 결과·판정 근거를 확인하고 심사합니다. 두 화면은 프런트엔드 하나에 들어 있으며, 주소에 따라 둘 중 하나가 열립니다.

공고문·서식 PDF를 한 번에 올리고 분석 초안·입력칸을 확인하면 신청부터 사업별 심사까지 연결합니다. 기존 전북청년 취업지원패키지 흐름도 함께 제공합니다.

## 관련 저장소

| 용도 | 저장소 |
|---|---|
| 전체 안내 | [26-2-capstone](https://github.com/zohijin-k/26-2-capstone) |
| 관련 화면 | [26-2-savings-applicant](https://github.com/zohijin-k/26-2-savings-applicant) |
| 관련 화면 | [26-2-savings-officer](https://github.com/zohijin-k/26-2-savings-officer) |

## 실행 방법 — Windows WSL2(Ubuntu)

엔진·백엔드·시나리오 기준선은 두 화면을 합치기 전 기준 커밋 `e449c55`에서 **WSL2 Ubuntu 24.04.5 LTS · Python 3.12.3 · Node 22.23.4 · npm 10.9.9**로 측정했습니다. 두 화면을 합친 뒤에는 macOS(Python 3.14.6 · Node 26.13.1 · npm 11.20.0)에서 같은 수치와 프런트엔드 lint·build·단위 시험을 확인했고, WSL2에서는 다시 실행하지 않았습니다. Python 3.12 이상, Node 22.13 이상과 GitHub CLI가 준비된 Ubuntu 터미널에서 실행합니다.

```bash
gh repo clone zohijin-k/26-2-youth
cd 26-2-youth
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r demo/backend/requirements.txt -r engine_v2/requirements.txt
python -m engine_v2.tools.fetch_own_models
cd demo/frontend
npm ci
cd ../..
```

own OCR 모델은 다운로드할 때 고정 SHA-256으로 검증합니다. 모델 파일은 저장소에 포함하지 않습니다. WSL2에서는 Apple Vision 패키지가 설치 대상에서 제외됩니다. JBAI_* 설정은 비워 둡니다.

터미널 두 개에서 실행합니다.

```bash
# 터미널 1: 저장소 루트
source .venv/bin/activate
python -m uvicorn demo.backend.main:app --env-file .env --reload --port 8000
```

담당자 인증 설정을 읽도록 `--env-file .env` 옵션을 유지해 주세요. 환경 설정을 불러오지 않으면 담당자 로그인이 차단됩니다.

```bash
# 터미널 2: 저장소 루트에서
cd demo/frontend
npm run dev
```

프런트 개발 서버 주소는 <http://localhost:5173>입니다. 주소에 따라 화면이 정해집니다.

| 주소 | 열리는 화면 |
|---|---|
| <http://localhost:5173/> | 신청자 화면. 게시된 사업을 고르는 사업 찾기에서 시작합니다. |
| <http://localhost:5173/programs/1> | 신청자 화면의 사업 안내. 숫자는 사업 번호이며, 취업지원패키지는 여기서 신청하기를 누르면 본인인증(`/apply/identity`)으로 이어집니다. |
| <http://localhost:5173/officer> | 담당자 화면. 사업 목록에서 시작하며 새 사업을 올리거나 사업별 신청 목록을 엽니다. |
| `/?mode=officer` | 담당자 화면으로 이동합니다(주소가 `/officer`로 바뀝니다). |

담당자가 올린 사업은 **작성 중**으로 저장됩니다. 모든 서식 틀을 확인·확정하고 게시하면 신청자 화면에서 해당 서식으로 신청할 수 있습니다.

`/api` 요청은 백엔드의 8000 포트로 전달됩니다. API 문서는 <http://localhost:8000/docs>입니다.

신청자 화면은 백엔드 API로 신청을 만들고 저장하므로 백엔드를 함께 실행합니다. 본인인증을 제출할 때 신청을 만들고, 같은 탭에서 다시 열면 진행 중이던 신청을 이어서 엽니다. 본인인증 화면만 열어서는 신청을 만들지 않습니다. 서류 업로드 단계만 시험하는 개발용 도구는 [데모 안내](demo/README.md#3-기동)에 있습니다.

**Windows 네이티브: 이번에 검증하지 않음.**

### macOS — 설치 절차는 이번에 검증하지 않음

기존 macOS 안내를 기준으로, Python 3.12 이상과 Node 22.13 이상을 준비하고 위의 `gh repo clone`부터 설치·실행 명령을 그대로 사용합니다. 가상환경은 `python3 -m venv .venv`, `source .venv/bin/activate`로 생성·활성화합니다. macOS에서도 own 모델 다운로드가 필요하며, 엔진 의존성의 Apple Vision 패키지는 macOS에서만 설치됩니다.

## 합성 데이터로 시연하기

서버와 프런트를 실행한 뒤 <http://localhost:5173/officer?mock=1>을 열고 사업 목록에서 취업지원패키지를 고릅니다. 기존 **합성 목업**으로 취업지원패키지 담당자 목록·상세·심사 동작을 확인할 수 있습니다. 화면의 목업 배너로 시연 데이터임을 구분합니다.

- 합성 목업은 담당자 화면에만 있습니다. 브라우저 메모리에서 생성되며 DB에 신청을 넣지 않습니다.
- 목업의 심사 처리 결과는 새로고침하면 초기화됩니다. 서류 미리보기도 합성 예시입니다.
- 심사 기준 편집은 백엔드 API를 사용하므로 백엔드를 함께 실행합니다.
- 실제 접수 목록만 확인하려면 <http://localhost:5173/officer?mock=0>을 엽니다. 접수 건이 없으면 빈 목록으로 표시됩니다.
- `mock` 값은 `/officer` 주소에 붙입니다. 루트 주소에 붙인 `/?mock=1`은 신청자 화면을 엽니다.
- 목업에서는 사업 목록과 신청·심사 예시를 브라우저에서 만들며 백엔드를 호출하지 않습니다.

실서류는 시연·시험에 사용하지 않습니다. 신청자 화면에 올리는 서류도 합성 데이터만 사용합니다. 내려받은 모델, 생성 문서, 업로드 저장소와 SQLite DB는 커밋하지 않습니다.

## 검증

저장소 루트에서 가상환경을 활성화한 뒤 실행합니다.

```bash
python -m pip install pytest
python -m pytest engine_v2/tests -q -ra
python -m pytest demo/backend/tests -q -ra
cd demo/frontend
npm run lint
npm run build
node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts
```

기대 결과는 다음과 같습니다.

- 엔진: 2026-11-23 기준 own 모델을 설치하고 합성 글꼴을 받지 않은 상태에서 1,273개 통과·3개 건너뜀입니다. OCR 여러 쪽 읽기 시험 9개를 포함합니다. 건너뛴 시험의 합성 글꼴은 `python -m engine_v2.tools.fetch_synth_fonts`로 `engine_v2/data/synth_fonts/`에 받으며 커밋하지 않습니다.
- 백엔드: 2,325개 통과입니다(2026-11-23 기준, 범용 사업·서식·신청 흐름 및 개인정보 경계 시험 포함).
- `npm run lint`: 종료 코드 0, 경고 없음입니다.
- `npm run build`: 종료 코드 0입니다. 두 화면을 나눠 싣기 때문에 청크 크기 안내는 나오지 않습니다.
- `node src/forms/phone.test.ts`: 신청자 서식의 전화번호 형식 단위 시험입니다. Node가 TypeScript 파일을 직접 실행하므로 이 명령은 Node 22.18 이상에서 실행합니다. 통과하면 오류 없이 종료 코드 0으로 끝납니다. `node src/pages/officer/bulk-actions.test.ts`는 담당자 신청 목록의 구분과 일괄 처리 버튼 규칙 단위 시험입니다.

시나리오 18개 모듈의 실행 방법은 [데모 안내](demo/README.md#5-검증-스크립트)에 있습니다. 시험은 합성 데이터와 임시 DB·저장소를 사용합니다.

## 참고 문서

- [개발 안내](docs/DEVELOPMENT.md): 저장소 구조·OCR 설정·검증
- [데모 안내](demo/README.md): 신청자·담당자 화면·시나리오·서식 기능
- [제3자 고지](THIRD_PARTY_NOTICES.md): 모델·글꼴·패키지 출처와 라이선스

## 사업 올리기와 범용 신청

담당자는 `/officer/login`에서 로그인합니다. 실행 설정에 `OFFICER_PASSWORD=<비밀번호>`와 `OFFICER_SESSION_SECRET=<서명 비밀값>`이 필요합니다. 비밀번호가 비어 있으면 담당자 API는 503을 반환합니다. 세션은 HttpOnly·SameSite=Lax 쿠키로 8시간 유지되며, 만료 후 로그인하면 원래 주소로 돌아갑니다. 역할·지역 선택은 로그인 뒤 업무 범위를 고르는 화면 선택이며 별도 인증 수단이 아닙니다. `?mock=1`은 로그인과 백엔드 요청 없이 합성 목록·심사 예시를 보여 줍니다.

새 사업 올리기는 **공고문 PDF + 서식 PDF 여러 개 + 부가 설명문 → 분석하기 → 예시 페이지 수정·확인 → 올리기(게시)** 순서입니다. 예시 페이지는 ① 사업 제목·기간 ② 안내문 ③ 서식(서명용) ④ 제출 서류와 기준으로 구성합니다. 서식은 1~10개, 파일당 20MB·20쪽 이하이며 부가 설명은 4,000자 이하입니다. 노란 확인 항목과 서식 틀을 모두 확정하고 유효한 기간·네 칸의 내용을 저장해야 게시됩니다. 작성 중 저장, 게시 취소와 마감을 지원합니다. 글자층이 없거나 모호한 조건은 직접 입력·담당자 확인으로 남깁니다.

`/officer/programs/<사업 번호>`에는 신청 목록·사업 설정·사업 정보 탭이 있습니다. 범용 심사는 `/officer/programs/<사업 번호>/applications/<신청 번호>`에서 제출 원본과 작성 PDF, 기존 규칙 결과와 기준 체크리스트를 함께 봅니다. 원본은 inline으로만 표시하며 심사표는 없습니다. 확인 필요 건은 원본과 기준 확인을 마쳐야 최종 선정할 수 있고 API에서도 미확인 선정과 일괄 선정을 차단합니다. 취업지원패키지는 기존 신청·목록·심사 상세를 유지하며 설정 화면은 읽기 전용입니다.

신청자는 `/programs/<사업 번호>`에서 안내를 보고 본인인증·서식 작성·업로드·제출을 진행합니다. 모든 사업 종류와 신청 버전의 개인 신청·작성본·원본 API는 신청별 소유자 쿠키를 검사합니다. 같은 브라우저의 기존 좁은 범위 쿠키는 유효한 동일 토큰만 범위를 옮겨 이어갑니다. 토큰 없는 과거 신청은 차단하며 재발급 경로는 없습니다. 공개 사업 안내·공고문과 기존 공개 빈 서식·좌표 경로는 유지합니다. 신청자 응답에는 공고문 분석의 담당자 체크리스트·인용·신뢰도와 엔진 내부 정보를 싣지 않습니다. 기존 관리형 API와 제출 시점의 서식·기준 사본은 호환되며 DB·저장소를 초기화하지 않습니다.

### 선택적 JBAI 공고문 제안

기본 공급자는 `none`입니다. 공고문 분석용 제안을 켜려면 기존 실행 설정의 `JBAI_BASE_URL`·`JBAI_API_KEY=<API 키>`와 함께 `LLM_PROVIDER=jbai`, `JBAI_TEXT_MODEL=MainModel`을 명시합니다. 연결 확인은 합성 요약 문장 한 번으로 `/open-api/v1/chat/completions`의 HTTP 200을 확인했습니다. 실제 strict JSON schema 호환성은 추가 호출하지 않았으며 가짜 공급자로 검증했습니다. 공개 공고문 글자와 부가 설명문만 전송하고, 신청자 정보와 서류 판독값은 전송하지 않습니다. 근거가 맞는 제안만 담당자 화면에 덧붙이며 판정은 기존 엔진과 담당자가 확정한 기준이 수행합니다. 공급자 실패나 인용 불일치 시 규칙 초안을 유지합니다. 기존 안내·사유 설명의 별도 옵션 `PROGRAM_LLM_PROVIDER`·`PROGRAM_LLM_ENABLED`·`JBAI_LLM_MODEL`도 호환됩니다.

### 실행과 검증

2026-11-15 합성 검증: 엔진 **1,267**, 백엔드 **1,645**, 프런트 단위 시험 **52** 통과, 시나리오 **18개 모듈 실패 0**, lint·빌드 청크 경고 0입니다. 기존 심사 상세 보호 파일은 변경하지 않았습니다.

```bash
source .venv/bin/activate
python -m uvicorn demo.backend.main:app --env-file .env --host 127.0.0.1 --port 8010
```

```bash
cd demo/frontend
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

확인 주소: `http://127.0.0.1:5183/`, `/officer/login`, `/officer/programs/new`, `/officer/programs/<사업 번호>`, `/officer?mock=1`, 백엔드 문서 `http://127.0.0.1:8010/docs`.

전체 시험은 엔진을 먼저 실행하고 다음을 확인합니다. 시험은 실행 설정 파일 없이 합성 자료와 임시 DB·저장소를 사용하며 외부 텍스트 공급자는 가짜 공급자로 검증합니다.

```bash
source .venv/bin/activate
python -m pytest engine_v2/tests -q
python -m pytest demo/backend/tests -q
for f in demo/backend/tests/run_p*_scenarios.py; do
  python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"
done
cd demo/frontend
npx tsc -b && npx oxlint && npx vite build
node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts
```

## 결제영수증 검토

취업지원패키지의 정장비·사진비·자격증 응시료 결제영수증은 **담당자 확인 대상**입니다. OCR·Document AI로 판독하거나 자동 적합·부적합을 만들지 않습니다. 필수 영수증은 해당 업로드 칸에 정상적인 PDF·JPG·PNG 원본을 제출해야 하며, 권한 있는 담당자가 원본과 신청 금액을 직접 확인하고 기존 심사 메모·처리에 판단 근거를 기록합니다. 합본 PDF를 영수증 칸에 올려도 다른 필수 서류 칸은 채워지지 않습니다. 다른 서류는 각 칸에 제출하며 기존 자동 판독·행정 규칙을 유지합니다.

정책 범위와 검증 명령은 [영수증 검토 안내](docs/receipt-manual-review.md), 기존 미결정 항목은 [Phase 7 정책 결정표](docs/phase7-policy-decisions.md)를 확인하세요. PRODUCTION_NOT_READY를 유지합니다.
