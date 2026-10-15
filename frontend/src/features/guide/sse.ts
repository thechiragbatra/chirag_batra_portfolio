// Server-sent events over fetch: EventSource cannot POST, so the guide parses the stream itself.

/** Split an SSE byte stream into the JSON payloads of its `data:` lines. */
export function parseSse<T = unknown>(buffer: string): { events: T[]; rest: string } {
  const events: T[] = []
  const blocks = buffer.split('\n\n')
  const rest = blocks.pop() ?? ''
  for (const block of blocks) {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n')
    if (data) events.push(JSON.parse(data) as T)
  }
  return { events, rest }
}
