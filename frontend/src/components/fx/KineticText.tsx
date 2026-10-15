/**
 * A headline whose letters (or whole words) rise into place one after another. Screen readers
 * get the plain text; the animated pieces are hidden from them. Reduced motion shows the text
 * at once (the global reduced-motion rule shortens every animation).
 *
 * Use by="word" with a gradient class: background-clip text cannot reach letters that are
 * transformed separately, so a gradient word must move as one piece.
 */
export function KineticText({
  text,
  delay = 0,
  stagger = 28,
  by = 'char',
  unitClassName = '',
}: {
  text: string
  delay?: number
  stagger?: number
  by?: 'char' | 'word'
  unitClassName?: string
}) {
  let index = 0
  const unit = (content: string) => (
    <span key={index} className={`kinetic-char ${unitClassName}`} style={{ animationDelay: `${delay + index++ * stagger}ms` }}>
      {content}
    </span>
  )
  return (
    <span className="inline-block">
      <span className="sr-only">{text}</span>
      {text.split(' ').map((word, w, words) => (
        <span key={w} aria-hidden className="inline-block overflow-hidden pb-[0.1em] align-bottom whitespace-nowrap">
          {by === 'word' ? unit(word) : [...word].map((char) => unit(char))}
          {w < words.length - 1 && <span className="inline-block">&nbsp;</span>}
        </span>
      ))}
    </span>
  )
}
