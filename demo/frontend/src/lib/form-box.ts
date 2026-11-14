/** PDF-point geometry shared by the officer template editor and its preview. */
export type PdfBox = [number, number, number, number]
export interface PageSize { width: number; height: number }
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value))

export function boundedBox(box: PdfBox, page: PageSize): PdfBox {
  const width = Math.max(0.1, page.width)
  const height = Math.max(0.1, page.height)
  const x0 = clamp(Math.min(box[0], box[2]), 0, width - 0.1)
  const y0 = clamp(Math.min(box[1], box[3]), 0, height - 0.1)
  const x1 = clamp(Math.max(box[0], box[2]), x0 + 0.1, width)
  const y1 = clamp(Math.max(box[1], box[3]), y0 + 0.1, height)
  return [x0, y0, x1, y1]
}

export function movedBox(box: PdfBox, dx: number, dy: number, page: PageSize): PdfBox {
  const safe = boundedBox(box, page)
  const width = safe[2] - safe[0]
  const height = safe[3] - safe[1]
  const x = clamp(safe[0] + dx, 0, page.width - width)
  const y = clamp(safe[1] + dy, 0, page.height - height)
  return [x, y, x + width, y + height]
}

export function boxPercent(box: PdfBox, page: PageSize) {
  return { left: `${box[0] / page.width * 100}%`, top: `${box[1] / page.height * 100}%`,
    width: `${(box[2] - box[0]) / page.width * 100}%`, height: `${(box[3] - box[1]) / page.height * 100}%` }
}
