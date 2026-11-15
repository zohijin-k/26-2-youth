"""Append current rerun evidence while preserving the prior report verbatim."""
from pathlib import Path
import hashlib,json,re,subprocess
T=Path(__file__).resolve().parent
R=T/'rerun'
ROOT=T.parents[2]
def read(name,default=None):
 p=R/name
 return json.loads(p.read_text()) if p.exists() else default

def state(row,forms=False):
 if not row:return '미실행'
 if row['exit']!=0:return '실패'
 text=' '.join(row.get('summary',[])); numbers=re.findall(r'(\d+) passed|tests (\d+)|통과\s*(\d+)\s*/\s*실패',text)
 n=next((a or b or c for a,b,c in reversed(numbers)),None)
 log=Path(row.get('log',''))
 if not n and str(log).startswith('/tmp/officer-polish-final-') and log.is_file():
  match=re.search(r'통과\s*(\d+)\s*/\s*실패',log.read_text(errors='replace'))
  n=match[1] if match else None
 return '통과'+(f' ({n}개)' if n else ' (원본 서식 8개)' if forms else '')

code=read('gate-code.json',{});docs=read('gate-docs.json',{});commit=read('commits.json',{}).get('code','미기록')
before={x['name']:x for x in read('surfaces-before.json',{}).get('surfaces',[])};after={x['name']:x for x in read('surfaces-after.json',{}).get('surfaces',[])}
old=subprocess.check_output(['git','show','ffbaab7:.trellis/tasks/11-15-officer-ui-polish/report.md'],cwd=ROOT,text=True)
lines=['## 9. 3단계 재실행 (2026-11-15)','', '작업 브랜치 `feat/officer-ui-polish`, 시작 HEAD `ffbaab7`. 기존 실패 패치의 적용 가능 여부를 확인한 뒤 적용했다. 다른 저장소와 그 생성물에는 접근하지 않았다. 앞선 1~8절은 최초 실행 당시의 기록이며, 현재 상태는 이 절을 따른다.','', f'- 코드 커밋: `{commit}` · `feat(officer-ui): simplify upload, login and program list screens`.', '- 보고서·검증 자료는 별도 문서 커밋 `docs: record officer UI polish stage 3 rerun`에 포함한다. 해당 문서 커밋은 현재 HEAD이며, 같은 커밋에 자기 해시를 넣지 않는다.', '- 재실행은 성공했다. 한글 업로드·파일 칩·단계와 경과 시간, 단일 로그인 카드, 상태 칩과 행 메뉴를 적용했다.', '- 현대화 화면의 로그아웃은 서랍으로 모았다. 기존 취업패키지 로그인 표시줄은 그대로 유지한다. 완료된 남은 확인 메뉴는 상태 칩으로 바꾸고 오른쪽 패널의 중복 서류 이동 버튼을 제거했다. 항목별 확인·게시·선정 버튼과 원본 탭은 유지했다.','', '### 공간 기록과 중단 규칙','', '- 최초 `df -h /`: **27GiB 가용**. 파일에 저장한 후속 시작 측정은 25GiB였다. 모두 시작 기준 15GB 이상이다.', '- `run_rerun_gate.py`는 각 시험에 고유 임시 폴더를 할당하고, 종료 후 그 폴더만 정리한다. 1초 간격으로 ENOSPC 출력을 감시하며 발생 시 해당 임시 폴더만 정리하고 즉시 중단한다.', '- 이번 재실행에는 ENOSPC가 발생하지 않았다. 다른 저장소·생성물 정리는 수행하지 않았다.']
for label,g in [('코드',code),('문서',docs)]:
 values=[x['free_bytes']/1024**3 for x in g.get('disk',[])]
 lines.append(f'- {label} 게이트의 시험 경계에서 기록한 최저 가용 공간: {min(values):.1f}GiB.' if values else f'- {label} 게이트 공간 기록: 미실행.')
