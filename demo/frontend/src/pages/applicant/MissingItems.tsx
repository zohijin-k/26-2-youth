/**
 * 아직 제출할 수 없을 때 남은 항목을 단계별로 묶어 보여 준다.
 * 서류 업로드에서 "제출 전 최종 확인"을 눌렀을 때와, 확인 및 제출에서 제출을 눌렀을 때 같은 모양으로 쓴다.
 * 판단은 서버의 final-check 결과(blockers)만 따른다.
 */
import type { Blocker } from '../../api.ts'
import Notice from '../../components/Notice.tsx'

/** 남은 항목을 고치는 화면. 순서는 신청 순서대로. */
export type ApplicantStage = 'identity' | 'forms' | 'subsidy' | 'upload'

const BLOCKER_GROUPS: { goto: ApplicantStage; title: string; action: string }[] = [
  { goto: 'identity', title: '본인인증', action: '본인인증으로' },
  { goto: 'forms', title: '신청 서식', action: '서식 작성으로' },
  { goto: 'subsidy', title: '지원 항목', action: '지원 항목으로' },
  { goto: 'upload', title: '서류', action: '서류 업로드로' },
]

function applicantStage(goto: Blocker['goto']): ApplicantStage {
  return goto === 'form1' || goto === 'consent' ? 'forms' : goto
}

function itemText(blocker: Blocker): string {
  // 서류는 서버 문구에 서류 이름과 이유(미제출·부적합 사유)가 함께 들어 있다.
  if (blocker.kind === 'document' || blocker.kind === 'eligibility') return blocker.kind === 'eligibility' ? `${blocker.label}: ${blocker.message}` : blocker.message
  return blocker.label
}

export default function MissingItems({ id, title, blockers, current, onGoto }: {
  id: string
  title: string
  blockers: Blocker[]
  /** 지금 화면. 같은 화면으로 가는 버튼 대신 해당 칸으로 바로 옮기는 링크를 준다. */
  current?: ApplicantStage
  onGoto: (stage: ApplicantStage) => void
}) {
  return (
    <Notice id={id} tabIndex={-1} tone="danger" role="alert" title={title} className="missing">
      {blockers.length === 0 ? (
        <p>지금은 제출할 수 없습니다. 잠시 뒤 다시 시도해 주세요.</p>
      ) : (
        <ul className="missing__groups">
          {BLOCKER_GROUPS.map((group) => {
            const items = blockers.filter((blocker) => applicantStage(blocker.goto) === group.goto)
            if (items.length === 0) return null
            return (
              <li key={group.goto}>
                <div className="missing__row">
                  <span className="missing__title">{group.title} <span className="missing__count">{items.length}개 남음</span></span>
                  {group.goto !== current && (
                    <button type="button" className="btn btn--small" onClick={() => onGoto(group.goto)}>{group.action}</button>
                  )}
                </div>
                <ul className="missing__items">
                  {items.map((blocker) => (
                    <li key={`${blocker.kind}-${blocker.target}`}>
                      {group.goto === current && blocker.kind === 'document'
                        ? <a className="link" href={`#slot-${blocker.target}`}>{itemText(blocker)}</a>
                        : itemText(blocker)}
                    </li>
                  ))}
                </ul>
              </li>
            )
          })}
        </ul>
      )}
    </Notice>
  )
}
