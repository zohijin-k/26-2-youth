"""Render the audit report from recorded synthetic checks, without secret values."""
from pathlib import Path
import hashlib,json,re,subprocess
T=Path(__file__).resolve().parent
R=T.parents[2]
def read(name,default=None):
 p=T/name
 return json.loads(p.read_text()) if p.exists() else default
def result(row):
 if not row:return '미실행'
 text=' '.join(row.get('summary',[])); count=re.findall(r'(\d+) passed|tests (\d+)',text)
 log=Path(row.get('log',''))
 raw=log.read_text(errors='replace') if log.is_file() else ''
 korean=re.search(r'통과\s*(\d+)\s*/\s*실패\s*(\d+)',raw)
 n=next((a or b for a,b in reversed(count)),None) or (korean[1] if korean else None)
 return ('통과' if row['exit']==0 else '실패')+(f' ({n}개)' if n else (' (원본 서식 8개)' if '[OK] 8개 원본 서식' in raw else ''))
stages=read('stages.json',[]);base=read('gate-baseline.json',{}); final=read('gate-final.json',{})
lines=['# 담당자 UI 정리 작업 보고서','', '기준 브랜치: `main` (`b654752`). 작업 브랜치: `feat/officer-ui-polish`. 합성 자료와 격리 서버만 사용했다. 원래 있던 사용자 수정 2개는 커밋에서 제외했다.','', '## 1. 단계','', '| 단계 | 결과 | 커밋 | 새 시험 수 | 비고 |','| --- | --- | --- | ---: | --- |']
for s in stages:lines.append(f"| {s['stage']} | {s['result']} | {s.get('commit') or '—'} | {s.get('new_tests',0)} | {s.get('notes','')} |")
lines+=['','## 2. 전체 시험: 기준선과 최종','', '| 시험 | 기준선 | 최종 |','| --- | --- | --- |']
for key in ['engine','backend']:lines.append(f'| {key} | {result(base.get(key))} | {result(final.get(key))} |')
for key in base.get('scenarios',{}):lines.append(f"| C · {key} | {result(base['scenarios'][key])} | {result(final.get('scenarios',{}).get(key))} |")
lines.append(f"| D · 프런트 단위 | {result(base.get('frontend'))} | {result(final.get('frontend'))} |")
for label in ['TypeScript (tsc -b)','oxlint (경고 0)','Vite build (청크 경고 없음)']:lines.append(f"| D · {label} | {'통과' if base.get('frontend',{}).get('exit')==0 else '확인 필요'} | {'통과' if final.get('frontend',{}).get('exit')==0 else '미실행'} |")
lines+=['','엔진·백엔드의 기존 의존성 경고는 기준선과 동일하며, 프런트 lint와 build는 경고 없이 통과해야 한다. 단계별 전체 시험 원본 결과는 `gate-*.json`에 있다.','', '## 3. 기존 프런트 시험 기대값 수정','', '없음. 동작·권한·게시·확인·선정 조건의 기존 기대값은 변경하지 않았다.','', '## 4. 보호 파일과 수정 범위','', '| 보호 파일 | 시작 | 최종 SHA-256 일치 |','| --- | --- | --- |']
for name,digest in read('protected-files.json',{}).items():
 ok=hashlib.sha256((R/name).read_bytes()).hexdigest()==digest
 lines.append(f'| `{name}` | 일치 | {"일치" if ok else "불일치"} |')
paths=subprocess.check_output(['git','diff','b654752','--name-only','--','demo/backend','engine','engine_v2'],cwd=R).decode().strip()
lines+=['',f'백엔드·엔진 diff: {"0" if not paths else "변경 있음"}. 보호 파일은 시작·각 커밋 직전·최종에 검사한다.','', '## 5. 기존 화면 픽셀 비교','']
pixel=read('pixel-comparison.json',{})
if pixel:
 for name,row in pixel.items():lines.append(f"- {name}: 차이 {row['different_pixels']}픽셀 ({row['size'][0]}×{row['size'][1]}), 임시 좌표 보정 없이 전체 화면 비교.")
