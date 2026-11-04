import { useCallback, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartSkeleton, firstLoad } from "@/components/Loading";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { useToast } from "@/components/Toast";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { classicDoc, getDashboardData, type CycleRow, type GreenhouseRow } from "@/lib/flowers-api";
import { ClassicLink } from "./ClassicLink";

const AXIS = { fontSize: 11, fill: "var(--sd-muted)" };
const n = (v: number | null | undefined) => (v ?? 0).toLocaleString("en-US");
const compact = (v: number) =>
  v >= 1e6 ? `${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1).replace(/\.0$/, "")}M` : v >= 1e4 ? `${Math.round(v / 1e3)}K` : n(v);

const STATUS_DOT: Record<string, string> = {
  Active: "var(--sd-data-green)",
  Ended: "var(--sd-data-red)",
  Planned: "var(--sd-target)",
};

function BarsByLabel({ rows, color, unit }: { rows: { label: string; value: number }[]; color: string; unit: string }) {
  if (!rows.length) return <EmptyNote>No data yet.</EmptyNote>;
  const h = Math.max(120, rows.length * 30 + 24);
  return (
    <div style={{ height: h }} className="w-full" role="img" aria-label={`${unit} by label`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke="var(--sd-line-soft)" />
          <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} tickFormatter={compact} />
          <YAxis type="category" dataKey="label" tick={AXIS} axisLine={false} tickLine={false} width={120} />
          <Tooltip
            cursor={{ fill: "var(--sd-bg-soft)" }}
            formatter={(v: number) => [`${n(v)} ${unit}`, ""]}
            contentStyle={{ borderRadius: 12, border: "none", boxShadow: "var(--sd-shadow-2)", fontSize: 12 }}
          />
          <Bar dataKey="value" fill={color} radius={[0, 6, 6, 0]} maxBarSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** The Crop Cycle Dashboard block, rebuilt: plants standing, greenhouses, planted area, cycles and
 *  varieties; plants by farm; top varieties; cycles by status; the greenhouse table. */
export function FlowerOverview() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [ghs, setGhs] = useState<GreenhouseRow[] | null>(null);
  const [ccs, setCcs] = useState<CycleRow[] | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getDashboardData();
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setGhs(r.greenhouses);
    setCcs(r.cycles);
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const waiting = firstLoad(loading, !!ghs);
  const d = useMemo(() => {
    const g = ghs ?? [];
    const c = ccs ?? [];
    const sum = (f: (x: GreenhouseRow) => number | null) => g.reduce((a, x) => a + (f(x) ?? 0), 0);
    const plants = sum((x) => x.number_of_plants);
    const beds = sum((x) => x.number_of_beds);
    const planted = sum((x) => x.area_planted);
    const gross = sum((x) => x.gross_area);
    const varieties = new Set(c.map((x) => x.variety).filter(Boolean));
    const active = c.filter((x) => x.status === "Active").length;
    const byFarm = new Map<string, number>();
    g.forEach((x) => byFarm.set(x.farm || "(no farm)", (byFarm.get(x.farm || "(no farm)") ?? 0) + (x.number_of_plants ?? 0)));
    const byVar = new Map<string, number>();
    c.forEach((x) => x.variety && byVar.set(x.variety, (byVar.get(x.variety) ?? 0) + (x.plants_standing || x.qty_planted || 0)));
    const status = new Map<string, number>();
    c.forEach((x) => status.set(x.status || "Not set", (status.get(x.status || "Not set") ?? 0) + 1));
    const cyclesBy = new Map<string, number>();
    c.forEach((x) => x.greenhouse && cyclesBy.set(x.greenhouse, (cyclesBy.get(x.greenhouse) ?? 0) + 1));
    const top = (m: Map<string, number>, k = 10) =>
      [...m.entries()].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value).slice(0, k);
    return {
      plants, beds, planted, gross, varieties: varieties.size, active, cycles: c.length, houses: g.length,
      farms: top(byFarm), vars: top(byVar), status: [...status.entries()].sort(), cyclesBy,
      rows: g.slice().sort((a, b) => (b.number_of_plants ?? 0) - (a.number_of_plants ?? 0)),
    };
  }, [ghs, ccs]);

  const util = d.gross ? Math.round((d.planted / d.gross) * 100) : 0;
  return (
    <PageShell
      title="Overview"
      eyebrow={crop.name}
      actions={
        <>
          <ClassicLink href="/desk/greenhouse" />
          <RefreshButton onClick={() => void load()} loading={loading} label="the greenhouses and crop cycles" />
        </>
      }
      description={`${d.houses} greenhouses · ${compact(d.beds)} beds · ${d.cycles} crop cycles`}
    >
      <KpiGrid cols={5}>
        <KpiCard label="Plants standing" value={compact(d.plants)} hint={`${n(d.plants)} across all beds`} tone="accent" loading={waiting} />
        <KpiCard label="Greenhouses" value={d.houses} hint={`${compact(d.beds)} beds`} loading={waiting} />
        <KpiCard label="Planted area" value={`${compact(Math.round(d.planted))} m²`} hint={`${util}% of ${compact(Math.round(d.gross))} m² gross`} loading={waiting} />
        <KpiCard label="Crop cycles" value={d.cycles} hint={`${d.active} active`} loading={waiting} />
        <KpiCard label="Varieties in ground" value={d.varieties} hint="distinct, from crop cycles" loading={waiting} />
      </KpiGrid>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Plants standing by farm" hint="From the beds in each greenhouse">
          {waiting ? <ChartSkeleton height={160} /> : <BarsByLabel rows={d.farms} color={accent} unit="plants" />}
        </Panel>
        <Panel title="Top varieties by plants" hint="Largest ten across the estate">
          {waiting ? <ChartSkeleton height={160} /> : <BarsByLabel rows={d.vars} color={accent} unit="plants" />}
        </Panel>
      </div>

      <Panel title="Crop cycles by status" hint="Each cycle is one variety planted in one bed range">
        {d.status.length ? (
          <div className="flex flex-wrap gap-2">
            {d.status.map(([k, v]) => (
              <span key={k} className="inline-flex items-center gap-2 rounded-full bg-[var(--sd-bg-soft)] px-3 py-1 text-[12px]">
                <span className="h-2 w-2 rounded-full" style={{ background: STATUS_DOT[k] ?? "var(--sd-muted)" }} />
                {k} <b className="tabular-nums">{v}</b>
              </span>
            ))}
          </div>
        ) : (
          <EmptyNote>No crop cycles yet.</EmptyNote>
        )}
      </Panel>

      <Panel title="Greenhouses" hint="Beds, plants and cycles per greenhouse">
        {d.rows.length === 0 ? (
          <EmptyNote>No greenhouses yet.</EmptyNote>
        ) : (
          <ScrollTable>
            <Table>
              <TableHeader>
                <TableRow>
                  {["Greenhouse", "Farm", "Beds", "Plants", "Planted m²", "Gross m²", "Varieties", "Cycles"].map((h, i) => (
                    <TableHead key={h} className={`${STICKY_HEAD} ${i > 1 ? "text-right" : ""}`}>{h}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {d.rows.map((g) => (
                  <TableRow key={g.name}>
                    <TableCell><a className="font-medium text-[var(--sd-ink)] hover:underline" href={classicDoc("Greenhouse", g.name)}>{g.name}</a></TableCell>
                    <TableCell>{g.farm || "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(g.number_of_beds)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(g.number_of_plants)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(Math.round(g.area_planted ?? 0))}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(Math.round(g.gross_area ?? 0))}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(g.varieties)}</TableCell>
                    <TableCell className="text-right tabular-nums">{d.cyclesBy.get(g.name) ?? 0}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollTable>
        )}
      </Panel>
    </PageShell>
  );
}
