/** Only server-provided receipt text is retained across same-tab refreshes. */
export function readReceiptSteps(raw: string | null): string[] {
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) && parsed.every((item) => typeof item === 'string') ? parsed : []
  } catch { return [] }
}
