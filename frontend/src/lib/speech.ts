// Text helpers for reading answers aloud (kept free of DOM APIs so they are unit tested).

/** Plain speakable text: no citation markers, markdown or bullet symbols. */
export function speakable(text: string): string {
  return text
    .replace(/\s*[[【]\s*(?:\*\*)?\s*S\d+[^\]】]*[\]】]/g, '')
    .replace(/\*\*/g, '')
    .replace(/^\s*(?:[-*•]|\d+\.)\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}
