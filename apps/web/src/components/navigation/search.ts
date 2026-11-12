import type { SearchEntry } from "@/components/navigation/access";

export interface SearchResult {
  entry: SearchEntry;
  score: number;
  /** [start, end) ranges of the label that matched the query, for highlighting */
  ranges: [number, number][];
}

const normalise = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");

/** Where each word of the query matches the text, as ranges; null when any word is missing. */
function matchRanges(text: string, words: string[]): [number, number][] | null {
  const lower = normalise(text);
  const ranges: [number, number][] = [];
  for (const w of words) {
    const at = lower.indexOf(w);
    if (at < 0) return null;
    ranges.push([at, at + w.length]);
  }
  return ranges.sort((a, b) => a[0] - b[0]);
}

function score(label: string, group: string, keywords: string[], query: string, words: string[]): { score: number; ranges: [number, number][] } | null {
  const l = normalise(label);
  const inLabel = matchRanges(label, words);
  if (l === query) return { score: 100, ranges: [[0, label.length]] };
  if (l.startsWith(query)) return { score: 90, ranges: [[0, query.length]] };
  if (inLabel && l.split(/[\s&/-]+/).some((w) => w.startsWith(words[0]))) return { score: 75, ranges: inLabel };
  if (inLabel) return { score: 60, ranges: inLabel };
  const g = normalise(group);
  // every word is found somewhere in the label, the group or the keywords
  const haystack = `${l} ${g} ${keywords.map(normalise).join(" ")}`;
  if (words.every((w) => haystack.includes(w))) {
    const inKeyword = keywords.some((k) => normalise(k).includes(query));
    return { score: inKeyword ? 50 : 40, ranges: matchRanges(label, words.filter((w) => l.includes(w))) ?? [] };
  }
  return null;
}

/** Instant, local search over the entries a user may open. Ordered by how well they match, then by menu order; at most `limit` results. */
export function searchNav(entries: SearchEntry[], rawQuery: string, limit = 12): SearchResult[] {
  const query = normalise(rawQuery.trim());
  if (!query) return [];
  const words = query.split(/\s+/).filter(Boolean);
  const results: (SearchResult & { order: number })[] = [];
  entries.forEach((entry, order) => {
    const hit = score(entry.item.label, entry.groupTitle ?? "", entry.item.keywords ?? [], query, words);
    if (hit) results.push({ entry, score: hit.score, ranges: hit.ranges, order });
  });
  return results.sort((a, b) => b.score - a.score || a.order - b.order).slice(0, limit);
}

/** Splits a label into plain and highlighted pieces for rendering. */
export function highlight(label: string, ranges: [number, number][]): { text: string; match: boolean }[] {
  const merged: [number, number][] = [];
  for (const r of [...ranges].sort((a, b) => a[0] - b[0])) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  const out: { text: string; match: boolean }[] = [];
  let at = 0;
  for (const [s, e] of merged) {
    if (s > at) out.push({ text: label.slice(at, s), match: false });
    out.push({ text: label.slice(s, e), match: true });
    at = e;
  }
  if (at < label.length) out.push({ text: label.slice(at), match: false });
  return out.length ? out : [{ text: label, match: false }];
}
