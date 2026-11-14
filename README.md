# 사업 등록·신청·서류 검토 서비스

청년 취업지원패키지 **신청자 화면과 담당자 화면을 함께 담은 데모 저장소**입니다. 신청자는 본인인증, 서식 작성·서명, 지원 항목 선택, 서류 업로드, 확인·제출과 신청 현황 조회를 진행하고, 담당자는 신청 목록과 제출 서류, 판독 결과·판정 근거를 확인하고 심사합니다. 두 화면은 프런트엔드 하나에 들어 있으며, 주소에 따라 둘 중 하나가 열립니다.

공고문·서식 PDF로 새 사업을 등록하고 담당자가 입력칸을 확정하면 신청부터 접수 목록까지 연결합니다. 기존 전북청년 취업지원패키지 흐름도 함께 제공합니다.

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
python -m uvicorn demo.backend.main:app --reload --port 8000
```

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
- 사업 목록 자체는 항상 백엔드의 사업 저장소에서 읽습니다. 목업을 켜면 취업지원패키지 카드의 신청 수만 목업 수치로 바뀝니다.

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

- 엔진: own 모델을 설치한 상태에서, 합성 글꼴을 `python -m engine_v2.tools.fetch_synth_fonts`로 받아 두었으면 1,267개 통과, 받지 않았으면 1,264개 통과·3개 건너뜀입니다. 글꼴은 `engine_v2/data/synth_fonts/`에 받으며 커밋하지 않습니다.
- 백엔드: 1,412개 통과입니다(범용 사업·서식·신청 흐름 및 개인정보 경계 시험 포함).
- `npm run lint`: 종료 코드 0, 경고 없음입니다.
- `npm run build`: 종료 코드 0입니다. 두 화면을 나눠 싣기 때문에 청크 크기 안내는 나오지 않습니다.
- `node src/forms/phone.test.ts`: 신청자 서식의 전화번호 형식 단위 시험입니다. Node가 TypeScript 파일을 직접 실행하므로 이 명령은 Node 22.18 이상에서 실행합니다. 통과하면 오류 없이 종료 코드 0으로 끝납니다. `node src/pages/officer/bulk-actions.test.ts`는 담당자 신청 목록의 구분과 일괄 처리 버튼 규칙 단위 시험입니다.

시나리오 18개 모듈의 실행 방법은 [데모 안내](demo/README.md#5-검증-스크립트)에 있습니다. 시험은 합성 데이터와 임시 DB·저장소를 사용합니다.

## 참고 문서

- [개발 안내](docs/DEVELOPMENT.md): 저장소 구조·OCR 설정·검증
- [데모 안내](demo/README.md): 신청자·담당자 화면·시나리오·서식 기능
- [제3자 고지](THIRD_PARTY_NOTICES.md): 모델·글꼴·패키지 출처와 라이선스

## 사업 올리기와 범용 신청

담당자는 `/officer/programs/new`에서 제목·기간·공고문 PDF·서식 PDF(1~10개)·제출 서류를 입력합니다. ① 기본 정보 저장 → ② 자동 입력칸 초안 확인·수정·확정 → ③ 안내 메시지 작성 → ④ 신청자 미리보기·게시 순서입니다. 서식 PDF는 파일당 20MB·20쪽 이하이며 암호 PDF는 거부합니다. 자동 초안의 모든 칸은 담당자 확인 대상입니다. 수정한 틀은 다시 확정해야 게시할 수 있습니다.

게시한 사업은 `/programs/<사업 번호>`에서 안내하고 `/apply/programs/<사업 번호>/identity`에서 신청합니다. 본인인증 제출 때 신청번호를 만들며, 새로고침하면 같은 신청을 이어갑니다. 확정된 서식과 PDF 사본·제출 서류 목록을 신청에 고정하고, 서식 작성 → 서류 업로드 → 최종 확인 → 제출 → 작성 PDF·접수증·마이페이지로 이어집니다. 범용 사업에는 취업지원패키지의 자격 질문·지원 항목·선착순 안내를 표시하지 않습니다.

담당자 사업 작업 공간 `/officer/programs/<사업 번호>`에서 해당 사업 신청 목록의 확인 필요·적합·처리 완료 탭을 봅니다. 판독 불확실성은 확인 필요로 보내며 기존 서류 FAIL 차단과 일괄 최종 선정 제한을 유지합니다. 범용 사업은 “자격 규칙 미설정 — 담당자가 공고문 기준으로 확인”을 표시합니다. 기존 심사 상세·원본 뷰어는 보존하고, 범용 사업의 호환되지 않는 심사표에는 연결하지 않습니다. 기본 취업지원패키지는 기존 신청·심사 흐름을 유지하고 목록에서 읽기 전용으로 표시합니다.

기존 postings 응답 계약을 유지하기 위해 새 작성 화면은 `workflow_version=1` 관리형 사업과 `/api/officer/postings/<id>/workspace` 확장 API를 사용합니다. 이전 방식의 사업은 온라인 신청을 열지 않습니다. 기존 DB는 새 테이블을 추가하여 시작하며 업로드 저장소를 초기화하지 않습니다. 신규 범용 신청·서식·파일 API는 신청자 소유 쿠키를 확인합니다.

### 선택적 문장 초안

안내 초안과 사유 설명의 기본 공급자는 `none`이며 규칙 기반 문장을 사용합니다. `.env`에서 `PROGRAM_LLM_PROVIDER=jbai`, `PROGRAM_LLM_ENABLED=true`와 기존 `JBAI_BASE_URL`·`JBAI_API_KEY`를 명시해야 외부 초안 공급자가 켜집니다. 선택 모델은 `JBAI_LLM_MODEL`입니다. `.env` 설정을 적용할 때는 백엔드를 `python -m uvicorn demo.backend.main:app --env-file .env --port 8010`으로 실행합니다. 공개 사업 정보·공고문 또는 허용한 규칙 코드·정적 필드 이름·규칙 문구만 전송하며, 신청자 입력·판독값·저장된 사유 메시지는 보내지 않습니다. 설명은 규칙 결과 아래 “설명(자동 작성)”으로 표시되며 판정을 바꾸지 않습니다. 이번 검증은 가짜 공급자만 사용했으며 실제 JBAI 텍스트 API 호환성은 확인하지 않았습니다.

### 별도 포트로 확인

기존 서버와 분리해 확인할 때는 다음 두 터미널을 사용합니다. `/api` 프록시는 `VITE_API_TARGET`으로 선택하며 기본값은 기존 8000 포트입니다.

```bash
# 저장소 루트: 백엔드
source .venv/bin/activate
python -m uvicorn demo.backend.main:app --host 127.0.0.1 --port 8010
```

```bash
# 다른 터미널: 프런트
cd demo/frontend
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

확인 주소: `http://127.0.0.1:5183/`, `/officer/programs/new`, `/officer?mock=1`, 백엔드 문서 `http://127.0.0.1:8010/docs`.

### 최신 전체 검증

2026-11-15 macOS 가상환경(Python 3.12.16 · Node 26.13.1) 검증: 엔진 **1,267**, 백엔드 **1,412**, 프런트 단위 시험 **48** 통과, 시나리오 **18개 모듈 실패 0**, lint 경고 0, 빌드 청크 경고 없음. 이번 기능의 새 시험은 백엔드 95개·프런트 16개입니다. 엔진 OCR 시험은 메모리 피크를 피하도록 먼저 단독 실행한 뒤 다른 전체 시험을 실행합니다.

```bash
source .venv/bin/activate
python -m pytest engine_v2/tests -q
python -m pytest demo/backend/tests -q
for f in demo/backend/tests/run_p*_scenarios.py; do
  echo "== $f"
  python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"
done
cd demo/frontend
npx tsc -b && npx oxlint && npx vite build
node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts
```
