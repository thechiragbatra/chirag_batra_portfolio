// How busy the site is right now (a deploy streaming, Smith thinking), from 0 to 1. The
// background shader reads it every frame, so it is a plain store, not React state.

const levels = new Map<string, number>()

/** Report a source's activity (0 = idle). The background follows the busiest source. */
export function setActivity(source: string, level: number) {
  if (level <= 0) levels.delete(source)
  else levels.set(source, Math.min(1, level))
}

export function activityLevel(): number {
  let max = 0
  for (const level of levels.values()) max = Math.max(max, level)
  return max
}
