/** 반려 안내문 만들기. 반려 페이지와 단위 시험이 같이 쓴다. */
import type { ApplicationReasons } from '../../api.ts'

export const NOTICE_MAX = 2000
export const NOTICE_INTRO = '제출하신 신청이 아래 사유로 반려되었습니다.'

/** 이 건의 확인 필요 항목을 신청자에게 보일 문장 하나씩으로 바꾼다. */
export function reasonLines(reasons: ApplicationReasons, extra: string[] = []): string[] {
  const lines = reasons.documents.flatMap((doc) => doc.findings.length
    ? doc.findings.map((finding) => `${doc.label}: ${finding.message}`)
    : [`${doc.label}: 서류를 다시 확인해 주세요.`])
  lines.push(...reasons.missing.map((doc) => `${doc.label}: 필수 서류가 제출되지 않았습니다.`), ...extra)
  return [...new Set(lines.map((line) => line.replace(/\s+/g, ' ').trim()).filter(Boolean))]
}

/** 고른 사유를 안내문에 넣거나 뺀다. 담당자가 손으로 고친 다른 줄은 그대로 둔다. */
export function toggleReason(notice: string, reason: string, on: boolean): string {
  const line = `- ${reason}`
  const lines = notice.split('\n')
  if (!on) return lines.filter((value) => value !== line).join('\n')
  if (lines.includes(line)) return notice
  const base = notice.trim() ? notice.replace(/\s+$/, '') : NOTICE_INTRO
  return `${base}\n${line}`
}
