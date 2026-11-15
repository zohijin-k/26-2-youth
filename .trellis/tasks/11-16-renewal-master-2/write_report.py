"""Render the requested report from measured, value-free evidence."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def read(name):
    return json.loads((HERE / name).read_text())

baseline = read('baseline.json')
final = read('gate-final.json')
assert all(row['exit'] == 0 for key, row in final.items() if key != 'scenarios')
assert all(row['exit'] == 0 for row in final['scenarios'].values())
security = read('security-matrix.json')
visual = read('visual-e2e-result.json')
pixel = read('visual-pixel-comparison.json')
connection = read('jbai-connection.json')
measurements = read('analysis-measurements.json')
assert security['passed'] and not visual['page_errors'] and not visual['errors']
assert not visual['mock_api_requests']
protected = read('protected-files.json')
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in protected.items())
stages = read('stages.json')
stages = [row for row in stages if row['stage'] != 6]
stages.append({'stage': 6, 'result': '커밋됨', 'commit': 'HEAD(문서 커밋)',
               'new_tests': 0, 'gate': 'gate-final.json',
               'notes': '화면22확인·22캡처, 실제HTTP54행, 문서·보고서'})
(HERE / 'stages.json').write_text(json.dumps(stages, ensure_ascii=False, indent=2) + '\n')

section2 = '''## 2. 단계별 결과

| 단계 | 결과 | 커밋 해시 | 새 시험 수 | 비고 |
|---|---|---|---|---|
| 0 | 준비 완료·커밋 없음 | — | 0 | origin/main 7dc87a9에서 시작, 2f7bb2b 포함 확인 |
'''
for row in stages:
    if row['stage'] == 0:
        continue
    count = row['new_tests']
    count = f"백엔드 {count['backend']}·프런트 {count['frontend']}" if isinstance(count, dict) else str(count)
    section2 += f"| {row['stage']} | {row['result']} | {row['commit']} | {count} | {row['notes']} |\n"
section2 += '\n실패 패치·선행 실패 건너뜀은 없습니다. 6단계는 자기 참조를 피하려고 `HEAD`로 표기합니다. 역할·지역 선택은 로그인 뒤 업무 화면 선택이며 인증 수단이 아닙니다.\n'

section3 = '''## 3. 전체 시험 결과와 익명 기대값 폐기

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
'''
for name in baseline['scenarios']:
    assert name in final['scenarios'] and baseline['scenarios'][name]['exit'] == 0
    section3 += f'| {name} | 통과·실패 0 | 통과·실패 0 |\n'
section3 += '''
새 시험은 백엔드 233개·프런트 4개입니다. 기존 시험 삭제와 통과 수 감소는 없습니다. Python 의존성 경고는 기준선과 같은 엔진 7개·백엔드 9개이며 lint 경고와 구분합니다.

| 파일 | 함수 | 이전 기대값 | 이후 기대값 |
|---|---|---|---|
'''
for row in read('retired-security-tests.json'):
    section3 += f"| `{row['file']}` | `{row['function']}` | {row['before']} | {row['after']} |\n"
section3 += '''
위 두 익명 성공 기대값만 폐기했습니다. 1단계 커밋 본문에 `security: anonymous-access expectations retired`를 넣었습니다. 그 밖의 기존 업무 기대값은 수정하지 않았습니다. 기존 담당자 fixture는 실제 로그인 API로, 직접 DB에 만든 합성 신청 fixture는 명시적 시험 소유권으로 준비했습니다(`authenticated-test-fixtures.json`).

중간 검증에서 기존 P6 S2의 `slowest_upload_ms`가 0ms와 1ms로 달라 반복 비교가 한 번 실패했습니다. 시험·기대값·제품의 시간 측정은 수정하지 않았고 단독 재실행에서 261/0을 확인했습니다. 최종 A→B→C→D는 순서대로 다시 실행해 모두 통과했습니다. 초기 기준선 측정의 임시 공간 부족과 누락된 임시 작업 트리 자원은 별도 재측정으로 분리했습니다. 각 단계 JSON과 원인 기록은 `notes.md`에 남겼습니다.
'''

section4 = f'''## 4. 실제 HTTP 보안 확인 표

분리된 합성 서버에서 요청한 {security['row_count']}개 행입니다. 숫자는 임시 합성 신청·서류 번호입니다. 공개 행은 세 요청 모두 200이며, 개인 신청은 두 비소유자 요청 모두 403, 담당자 경로는 두 무세션 요청 모두 401입니다. v0/v1·범용 경계와 토큰 없는 과거 신청·쿠키 이전·세션 만료·미설정 503은 추가 pytest로 검증했습니다.

| 경로 | 무쿠키 | 남의 쿠키 | 본인/담당자 |
|---|---:|---:|---:|
'''
for row in security['rows']:
    section4 += f"| `{row['method']} {row['path']}` | {row['anonymous']} | {row['other']} | {row['owner_or_officer']} |\n"

section5 = '''## 5. 공고문 분석 측정

| 합성 공고문 항목 | 결과 |
|---|---|
| 제목·신청 기간·안내문 | 추출 성공 |
| 제출 서류 | 기존 슬롯 2종 연결 |
| 나이·도 단위 거주지·발급일·계속 근로 | 기존 규칙 후보 연결 |
| 미지원 봉사활동 기준 | checklist 보존 |
| 모든 초안의 needs_review | true |
| 부정확한 연산·복합·상충 기준 | 수동 확인으로 보존하는 회귀 시험 통과 |
| 합성 서식 PDF | 기존 탐지기로 3칸, 담당자가 수정·확정 |
| templates/hwp의 공고문 PDF | 0개·측정 대상 없음 |

실서류 정확도 수치는 아닙니다. 이미지 공고문·모호한 기간·도 외 시군 조건·미지원 연산은 직접 입력 또는 담당자 확인으로 남습니다. 중위소득은 기존 지원 표와 동일한 140% 표·확정 고지 월이 있어야 기존 규칙에 연결하며, 나머지 표는 체크리스트입니다. 원본 좌표와 기존 판독·판정 코드는 변경하지 않았습니다.
'''

section6 = '''## 6. JBAI 연결 결과

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
'''

section7 = '''## 7. 사람이 아침에 결정할 것

1. 기존 보호 뷰어의 단일 페이지 PDF 최초 표시 문제를 다음 작업에서 수정할지 결정해 주세요. 현재 기존 상세는 확대·축소 후 확인 가능하며 범용 상세는 원본 페이지 이미지로 첫 표시를 보완했습니다.
2. JBAI 공고문 제안을 켤지 결정해 주세요. 기본은 none이며, 켜기 전 실제 JSON schema 호환 여부를 추가 확인할 수 있습니다.
3. 실제 사업의 서식 틀·인용·기준을 담당자가 확인하고, 자동 연결되지 않은 기준의 체크리스트 운영 방식을 확정해 주세요.
'''

section8 = f'''## 8. 화면 검증·보호 확인·알려진 문제

- 브라우저 확인 {len(visual['assertions'])}개·종단 캡처 {len(visual['shots'])}개·페이지 오류 0·강제 목업 API 요청 0입니다. 사업 {visual['posting_id']}, 범용 신청 {visual['application_id']}, 기존 취업패키지 신청 {visual['job_application_id']}는 모두 합성 자료입니다. 범용 게시→신청·제출→목록→상세→원본·체크리스트 확인→최종 선정, 기존 취업패키지의 실제 제출과 기존 상세를 확인했습니다.
- 범용 작성 PDF는 확대 조작 0회로 표시되고 원본 PDF 바이트가 그대로인 것을 확인했습니다. 담당자 표시용 PNG도 세션·사업·신청·서류 경계를 검사합니다.
- 보호 파일 10개는 초기 SHA-256과 같습니다. 기존 상세 원시 픽셀 차이는 {pixel['changed_pixels']:,}개({pixel['changed_percent']:.6f}%)입니다. 바깥 작업 공간의 0.78125px 위치 차이를 정렬한 비교는 {pixel['aligned']['changed_pixels']:,}개({pixel['aligned']['changed_percent']:.6f}%)이며 차이 범위는 문서 탭·도구줄입니다. 남은 차이의 정확한 원인은 확정하지 않았습니다. 두 이미지와 정렬 기록을 모두 보존했습니다. 픽셀 차이 0이라고 보고하지 않습니다.
- 기존 보호 뷰어의 단일 페이지 PDF 최초 빈 화면은 남아 있습니다. 파일을 수정하지 않는 규칙 때문에 기존 상세에는 보완을 넣지 않았으며, 실제 PDF가 확대·축소 뒤 정상 렌더되는 것을 확인했습니다.
- 기존 공개 빈 서식·좌표·HWP 경로는 공개로 유지했습니다. 범용 신청에 고정된 사본의 빈 서식·좌표는 기존 403 계약에 따라 소유자 제한을 유지했습니다.
- 엔진 파일과 기존 규칙 구현은 그대로이며 문서 종류에 수동 기타 서류 항목만 추가했습니다. 불확실·NaN·무한대·boolean 신뢰도는 자동 통과로 쓰지 않습니다. 개인정보 텍스트는 저장 전 가리고, 서명 저장 경로는 보호 URL로 투영합니다.
- 실제 런타임 DB·저장소 초기화·삭제, 실서류·다른 저장소 접근, 실행 설정 파일 수정·복사, push·PR·병합은 하지 않았습니다. 시험 DB·자료는 임시 경로에 만들었습니다. 0단계에는 설정 키 6개의 존재·공란 여부만 기록했고, 연결·비밀 검사에 필요한 값은 읽기만 했습니다.
- 사용자 변경 `.trellis/tasks/11-14-renewal-applicant-design/task.json`과 루트 `logo.png`는 보존하고 모든 커밋에서 제외했습니다. 수동 서버 8010·5183은 종료했습니다. React 개발 모드의 화면 이동 중 취소된 세션·동의 요청은 별도 기록했으며 페이지 오류는 없습니다.

증거: `baseline.json`, `gate-final.json`, `stages.json`, `security-matrix.json`, `analysis-measurements.json`, `jbai-connection.json`, `visual-e2e-result.json`, `visual-pixel-comparison.json`, `protected-files.json`, `bundle-proof.json`. 신청자 정적 번들의 담당자·목업 정적 import와 목업 식별 문자열은 0입니다.

대표 화면: [로그인](shots/officer-login.png), [한 번에 올리기](shots/officer-one-shot-upload.png), [분석 예시](shots/officer-analyzed-preview.png), [편집·확정](shots/officer-editable-preview.png), [신청 접수](shots/applicant-receipt.png), [범용 심사](shots/officer-generic-written-form.png), [기존 심사](shots/job-officer-existing-review-detail.png).
'''

section9 = '''## 9. 아침에 실행할 명령

아래 push·PR·병합 명령은 실행하지 않았습니다. 보고서와 변경을 검토한 뒤 실행합니다.

```bash
git switch feat/renewal-master-2
git status --short
git log --oneline origin/main..HEAD
git push -u origin feat/renewal-master-2
gh pr create --base main --head feat/renewal-master-2 --title "feat: secure program authoring and review" --body-file .trellis/tasks/11-16-renewal-master-2/report.md
# PR 검토 후에만 실행
gh pr merge --merge
```

```bash
source .venv/bin/activate
python -m uvicorn demo.backend.main:app --env-file .env --host 127.0.0.1 --port 8010
```

```bash
cd demo/frontend
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

확인 주소: `http://127.0.0.1:5183/`, `/officer/login`, `/officer/programs/new`, `/officer/programs/<id>`, `/officer/programs/<id>/applications/<appId>`, `/officer?mock=1`, `http://127.0.0.1:8010/docs`.

전체 시험: `.venv/bin/python .trellis/tasks/11-16-renewal-master-2/run_gate.py morning`.
'''

header = '# Renewal master 2 run report\n\n## 1. 한 줄 요약\n\n신청 소유권·담당자 인증, 사업별 심사와 네 칸 공고문 작성, 선택적 JBAI 제안을 구현하고 합성 종단·보안·전체 회귀를 검증했습니다.\n\n'
sections = [section2, section3, section4, section5, section6, section7, section8, section9]
(HERE / 'report.md').write_text(header + '\n'.join(sections))
(HERE / 'final-response.md').write_text('\n'.join([section2, section3, section4, section6, section7]))
task = read('task.json')
task['status'] = 'completed'
task['completedAt'] = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
task['notes'] = 'Requested report path retained; five feature commits plus final report commit. No remote publication.'
(HERE / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n')
print('Report and requested final-response sections written')
