export type Segment = { kind: "text"; value: string } | { kind: "code"; language: string; code: string };

// ```lang <newline> code <newline> ```   (the language tag is optional)
const FENCE_RE = /```([^\n`]*)\n?([\s\S]*?)\n?```/g;

/** Split question/option text into prose and fenced code blocks (an unclosed fence stays prose). */
export function splitSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(FENCE_RE)) {
    const index = match.index ?? 0;
    if (index > last) segments.push({ kind: "text", value: text.slice(last, index) });
    segments.push({ kind: "code", language: match[1].trim().split(/\s+/)[0] ?? "", code: match[2] });
    last = index + match[0].length;
  }
  if (last < text.length) segments.push({ kind: "text", value: text.slice(last) });
  return segments;
}
