import type { FileKind } from './file-precheck.ts'

export interface Observation { kind: FileKind; pages: number; ms: number }
/** Use only measurements from this visit. The first file has no invented estimate. */
export function estimateSeconds(kind: FileKind, pages: number | null, history: readonly Observation[]): number | null {
  const samples = history.filter((entry) => entry.kind === kind && Number.isFinite(entry.ms) && entry.ms > 0 && entry.pages > 0)
  if (!samples.length) return null
  const perPage = samples.reduce((total, entry) => total + entry.ms / entry.pages, 0) / samples.length
  return Math.max(1, Math.round(perPage * Math.max(1, pages ?? 1) / 1000))
}
export function slowThresholdSec(estimate: number | null): number { return estimate === null ? 10 : Math.min(10, estimate * 1.5) }
export function rememberObservation(history: readonly Observation[], entry: Observation): Observation[] { return [...history, entry].slice(-20) }
