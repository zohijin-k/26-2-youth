/** Parse only paired bold markers; all content stays plain React text. */
export function splitEmphasis(text: string): { text: string; strong: boolean }[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part) => {
    const strong = part.startsWith('**') && part.endsWith('**') && part.length > 4
    return { text: strong ? part.slice(2, -2) : part, strong }
  })
}
