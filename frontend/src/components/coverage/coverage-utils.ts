import type { CoverageMap, CoverageState, CoverageTask, CoverageUnit, UnitGeoJSON } from "@/lib/map-api";

/** Lower sorts first: the block that needs a manager's attention soonest. */
const URGENCY: Record<CoverageState, number> = {
  late: 0,
  partial: 1,
  not_started: 2,
  pending_approval: 3,
  done: 9,
  no_work: 9,
};

/** Earliest due date among tasks with work still outstanding ("" when none). */
export function nextDue(u: CoverageUnit): string {
  const dues = u.tasks.filter((t) => t.remaining_qty > 0 && t.due_date).map((t) => t.due_date);
  return dues.length ? dues.sort()[0] : "";
}

/** Blocks with work remaining, most urgent first: late, in progress, not started, awaiting approval;
 *  then earliest due date, then least progress. Done and no-work blocks are left out. */
export function remainingBlocks(units: CoverageUnit[]): CoverageUnit[] {
  return units
    .filter((u) => URGENCY[u.state] < 9)
    .sort((a, b) => {
      const s = URGENCY[a.state] - URGENCY[b.state];
      if (s) return s;
      const da = nextDue(a) || "9999";
      const db = nextDue(b) || "9999";
      if (da !== db) return da < db ? -1 : 1;
      return a.progress_pct - b.progress_pct || a.name.localeCompare(b.name);
    });
}

export function taskProgress(t: CoverageTask): number {
  return t.planned_qty > 0 ? Math.min(100, Math.round((t.done_qty / t.planned_qty) * 100)) : 0;
}

type Pt = [number, number];

function walk(c: unknown, out: Pt[]) {
  if (Array.isArray(c) && typeof c[0] === "number" && typeof c[1] === "number") out.push([c[0], c[1]]);
  else if (Array.isArray(c)) c.forEach((x) => walk(x, out));
}

function coords(gj: UnitGeoJSON): Pt[] {
  const out: Pt[] = [];
  if (!gj) return out;
  walk(gj.type === "Feature" ? gj.geometry?.coordinates : gj.coordinates ?? gj.geometry?.coordinates, out);
  return out;
}

export function unitBounds(u: CoverageUnit): [[number, number], [number, number]] | null {
  const pts = coords(u.geojson);
  if (!pts.length) return null;
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return [
    [Math.min(...xs), Math.min(...ys)],
    [Math.max(...xs), Math.max(...ys)],
  ];
}

export function unitCenter(u: CoverageUnit): [number, number] | null {
  const b = unitBounds(u);
  return b ? [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2] : null;
}

/** "Done 4 · Remaining 7 ..." pieces for the KPI pill. */
export function remainingBlockCount(t: CoverageMap["totals"]): number {
  return t.blocks - (t.by_state.done ?? 0) - (t.by_state.no_work ?? 0);
}