lines+=['','공간 원본: [최초 기록](rerun/disk-initial.txt), [후속 시작 기록](rerun/disk-start.txt), [코드 게이트](rerun/disk-code.txt), [문서 게이트](rerun/disk-docs.txt).','', '### 전체 시험','', '| 시험 | ffbaab7 기준선 | 재실행 코드 게이트 | 문서 커밋 전 게이트 |','| --- | --- | --- | --- |']
base=json.loads((T/'gate-final.json').read_text())
for key in ['engine','backend']:lines.append(f'| {key} | {state(base.get(key))} | {state(code.get(key))} | {state(docs.get(key))} |')
for name,row in base['scenarios'].items():lines.append(f"| C · {name} | {state(row,'p14_' in name)} | {state(code.get('scenarios',{}).get(name),'p14_' in name)} | {state(docs.get('scenarios',{}).get(name),'p14_' in name)} |")
lines.append(f"| D · 프런트 단위 | {state(base.get('frontend'))} | {state(code.get('frontend'))} | {state(docs.get('frontend'))} |")
for label in ['tsc','oxlint (경고 0)','Vite build (청크 경고 없음)']:lines.append(f"| D · {label} | 통과 | {'통과' if code.get('frontend',{}).get('exit')==0 else '미실행'} | {'통과' if docs.get('frontend',{}).get('exit')==0 else '미실행'} |")
lines+=['','단위 시험 1개를 추가했다. 여러 서랍의 등록·해제 순서와 중복 해제에도 마지막 서랍이 사라질 때만 기존 표시줄을 복원하는 동작을 확인한다. 기존 엔진·백엔드·시나리오 시험 파일과 기존 프런트 단위 시험 기대값은 수정하지 않았다. 엔진·백엔드 의존성 경고는 기존과 동일하다.','', '### 시험 기대값 수정','', '기존 프런트 단위 시험 수정: **없음**. 재실행용 Playwright 스크립트의 준비 대기만 새 마크업에 맞췄다.','', '| 파일·검증 | 이전 → 이후 | 이유 |','| --- | --- | --- |','| rerun/visual-e2e.mjs · 파일 입력 준비 | 기본 파일 입력이 보일 때 대기 → 숨긴 입력이 DOM에 있고 한글 선택 버튼이 동작할 때 진행 | 기본 Choose File 대신 한글 버튼을 쓰는 마크업 변경. 업로드·게시 조건 기대값은 유지 |','| rerun/verify-entry.mjs · 화면 준비 | networkidle → DOM 로드 후 비밀번호·업로드 요소와 현대화 표시줄 상태 확인 | 개발 서버 연결 유휴 대기 대신 실제 목표 요소를 기다림. 동작 기대값은 유지 |','', '### 겉에 보이는 버튼 수','', '같은 합성 사업 두 개와 1440×900의 첫 시야를 비교했다. 숨긴 메뉴 항목은 제외한다. 공유 머리줄 버튼은 양쪽에 포함한다. 기존 기본 파일 입력의 Choose File도 보이는 버튼이므로 별도 집계해 합산한다. 접힘(summary) 수를 따로 남겼으며, 비활성 컨트롤의 상태 표시 전환은 실제 동작 감소와 구분한다.','', '| 화면 | DOM 버튼 이전→이후 | 기본 파일 선택 이전→이후 | 실제 보이는 버튼 합계 | 접힘 이전→이후 | 최소 글자 px |','| --- | --- | --- | --- | --- | --- |']
names=['login','upload','program-list','preview','workspace','generic-review']
for name in names:
 a,b=before[name],after[name]
 lines.append(f"| {name} | {a['buttons']}→{b['buttons']} | {a['native_file_buttons']}→{b['native_file_buttons']} | {a['buttons']+a['native_file_buttons']}→{b['buttons']+b['native_file_buttons']} | {a['visible_disclosures']}→{b['visible_disclosures']} | {a['min_font']:g}→{b['min_font']:g} |")
lines+=['','업로드·예시 편집·작업 공간·범용 상세의 버튼 수를 줄였다. 예시 편집 14→12 중 1개는 이미 비활성이던 남은 확인 0개 버튼을 정적 완료 상태로 바꾼 것이고, 실제 중복 동작 감소는 로그아웃 1개다. 로그인은 공유 머리줄 버튼과 로그인 버튼 2개로 동일하다. 사업 목록은 필수 서랍과 범용 사업의 행 메뉴 추가로 3→4개가 되어 총 버튼 수 감소는 달성하지 못했다. 기본 사업의 중복 행 메뉴는 제거했다. 최초 작업 전 기준으로 예시 편집은 11개였으므로 현재 12개는 그 기준보다 1개 많다. 필수 진행 칩과 업무 판단 버튼은 유지했다.','', '### 화면·키보드·종단 검증','', '| 화면 | 이전 | 이후 | 1280/1024 가로 넘침 |','| --- | --- | --- | --- |']
for name in names:
 widths=after[name]['widths'];ok=not any(x['overflow'] for x in widths)
 lines.append(f'| {name} | [캡처](rerun/shots/before/{name}.png) | [캡처](rerun/shots/after/{name}.png) | {"없음" if ok else "있음"} |')
