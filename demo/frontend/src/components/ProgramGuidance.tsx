/** Shared applicant-facing paragraphs, also shown in the officer preview. */
export default function ProgramGuidance({ text }: { text: string }) {
  const paragraphs = text.split(/\n\s*\n/).map((value) => value.trim()).filter(Boolean)
  return <div className="pinfo__guidance">{paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>
}
