/** Publication always checks the server state after persisting the reviewed draft. */
export async function publishReviewedProgram<T extends { publish_blockers?: string[] }>(operations: {
  save: () => Promise<unknown>
  refresh: () => Promise<T>
  publish: () => Promise<unknown>
  isCurrent?: () => boolean
}): Promise<{ published: boolean; data: T; blockers: string[] }> {
  await operations.save()
  if (operations.isCurrent?.() === false) throw new DOMException('작업 화면이 닫혔습니다.', 'AbortError')
  const data = await operations.refresh()
  if (operations.isCurrent?.() === false) throw new DOMException('작업 화면이 닫혔습니다.', 'AbortError')
  const raw = data.publish_blockers
  const blockers = Array.isArray(raw) && raw.every((reason) => typeof reason === 'string')
    ? raw : ['게시 조건을 확인하지 못했습니다. 다시 시도해 주세요.']
  if (blockers.length) return { published: false, data, blockers }
  await operations.publish()
  return { published: true, data, blockers: [] }
}