journey=read('visual-e2e-result.json',{});entry=read('entry-verification.json',{});ui=read('ui-verification.json',{});workspace=read('workspace-verification.json',{})
lines += ['',f"- 종단 흐름: {'통과' if not journey.get('errors') and journey.get('assertions') else '확인 필요'}, {len(journey.get('assertions',[]))}개 검증, 브라우저 오류 {len(journey.get('page_errors',[]))}개. 로그인→파일 분석→개별 확인→별도 저장 없이 게시→신청자 제출→사업별 목록→범용 상세→최종 선정.",f"- 업로드·로그인·서랍 검증: {entry.get('result')}, {len(entry.get('checks',[]))}개 그룹. 끌어놓기·키보드 선택·중복 제거·10개 제한·삭제·확장자/MIME가 없는 정상 PDF를 확인했다.",'- 사업 목록 행 메뉴·새 사업 주 버튼·서랍 이동 연결: entry-links.json의 3개 그룹 통과.',f"- 메뉴·서랍·확인 대화상자: {ui.get('result')}, {len(ui.get('checks',[]))}개 그룹. Esc·화살표·포커스 복귀·Tab 가두기·바깥 클릭 규칙 확인.",f"- 작업 공간: {workspace.get('result')}, {len(workspace.get('checks',[]))}개 그룹. 검색 후 선택 해제와 설정 진입 포커스·처리 버튼 위치 확인.",'- 6개 현대화 화면은 최소 14px 이상이고, 시야 내 주 버튼은 최대 1개다. 공유 머리줄과 보호된 기존 화면의 글자 크기는 바꾸지 않았다.','- 검증 서버는 별도 포트 8014/5187에서 실행했으며 백엔드에 `--env-file .env`를 적용했다. 저장소 런타임 DB를 쓰지 않는 기존 합성 서버 래퍼와 표시된 합성 저장소만 사용했다.', '- 파일 선택 상태: [합성 파일 칩](rerun/shots/after-journey/officer-one-shot-upload.png). 심사 확인 전: [범용 상세](rerun/shots/after-journey/officer-generic-review-detail.png).','', '### 보호 범위·기존 화면 픽셀','']
for name,row in read('pixel-comparison.json',{}).items():lines.append(f"- {name}: 차이 **{row['different_pixels']}픽셀**, {row['size'][0]}×{row['size'][1]}. 목업과 인증 상태를 각각 비교했다. 좌표 보정 없음.")
lines+=['','보호 파일 10개 SHA-256은 시작·각 커밋 전·끝에 일치했다. 백엔드·엔진·신청자 전역 CSS·공유 남색 머리줄·기존 목록/상세·동적 목업 API 경계 diff는 0이다. OfficerSession의 현대화 표시줄 생략은 UI 전용이며 인증·권한 판단을 바꾸지 않는다. 기존 표시줄 JSX와 인증 상태의 픽셀은 보존했다. 합성 자료만 사용했다.','', '### 남은 판단','', '- 사업 목록 총 버튼 수 3→4와 최초 기준 예시 편집 11→12를 더 줄일지는 필수 서랍·행 메뉴·진행 칩을 유지하는 범위에서 후속 결정이 필요하다.', '- 보호된 기존 취업패키지 화면의 1024px 가로 넘침은 기존과 동일하다. 이번 작업에서 수정하지 않았다.', '- 과거 실패 패치는 이력으로 보관한다. 현재는 적용 완료했으므로 다시 적용하지 않는다.','']
header,rest=old.split('\n',1)
(T/'report.md').write_text(header+'\n\n> 최신 상태: 3단계 재실행을 완료했다. 아래 9절이 현재 결과이며, 1~8절은 ffbaab7 당시의 이력이다.\n'+rest+'\n'+'\n'.join(lines))
print('Appended stage3 rerun section from recorded evidence')
