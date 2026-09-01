/**
 * Small, dependency-free fuzzy-ish search.
 *
 * Every whitespace-separated token in the query must appear somewhere in the
 * haystack, so "rep tax" finds "Report on taxes" while "zzz tax" does not.
 * Matching is case- and accent-insensitive, so "cafe" finds "Café".
 */

export function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export function tokenize(query: string): string[] {
  return normalize(query).split(/\s+/).filter(Boolean);
}

export function matchesSearch(query: string, fields: (string | null | undefined)[]): boolean {
  const tokens = tokenize(query);
  if (tokens.length === 0) return true;

  const haystack = normalize(fields.filter(Boolean).join(" "));
  return tokens.every((token) => haystack.includes(token));
}

/**
 * Split `text` into alternating unmatched/matched segments so the UI can
 * highlight what the query hit.
 */
export function highlightSegments(
  text: string,
  query: string,
): { text: string; match: boolean }[] {
  const tokens = tokenize(query);
  if (tokens.length === 0) return [{ text, match: false }];

  const normalizedText = normalize(text);
  const hits: [number, number][] = [];

  for (const token of tokens) {
    let from = 0;
    for (;;) {
      const index = normalizedText.indexOf(token, from);
      if (index === -1) break;
      hits.push([index, index + token.length]);
      from = index + token.length;
    }
  }
  if (hits.length === 0) return [{ text, match: false }];

  // Merge overlapping ranges so nested matches do not double-wrap.
  hits.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [hits[0]!];
  for (const [start, end] of hits.slice(1)) {
    const last = merged[merged.length - 1]!;
    if (start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }

  const segments: { text: string; match: boolean }[] = [];
  let cursor = 0;
  for (const [start, end] of merged) {
    if (start > cursor) segments.push({ text: text.slice(cursor, start), match: false });
    segments.push({ text: text.slice(start, end), match: true });
    cursor = end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), match: false });
  return segments;
}
