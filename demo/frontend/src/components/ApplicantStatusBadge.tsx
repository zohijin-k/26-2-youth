import type { DocStatus } from '../api.ts'
import Icon, { type IconName } from './Icon.tsx'
const PRESENTATION: Record<DocStatus, {label: string; icon: IconName; tone: string}> = {
  PASS: { label: '확인 완료', icon: 'checkCircle', tone: 'success' },
  FAIL: { label: '다시 올려 주세요', icon: 'refresh', tone: 'danger' },
  NEEDS_REVIEW: { label: '담당자 확인 예정', icon: 'info', tone: 'warning' },
}
export default function ApplicantStatusBadge({status}: {status: DocStatus; audience?: 'applicant'}) {
  const item = PRESENTATION[status]
  return <span className={`badge badge--${item.tone}`}><Icon name={item.icon} size={16} />{item.label}</span>
}
