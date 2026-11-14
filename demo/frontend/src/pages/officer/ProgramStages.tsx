const STAGES = ['① 기본 정보', '② 서식 틀', '③ 안내 메시지', '④ 미리보기·게시']

export default function ProgramStages({ current = 0, onChange }: { current?: number; onChange?: (index: number) => void }) {
  return <ol className="managed-program__steps" aria-label="사업 올리기 단계">
    {STAGES.map((label, index) => <li key={label} aria-current={index === current ? 'step' : undefined}>
      {onChange ? <button type="button" onClick={() => onChange(index)} aria-current={index === current ? 'step' : undefined}>{label}</button>
        : <span aria-disabled={index > 0 || undefined}>{label}</span>}
    </li>)}
  </ol>
}