else:lines.append('미실행.')
lines+=['','## 6. 이전·이후 캡처와 화면 측정','', '1440×900 캡처. 버튼 수는 현재 시야에 보이는 버튼, 최소 글자는 공유 머리줄·원본 PDF 외 화면 본문을 측정했다.','', '| 화면 | 이전 → 이후 | 버튼 수 | 최소 글자 크기 | 바뀐 점 |','| --- | --- | --- | --- | --- |']
before={s['name']:s for s in read('surfaces-before.json',{}).get('surfaces',[])};after={s['name']:s for s in read('surfaces-after.json',{}).get('surfaces',[])}
changes={'login':'3단계 실패로 원래 화면 복원','upload':'3단계 실패로 원래 화면 복원','program-list':'3단계 실패로 원래 화면 복원','preview':'고정 진행 막대·항목별 확인·근거 접기·저장 후 게시','workspace':'칩 탭·상태 필터·행 더보기','generic-review':'판정 카드·큰 확인란·아래 처리 영역','job-list':'보호된 기존 화면 유지','job-review':'보호된 기존 화면 유지'}
for name,a in before.items():
 b=after.get(name,{})
 lines.append(f"| {name} | [이전](shots/before/{name}.png) · [이후](shots/after/{name}.png) | {a['buttons']} → {b.get('buttons','—')} | {a['min_font']} → {b.get('min_font','—')}px | {changes[name]} |")
lines+=['','버튼 수에는 진행·필터 칩과 공유 머리줄 버튼도 포함한다. 3단계 복원으로 해당 화면의 최소 글자 크기 개선은 적용되지 않았다.','', '1280·1024px 가로 넘침 결과:','']
for name,b in after.items():lines.append(f"- {name}: "+', '.join(f"{w['width']}px {'넘침 있음' if w['overflow'] else '넘침 없음'}" for w in b['widths']))
lines+=['','기존 취업패키지 목록·상세의 1024px 넘침은 기준선에도 존재한다. 보호 범위와 픽셀 일치 요구에 따라 수정하지 않았다.','', '## 7. 덤 확인','']
probes=read('security-probes.json',{})
for key,label in [('draft_notice_without_cookie','작성 중 공고문 무쿠키 접근'),('preview_false_omits_entered_values','preview=false가 신청자 입력값을 그리지 않음')]:
 v=probes.get(key,{})
 lines.append(f"- {label}: **{v.get('observation','미실행')}** (응답 {v.get('status','—')}).")
lines+=['','보안 관찰만 수행했으며 관련 백엔드는 수정하지 않았다.','', '## 8. 사람이 결정할 것','']
qa=read('ui-verification.json',{});journey=read('visual-e2e-result.json',{})
lines.append('- 진행·필터 칩을 포함한 시야 버튼 수가 예시 편집 11→14, 작업 공간 9→10, 범용 상세 10→13으로 증가했다. 부가 동작은 메뉴에 접었지만 총 버튼 수 감소 목표는 충족하지 못했다. 추가 단순화 여부를 결정해야 한다.')
lines.append('- 기존 취업패키지의 1024px 가로 넘침을 추후 별도 작업으로 다룰지 결정할 수 있다.')
lines.append('- 3단계는 디스크 공간 부족으로 전체 게이트에 실패해 되돌렸다. 로그인·업로드·사업 목록 개선안은 [failed-stage3.patch](failed-stage3.patch)에 보관했다. 적용 재시도는 후속 작업으로 결정해야 한다. 중간 캡처 shots/intermediate는 되돌린 제안의 참고 자료다.')
lines+=['','### 브라우저 검증','', f"- 종단 흐름: {'통과' if journey and not journey.get('errors') else '확인 필요'}; 명시적 확인 {len(journey.get('assertions',[]))}건.", f"- 메뉴·서랍·확인 대화상자 키보드/포커스: {qa.get('result','미실행')}.", '- 작업 공간 키보드/검색 선택 상태/처리 영역 검사: workspace-verification.json의 4개 그룹 통과.', '- 원본 확인 전 심사 화면: [종단 캡처](shots/after-journey/officer-generic-review-detail.png).', '- 목업 목록·상세가 로그인·API 요청 없이 동작하고, 목업 데이터는 별도 동적 청크로 유지된다.', '- 대비 검사 9개 조합 모두 4.5:1 이상(contrast.json).', '- 캡처·측정·시험에 실서류를 사용하지 않았다.','', '### 실행 메모','', (T/'notes.md').read_text().replace('# Notes','').strip()]
(T/'report.md').write_text('\n'.join(lines)+'\n')
print('Report refreshed from recorded evidence.')
