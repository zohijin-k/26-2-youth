# 개발 안내

OCR은 서류 사진이나 PDF에서 글자를 읽는 기술입니다.

## 목차

- [저장소와 브랜치](#저장소와-브랜치)
- [협업 규칙](#협업-규칙)
- [폴더 구조](#폴더-구조)
- [개발 환경과 실행](#개발-환경과-실행)
- [OCR 판독 설정](#ocr-판독-설정)
- [평가 도구](#평가-도구)
- [확인 및 테스트](#확인-및-테스트)
- [지켜야 할 원칙](#지켜야-할-원칙)
- [확인이 필요한 사항](#확인이-필요한-사항)
- [참고 자료](#참고-자료)

## 저장소와 브랜치

저장소는 GitHub의 `zohijin-k/26-2-youth`입니다. 청년 취업지원패키지 신청자 화면과 담당자 화면을 함께 다루며, 기준 브랜치는 `main`입니다. 신청자 화면은 별도 저장소였던 `26-2-youth-applicant`의 내용을 이 저장소에 합친 것입니다. 이 저장소(이전 이름 `26-2-youth-officer`)의 기존 clone은 작업 중인 변경을 확인한 뒤 `git checkout main && git pull`로 갱신합니다. `26-2-youth-applicant`의 clone은 갱신되지 않으므로 이 저장소를 새로 clone합니다. git을 쓰지 않으면 저장소 첫 화면에서 브랜치가 `main`인지 확인하고 Code → Download ZIP으로 받습니다.

이전 통합 저장소의 기능 브랜치 목록은 이 저장소의 브랜치 현황이 아닙니다.

## 협업 규칙

1. 작업 전 `main`을 최신으로 받습니다: `git checkout main && git pull`.
2. 새 브랜치를 만듭니다: `git checkout -b feat/<작업-내용>`.
3. 커밋하고 push한 뒤 GitHub에서 `main`으로 PR(변경 내용을 검토받기 위한 병합 요청)을 만듭니다.
4. PR에 변경 내용을 적고 병합합니다. 병합한 브랜치는 삭제합니다.
5. `main`에 직접 push하지 않습니다.
6. 커밋 전 `git status`로 실제 서류, 환경 설정 파일, API 키가 섞이지 않았는지 확인합니다.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| [`demo/`](../demo/README.md) | 취업지원패키지 신청자·담당자 데모, FastAPI(Python 웹 API 도구) 백엔드, React(화면 구성 라이브러리) 화면, 시나리오 확인 스크립트 |
| [`engine/`](../engine/README.md) | 기존 규칙 판정 엔진. 데모가 서류·자격 판정 파이프라인으로 사용합니다. |
| [`engine_v2/`](../engine_v2/README.md) | OCR 파이프라인·서류 추출기·분류기·평가 도구. `own` 모델 파일은 `models/`에 내려받으며 커밋하지 않습니다. |
| [`engine_v2/pipeline/ocr/`](../engine_v2/pipeline/ocr/) | OCR 공통 인터페이스와 엔진별 모듈 (`own.py` 포함) |
| [`engine_v2/classifier/`](../engine_v2/classifier/) · [`engine_v2/docs/`](../engine_v2/docs/) | 합성 서류 분류 실험 코드 · OCR/분류 설명 문서 |
| `engine_v2/models/` | 내려받은 OCR·분류 모델 파일 (gitignore, 커밋하지 않음) |
| [`dashboard/`](../dashboard/) | 현황 대시보드 코드 |
| [대시보드 옛 안내](archive/dashboard-README.md) | 현재 상태와 다를 수 있는 이전 문서 |
| [`docs/archive/`](archive/) | 옛 기록 보관 문서 |
| [`docs/`](./) | 기획·계획, 개발, 데모 환경 문서 |
| [`.trellis/`](../.trellis/workflow.md), [`.claude/`](../.claude/), [`AGENTS.md`](../AGENTS.md) | 작업 흐름, 에이전트 설정, 저장소 작업 지침 |
| `engine_v2/data/private/` | 엔진 도구의 기본 데이터 경로 (gitignore). 이 저장소의 시험에는 합성 데이터만 사용합니다. |

`demo_run.py`는 기존 `engine/` 단독 실행 예제입니다. 시스템 전체는 데모 백엔드와 프론트엔드를 실행합니다.

## 개발 환경과 실행

엔진·백엔드·시나리오 기준선은 두 화면을 합치기 전 기준 커밋 `e449c55`에서 **WSL2 Ubuntu 24.04.5 LTS · Python 3.12.3 · Node 22.23.4 · npm 10.9.9**로 측정했습니다. 두 화면을 합친 뒤에는 macOS(Python 3.14.6 · Node 26.13.1 · npm 11.20.0)에서 같은 수치와 프런트엔드 lint·build·단위 시험을 확인했고, WSL2에서는 다시 실행하지 않았습니다. Python 3.12 이상, Node 22.13 이상을 사용합니다. Windows 네이티브와 macOS의 설치 절차는 이번에 검증하지 않았습니다. 데모 로컬 OCR은 own이 기본이며 macOS에서도 모델 설치가 필요합니다.

저장소 루트에서 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r demo/backend/requirements.txt -r engine_v2/requirements.txt
python -m engine_v2.tools.fetch_own_models
cd demo/frontend
npm ci
cd ../..
```

백엔드와 프론트엔드를 별도 터미널에서 실행합니다.

```bash
# 터미널 1 — 저장소 루트, 가상환경 활성화 후
python -m uvicorn demo.backend.main:app --env-file .env --reload --port 8000
```

담당자 인증 설정을 읽도록 `--env-file .env` 옵션을 유지해 주세요. 환경 설정을 불러오지 않으면 담당자 로그인이 차단됩니다.

```bash
# 터미널 2 — 저장소 루트에서
cd demo/frontend
npm run dev
```

프런트 개발 서버 주소는 <http://localhost:5173>이며, 프런트엔드 하나가 주소에 따라 두 화면 중 하나만 엽니다.

| 주소 | 열리는 화면 |
|---|---|
| <http://localhost:5173/> | 신청자 화면의 사업 찾기. 게시된 사업이 카드로 나옵니다. |
| `/programs/<사업 번호>` | 신청자 화면의 사업 안내. 취업지원패키지는 신청하기가 `/apply/identity`(본인인증)로 이어집니다. |
| `/apply/...` | 신청자 화면의 신청 흐름. 본인인증 제출 시 생성하고 이후 같은 신청을 복원합니다. |
| <http://localhost:5173/officer> | 담당자 화면의 사업 목록. `/officer/programs/new`에서 새 사업을 올립니다. |
| `/officer/programs/<사업 번호>` | 담당자 화면의 사업별 작업 공간. 취업지원패키지는 신청 목록과 심사 상세가 이 주소 아래에서 열립니다. |
| 그 밖의 주소 | `?mode=officer`가 있으면 담당자 화면, 없으면 신청자 화면입니다. 예전 담당자 주소(`/officer/<역할>`, `/officer/<역할>/review/<번호>`, `?mode=officer&o_open=...`)는 취업지원패키지 작업 공간의 같은 화면으로 옮겨집니다. `mode` 없이 저장해 둔 `?o_open=...` 주소는 신청자 화면으로 열립니다. |

신청자 쪽과 담당자 쪽을 고르는 규칙은 `demo/frontend/src/navigation-url.ts`의 `currentMode()`에 있고, `demo/frontend/src/App.tsx`가 그 결과에 따라 한쪽 입구(`pages/applicant/ApplicantApp.tsx` 또는 `pages/officer/OfficerApp.tsx`)만 불러옵니다. 각 입구가 자기 주소를 읽어 화면 하나를 올립니다.

사업은 백엔드의 사업 저장소(`ProgramPosting`, `demo/backend/api/postings.py`)에 있습니다. 담당자 API는 `/api/officer/postings`, 신청자 API는 `/api/postings`이며 신청자 쪽에는 게시되거나 마감된 사업만 나갑니다. 취업지원패키지는 서버가 처음 뜰 때 게시된 사업 한 건으로 들어가고, 실제 접수 기간이 지났으면 시연을 위해 종료일을 그해 12월 31일로 넣습니다. 접수 기간은 담당자 API로 고칠 수 있고 심사 기준의 날짜와는 별개입니다. 해가 바뀌어 취업지원패키지가 마감으로 보이면 `PATCH /api/officer/postings/<사업 번호>`에 `{"apply_end": "YYYY-MM-DD"}`를 보내 기간을 늘립니다(기간을 고치는 화면은 아직 없습니다). 관리형 새 사업은 입력칸 확인·확정 후 게시하면 사업 찾기와 온라인 신청에 연결됩니다. 화면을 오가는 탭은 없습니다.

담당자 화면의 기존 합성 목업은 <http://localhost:5173/officer?mock=1>, 실제 API 목록만 확인하려면 <http://localhost:5173/officer?mock=0>을 사용합니다. 목업은 담당자 화면에만 있고 DB를 채우지 않으며 처리 결과는 새로고침하면 초기화됩니다. 신청 흐름(`/apply/...`)은 열릴 때 같은 탭에 저장된 신청을 복원하고, 본인인증 제출 시에만 신청을 새로 만듭니다. 사업 찾기와 사업 안내는 신청 건을 만들지 않습니다. 두 쪽 모두 백엔드를 함께 실행합니다. FastAPI 문서는 <http://localhost:8000/docs>입니다.

시나리오 시험용 가상 PDF는 `demo/fixtures/samples/`가 없으면 시험에서 자동 생성합니다. 담당자 합성 목업 시연에는 이 PDF 생성이나 DB 초기화가 필요하지 않습니다. 신청자 화면에서 만든 신청 건은 `demo/demo.db`와 `demo/storage/`에 남습니다. 개발 중 DB·업로드 저장소 초기화가 필요하면 서버를 멈추고 `python -m demo.backend.reset --dry-run`으로 삭제 대상을 먼저 확인합니다. 서류 업로드 단계 시험용 `seed_application` 도구의 사용법은 [데모 안내](../demo/README.md#3-기동)에 있습니다.

## OCR 판독 설정

이번 제출에서는 전북AI를 사용하지 않습니다(연동 코드는 있으나 이번 제출에서는 사용하지 않음). JBAI_* 설정은 비워 둔 채 실행합니다. 판독 순서는 시연 고정 응답 → 로컬 OCR → PDF 텍스트입니다. 전북AI 연동 코드는 남아 있지만 이번 제출 판독 체인에서는 호출하지 않습니다.

데모 로컬 OCR은 macOS를 포함한 모든 환경에서 own이 기본입니다. 비어 있지 않은 `ENGINE_V2_OCR` 값이 있으면 이를 우선합니다. 기본 선택에서 own 모델 파일이 없을 때만 easyocr로 대체합니다. 명시적으로 own을 선택했는데 모델이 없거나 해시 확인·추론에 실패하면 다른 OCR 엔진으로 대체하지 않습니다. 모델 설치는 macOS에서도 필요합니다.

`engine_v2.engine.run`과 CLI(명령줄 도구)의 선택값은 `own`, `applevision`, `easyocr`, `paddle`입니다. `off`는 데모 전용 비활성화 값입니다. 공용 엔진 선택에 전북AI는 포함되지 않습니다.
## 평가 도구

`fetch_synth_fonts.py`는 합성 평가용 글꼴을 받고 `make_synth_eval.py`는 가상 문서 평가 세트를 만듭니다. `ocr_bench`로 own·Apple Vision 등 OCR 엔진을 비교할 수 있습니다. OCR은 서류 사진이나 PDF에서 글자를 읽는 기술입니다. 평가 정의와 한계, 실서류 평가의 개인정보 보호 방식은 [own OCR 설명](../engine_v2/docs/own-ocr.md)을 참고합니다. `extract_diag --safe-issue`는 값·인식 텍스트·파일명·좌표를 출력하지 않습니다.

```bash
python engine_v2/tools/fetch_synth_fonts.py
python engine_v2/tools/make_synth_eval.py
python -m engine_v2.tools.ocr_bench --synth engine_v2/data/synth_eval/manifest.json --engines own applevision
python -m engine_v2.tools.ocr_bench "<파일 경로>" --doc resident_abstract --engines own applevision
```

own의 현재 평가는 합성 서류 3종(주민등록초본·납부확인서·자격득실확인서 형태), 열화 조건과 ±2도 이내 회전을 포함합니다. 90도·180도 방향 보정은 없습니다. 기존 문서에서 보고한 실서류 관찰은 주민등록초본과 4대보험 가입내역에 한정되며 공개 안내에서는 식별정보와 수치 판독 결과를 공개하지 않습니다. 합성 자료 결과는 실제 서류 전반의 성능을 보장하지 않습니다.

자체 OCR 모델은 공개 사전학습 PP-OCRv5 mobile 검출·한국어 인식 모델의 ONNX 변환본이며, 모델을 직접 사전학습했다는 의미는 아닙니다. own은 데모 로컬 OCR의 기본 엔진이며, 분류 실험 모델은 데모 판정에 연결되어 있지 않습니다. 출처·라이선스, 모델 설치와 평가 방법은 [own OCR 설명](../engine_v2/docs/own-ocr.md)에 있습니다.

## 확인 및 테스트

테스트는 가상 데이터와 임시 저장소를 사용합니다. 시나리오 전체와 OCR 엔진 테스트는 저장소 루트에서 실행합니다.

```bash
for f in demo/backend/tests/run_p*_scenarios.py; do echo "== $f"; python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"; done
python -m pip install pytest
python -m pytest engine_v2/tests -q -ra
python -m pytest demo/backend/tests -q -ra
```

`e449c55`의 WSL2 기준선은 엔진 1,264개 통과·합성 글꼴 누락 3개 건너뜀, 백엔드 1,227개 통과입니다. 건너뛴 3개는 `engine_v2/tests/test_own_format_integration.py`의 시험으로, own 모델을 설치한 상태에서 합성 글꼴을 `python -m engine_v2.tools.fetch_synth_fonts`로 `engine_v2/data/synth_fonts/`에 받아 두면 함께 실행되어 엔진 기준선은 1,267개 통과가 됩니다. 시나리오 18개는 확인 1,885개 통과·실패 0이며 P14의 원본 서식 8개 검증도 통과했습니다. Apple Vision 관련 시험 건너뜀은 없고 `ocrmac` 설치는 Darwin 조건에 따라 제외됩니다. 위 반복문은 한 시나리오가 실패해도 나머지를 계속 실행합니다. 사업 저장소를 넣은 뒤 백엔드는 시험 62개가 늘어 1,289개, 신청 목록의 탭·검색·확인 필요 사유와 일괄 승인 제한을 넣은 뒤 28개가 더 늘어 1,317개, 범용 사업 작업에서 95개가 더 늘어 1,412개 통과입니다(macOS Python 3.12.16에서 확인).

프론트엔드 타입 검사·린트·빌드와 단위 시험은 다음과 같습니다.

```bash
cd demo/frontend
npm run lint
npm run build
node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts
```

`npm run lint`는 종료 코드 0에 경고 없이 끝납니다. `npm run build`는 종료 코드 0이며, 신청자 화면과 담당자 화면을 따로 나눠 싣기 때문에 청크 크기 안내는 나오지 않습니다. `node src/forms/phone.test.ts`는 신청자 서식의 전화번호 형식 단위 시험으로, Node가 TypeScript 파일을 직접 실행하므로 Node 22.18 이상에서 실행합니다. 통과하면 오류 없이 종료 코드 0으로 끝납니다. `node src/pages/officer/bulk-actions.test.ts`는 담당자 신청 목록의 구분과 일괄 처리 버튼 규칙 단위 시험입니다.

하위 폴더별 기능과 추가 실행 방법은 [데모](../demo/README.md), [기존 엔진](../engine/README.md), [엔진 v2](../engine_v2/README.md), 대시보드 코드와 [대시보드 옛 안내](archive/dashboard-README.md)를 확인합니다.

자체 OCR의 제작 과정·평가·한계는 [제작 과정 기록](../engine_v2/docs/own-ocr-history.md)을 참고하세요.

## 지켜야 할 원칙

- 이 저장소의 시연·시험에는 합성 데이터만 사용합니다. 모델, 생성 문서, 업로드 원본과 DB는 커밋하지 않습니다.
- 판정은 공고문에 근거한 규칙으로 합니다. OCR·모델은 문서를 읽는 데 씁니다.
- 두배적금 화면은 없지만 두 사업의 신청 API와 판정 저장·DB 모델은 보존합니다. 신청자용 API의 배점·내부 판단 정보 비노출 시험도 유지합니다.
- 파일 이름이 아니라 서류 내용으로 종류와 판정 근거를 판단합니다.
- 담당자는 신청자가 올린 원본 서류를 내려받지 않고 화면으로만 확인합니다. 신청자는 본인이 작성한 서식만 내려받을 수 있으며 P4 시나리오가 이 경계를 확인합니다.
- 값을 출력하는 점검 도구는 이름·주소·번호를 가립니다.
- OCR 모델·글꼴·패키지의 제3자 출처와 라이선스는 [제3자 고지](../THIRD_PARTY_NOTICES.md)와 [own OCR 설명](../engine_v2/docs/own-ocr.md)에서 확인합니다.
- API 키를 코드·로그·커밋에 넣지 않습니다.
- 모델 학습에는 개인정보가 없는 합성 데이터만 사용합니다. 실서류는 기관 내부 평가에만 사용하고 판독은 가능한 한 기관 내부 엔진으로 합니다. 외부 전송은 기관의 명시 확인 범위에서만 합니다. 주민등록번호 뒷자리는 응답 즉시 지우고 원문을 남기지 않습니다.

## 확인이 필요한 사항

- 혼합가입자가 제출할 서류와 건강보험료 합산 방식
- 공고문 표가 7인까지인 상태에서 8\~10인 상한표를 적용할 출처·기준
- 취업지원패키지 지원 횟수 누적 범위와 인정 시험 목록
- 담당자 심사 상태를 승인·보완요청·부적격·재검토 4종으로 전환할지

## 참고 자료

- `‘26년 전북청년 함께 두배적금 운영성과 및 ‘27년 운영계획.pdf` — 사업 개요, 2026년 운영 애로사항, 2027년 개선 방향
- `2026년 전북청년 함께 두배적금 상담(콜센터) 시스템 구축 및 운영 결과 보고서_주베스트인.pdf` — 콜센터 상담 데이터, 실무자 건의사항(통합 플랫폼, 자체 취소 기능, 온라인 서명 등)

## 관리형 사업 확장과 보안 검증

담당자는 `/officer/login`에서 로그인합니다. 실행 설정에 `OFFICER_PASSWORD=<비밀번호>`와 `OFFICER_SESSION_SECRET=<서명 비밀값>`이 필요합니다. 비밀번호가 비어 있으면 담당자 API는 503을 반환합니다. 세션은 HttpOnly·SameSite=Lax 쿠키로 8시간 유지되며, 만료 후 로그인하면 원래 주소로 돌아갑니다. 역할·지역 선택은 로그인 뒤 업무 범위를 고르는 화면 선택이며 별도 인증 수단이 아닙니다. `?mock=1`은 로그인과 백엔드 요청 없이 합성 목록·심사 예시를 보여 줍니다.

새 사업 올리기는 **공고문 PDF + 서식 PDF 여러 개 + 부가 설명문 → 분석하기 → 예시 페이지 수정·확인 → 올리기(게시)** 순서입니다. 예시 페이지는 ① 사업 제목·기간 ② 안내문 ③ 서식(서명용) ④ 제출 서류와 기준으로 구성합니다. 서식은 1~10개, 파일당 20MB·20쪽 이하이며 부가 설명은 4,000자 이하입니다. 노란 확인 항목과 서식 틀을 모두 확정하고 유효한 기간·네 칸의 내용을 저장해야 게시됩니다. 작성 중 저장, 게시 취소와 마감을 지원합니다. 글자층이 없거나 모호한 조건은 직접 입력·담당자 확인으로 남깁니다.

`/officer/programs/<사업 번호>`에는 신청 목록·사업 설정·사업 정보 탭이 있습니다. 범용 심사는 `/officer/programs/<사업 번호>/applications/<신청 번호>`에서 제출 원본과 작성 PDF, 기존 규칙 결과와 기준 체크리스트를 함께 봅니다. 원본은 inline으로만 표시하며 심사표는 없습니다. 확인 필요 건은 원본과 기준 확인을 마쳐야 최종 선정할 수 있고 API에서도 미확인 선정과 일괄 선정을 차단합니다. 취업지원패키지는 기존 신청·목록·심사 상세를 유지하며 설정 화면은 읽기 전용입니다.

신청자는 `/programs/<사업 번호>`에서 안내를 보고 본인인증·서식 작성·업로드·제출을 진행합니다. 모든 사업 종류와 신청 버전의 개인 신청·작성본·원본 API는 신청별 소유자 쿠키를 검사합니다. 같은 브라우저의 기존 좁은 범위 쿠키는 유효한 동일 토큰만 범위를 옮겨 이어갑니다. 토큰 없는 과거 신청은 차단하며 재발급 경로는 없습니다. 공개 사업 안내·공고문과 기존 공개 빈 서식·좌표 경로는 유지합니다. 신청자 응답에는 공고문 분석의 담당자 체크리스트·인용·신뢰도와 엔진 내부 정보를 싣지 않습니다. 기존 관리형 API와 제출 시점의 서식·기준 사본은 호환되며 DB·저장소를 초기화하지 않습니다.

### 선택적 JBAI 공고문 제안

기본 공급자는 `none`입니다. 공고문 분석용 제안을 켜려면 기존 실행 설정의 `JBAI_BASE_URL`·`JBAI_API_KEY=<API 키>`와 함께 `LLM_PROVIDER=jbai`, `JBAI_TEXT_MODEL=MainModel`을 명시합니다. 연결 확인은 합성 요약 문장 한 번으로 `/open-api/v1/chat/completions`의 HTTP 200을 확인했습니다. 실제 strict JSON schema 호환성은 추가 호출하지 않았으며 가짜 공급자로 검증했습니다. 공개 공고문 글자와 부가 설명문만 전송하고, 신청자 정보와 서류 판독값은 전송하지 않습니다. 공급자는 공고문의 모집 개요를 바탕으로 신청자 안내문 초안을 써서 안내문 칸에 바로 채우고(**AI 작성 · 공고문과 대조 필요** 칩, 담당자가 작성완료를 눌러야 게시 가능), 기준은 근거가 맞는 제안만 담당자 화면에 덧붙입니다. 판정은 기존 엔진과 담당자가 확정한 기준이 수행합니다. 공급자 실패나 인용 불일치 시 규칙 초안을 유지합니다. 기존 안내·사유 설명의 별도 옵션 `PROGRAM_LLM_PROVIDER`·`PROGRAM_LLM_ENABLED`·`JBAI_LLM_MODEL`도 호환됩니다.

`JBAI_RESPONSE_FORMAT`(선택)은 JSON 요청 방식을 고릅니다: `json_object`(기본) · `json_schema`(strict 스키마) · `prompt`(형식 지정 없이 "JSON만 출력" 지시). 그 방식이 오류·시간 초과(첫 호출 30초, 안내문 작성 시간 포함)·형식 오류로 끝나면 다음 방식(`json_schema`→`json_object`→`prompt`)으로 **한 번만** 다시 묻고, 그래도 안 되면 규칙 초안을 유지합니다. 분석 한 건이 공급자에 쓰는 시간은 두 호출을 합쳐 40초까지입니다(`JBAI_LLM_BUDGET_SEC`, 5~120초). 남은 시간이 8초보다 적으면 두 번째 호출은 하지 않습니다. 공고문은 앞에서부터 30,000자까지만 보냅니다(`JBAI_LLM_MAX_INPUT_CHARS`). 인용·값·기준 종류 검증은 방식과 관계없이 같습니다. 2026-11-16 실측과 확인 도구는 아래 "JBAI 공고문 제안 시연"을 봅니다.

응답은 코드 블록이나 앞뒤 설명에 싸여 있어도 JSON 객체를 찾아 읽고, 모르는 키와 모양이 틀린 항목은 그 부분만 버립니다. `guidance`와 `criteria` 두 키가 없는 응답은 쓸 수 없는 응답입니다. 기준 제안은 모델이 문장에 직접 적힌 값(나이는 `min_age`·`max_age` 또는 `birth_start`·`birth_end`, 거주는 `province`, 발급일은 `date`, 소득은 `percent`, 근속은 `months`)만 답해도 통과합니다. 조건은 모델이 쓴 값이 규칙 후보의 값과 모두 같고, 그 종류의 직접 적힌 값이 빠짐없이 있는 것입니다. 후보와 다른 값이나 후보에 없는 키가 하나라도 있으면 버립니다. 통과한 제안에 실리는 값은 규칙 후보의 값이며 모델의 값이 아닙니다.

호출마다 결과가 로거 `demo.backend.llm`에 한 줄 남습니다(예: `llm_call purpose=notice_analysis mode=json_object attempt=1 outcome=timeout seconds=30.0`). 결과 종류는 `ok`·`timeout`·`http_429`·`http_4xx`·`http_5xx`·`network`·`bad_transport`·`no_content`·`truncated`·`too_large`·`bad_shape`·`budget_exhausted`입니다. 실패는 WARNING이라 로그 설정 없이도 백엔드 콘솔에 보입니다. 응답을 읽은 뒤에는 `llm_result purpose=notice_analysis guidance=… criteria_received=… criteria_accepted=…` 한 줄(INFO)이 남고, `guidance`는 `accepted`·`none`·`shape`·`quote`·`length`·`number`·`promise` 중 하나입니다. 키·주소·모델 이름·요청과 응답 본문·예외 문구는 남기지 않습니다.

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

### JBAI 공고문 제안 시연

기본은 꺼짐(`LLM_PROVIDER=none`)이며 꺼져 있으면 외부 호출이 없습니다. 2026-11-16 첫 실측(실제 호출 11회, `.trellis/tasks/11-16-jbai-schema-check/report.md`)에서는 검증을 통과한 제안이 공고문당 평균 0~0.5개였고, 버려진 이유는 거의 전부 값 불일치였습니다. 그래서 값 일치 규칙, 응답 해석, 시간 상한을 바꾸고 같은 날 다시 쟀습니다(`.trellis/tasks/11-16-jbai-llm-stabilize/report.md`).

재측정은 합성 공고문 3종을 `json_object` 방식으로 4회씩, 바꾸기 전 코드 12회와 바꾼 코드 12회입니다.

| 공고문 (자동 기준 수) | 바꾸기 전: 통과 합계 | 바꾼 뒤: 안내문 채택 | 바꾼 뒤: 기준 제안 통과 |
|---|---|---|---|
| A (4) | 1, 1, 1, 1 | 4/4 | 4, 4, 4, 4 |
| B (2) | 0, 1, 1, 0 | 3/4 | 2, 2, 2, 2 |
| C (1) | 1, 1, 1, 1 | 4/4 | 1, 1, 1, 1 |

통과 합계는 안내문 초안과 기준 제안을 합친 수입니다. 24회 모두 HTTP 200이었고 2.8~8.7초가 걸렸습니다. 검증에서 탈락한 내용이 화면에 들어간 경우는 0입니다. 긴 합성 공고문(48,635자, 앞 30,000자 전송)도 6.3초에 정상 응답했습니다.

이 결과로는 **켠 상태로 시연할 수 있습니다.** 한계는 다음과 같습니다. 합성 공고문 3종, 12회 규모의 측정이고 실제 공고문 PDF로는 재지 않았습니다. 전북AI 응답이 느린 날에는 분석이 최대 40초까지 걸립니다. 시연 때는 실행 설정에 `JBAI_LLM_BUDGET_SEC=25`를 넣어 상한을 줄이는 것을 권장합니다. 꺼도 규칙 초안으로 같은 흐름을 시연할 수 있습니다.

다시 잴 때는 아래 명령을 씁니다. 합성 공고문 3종을 4회씩 보내며(12회), 출력에는 상태·방식·개수·초만 있습니다. `--long --max-calls 13`으로 바꾸면 긴 합성 공고문 1회를 더 보내 입력 상한을 확인합니다. 도구 한 번의 호출 한도는 15회입니다.

```bash
python -m demo.backend.tools.probe_jbai_notice --mode json_object --repeats 4 --max-calls 12 --json
```

켜는 법(백엔드 실행 설정 파일에서, 기존 `JBAI_BASE_URL`·API 키 설정은 그대로 둠):

1. `LLM_PROVIDER=jbai`
2. `JBAI_TEXT_MODEL`에 사용할 텍스트 모델 이름
3. (선택) `JBAI_RESPONSE_FORMAT` — 비우면 `json_object`입니다. 첫 실측에서 `json_schema`는 3회 중 2회 10초 시간 초과였고, `json_object`는 재측정 25회가 모두 정상 응답(2.8~8.7초)이었습니다.
4. 백엔드를 다시 시작합니다(`--env-file .env`).

끄는 법: `LLM_PROVIDER=none`으로 바꾸거나 줄을 지우고 백엔드를 다시 시작합니다.

동작: 공고문 분석 때 공개 공고문 글자와 부가 설명문만 보냅니다. 안내문은 공급자가 모집 개요로 쓴 초안이 안내문 칸에 들어갑니다. 인용이 원문에 없거나, 공고문에 없는 숫자(나이·금액·날짜·인원)나 선정 약속('자동 선정'·'누구나' 등)이 들어 있으면 버리고 로컬 초안(공고문 모집 개요 발췌)을 씁니다. 기준 제안은 담당자 화면 "추가 안내" 안에 **AI 제안 · 담당자 확인 필요** 칩이 붙은 카드로만 덧붙고, 규칙 초안의 기준은 바뀌지 않습니다. 인용이 원문에 없거나, 모델이 쓴 값이 규칙 후보와 다르거나, 직접 적힌 값이 빠졌거나, 허용 종류(`age`·`residence`·`issue_date`·`income`·`work_continuity`) 밖이면 버립니다. 오류·시간 초과·형식 오류·검증 실패는 모두 규칙 초안만 남기고, 원인은 백엔드 콘솔의 `llm_call`·`llm_result` 줄에서 확인합니다.

시연 전 확인(합성 공고문만 보내며 키·주소·응답 본문은 출력하지 않음, 기본 최대 9회 호출):

```bash
.venv/bin/python -m demo.backend.tools.probe_jbai_notice --all-modes
```
