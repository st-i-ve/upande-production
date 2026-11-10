/** Export count sizes: keep the gram bands contiguous. Mirrors production/logic/count_sizes.py. */

export type Row = Record<string, string | number | null>;
export interface BandIssue {
  kind: "invalid" | "duplicate" | "order" | "gap" | "overlap";
  counts: number[];
  message: string;
}

const n = (v: unknown) => {
  const x = parseFloat(String(v ?? ""));
  return Number.isNaN(x) ? 0 : x;
};
const g = (v: number) => String(Math.round(v * 100) / 100);

/** Rows with a count, sorted by count (big fruit first). */
export function sortedBands(rows: Row[]): Row[] {
  return rows.filter((r) => Math.trunc(n(r.count))).sort((a, b) => n(a.count) - n(b.count));
}

export function bandIssues(rows: Row[]): BandIssue[] {
  const out: BandIssue[] = [];
  const b = sortedBands(rows);
  b.forEach((r, i) => {
    const c = n(r.count);
    if (i && n(b[i - 1].count) === c) out.push({ kind: "duplicate", counts: [c], message: `Count ${c} appears more than once` });
    if (n(r.min_g) >= n(r.max_g)) out.push({ kind: "invalid", counts: [c], message: `Count ${c}: min ${g(n(r.min_g))} g is not below max ${g(n(r.max_g))} g` });
  });
  for (let i = 1; i < b.length; i++) {
    const a = b[i - 1];
    const c = b[i];
    const ca = n(a.count);
    const cc = n(c.count);
    if (ca === cc || n(a.min_g) >= n(a.max_g) || n(c.min_g) >= n(c.max_g)) continue;
    if (n(c.min_g) >= n(a.min_g)) out.push({ kind: "order", counts: [ca, cc], message: `Count ${cc} is not lighter than count ${ca} (a higher count is smaller fruit)` });
    else if (n(c.max_g) < n(a.min_g)) out.push({ kind: "gap", counts: [ca, cc], message: `Fruit between ${g(n(c.max_g))} g and ${g(n(a.min_g))} g has no count size` });
    else if (n(c.max_g) > n(a.min_g)) out.push({ kind: "overlap", counts: [ca, cc], message: `Counts ${ca} and ${cc} both cover ${g(n(a.min_g))}–${g(n(c.max_g))} g` });
  }
  return out;
}

/** Edit one cell. A band's min also sets the next-higher count's max; its max sets the next-lower count's min.
 *  Returns the new rows and a note about the neighbour that moved. */
export function linkedEdit(rows: Row[], index: number, field: string, value: string): { rows: Row[]; note: string | null } {
  const next = rows.map((r, j) => (j === index ? { ...r, [field]: value } : r));
  const row = next[index];
  const count = n(row.count);
  if ((field !== "min_g" && field !== "max_g") || !Math.trunc(count) || value.trim() === "" || Number.isNaN(parseFloat(value))) return { rows: next, note: null };
  let target = -1;
  for (let j = 0; j < next.length; j++) {
    if (j === index) continue;
    const c = n(next[j].count);
    if (!Math.trunc(c)) continue;
    if (field === "min_g" ? c > count && (target < 0 || c < n(next[target].count)) : c < count && (target < 0 || c > n(next[target].count))) target = j;
  }
  if (target < 0) return { rows: next, note: null };
  const other = field === "min_g" ? "max_g" : "min_g";
  next[target] = { ...next[target], [other]: value };
  return { rows: next, note: `Count ${n(next[target].count)} ${field === "min_g" ? "max" : "min"} moved to ${g(parseFloat(value))} g` };
}

/** Snap each band's max to the next-lower count's min, closing gaps and overlaps. */
export function closeGaps(rows: Row[]): Row[] {
  const order = sortedBands(rows);
  const max = new Map<Row, number>();
  order.forEach((r, i) => {
    if (i) max.set(r, n(order[i - 1].min_g));
  });
  return rows.map((r) => (max.has(r) ? { ...r, max_g: max.get(r)! } : r));
}
