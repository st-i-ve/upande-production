import { useMemo } from "react";
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
import { classicDoc } from "@/lib/flowers-api";
import { useFlowerData } from "@/lib/use-flower-data";
import { ClassicLink } from "./ClassicLink";
import { unitWord } from "./unit-words";

const AXIS = { fontSize: 11, fill: "var(--sd-muted)" };
const n = (v: number | null | undefined) => (v ?? 0).toLocaleString("en-US");
const compact = (v: number) =>
  v >= 1e6 ? `${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1).replace(/\.0$/, "")}M` : v >= 1e4 ? `${Math.round(v / 1e3)}K` : n(v);

const STATUS_DOT: Record<string, string> = {
  Active: "var(--sd-data-green)",
  Ended: "var(--sd-data-red)",
  Planned: "var(--sd-target)",
};

function BarsByLabel({ rows, color, unit }: { rows: { label: string; value: number; code?: string }[]; color: string; unit: string }) {
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
            formatter={(v: number, _n: string, item: { payload?: { code?: string } }) => [`${n(v)} ${unit}`, item?.payload?.code ? `code ${item.payload.code}` : ""]}
            contentStyle={{ borderRadius: 12, border: "none", boxShadow: "var(--sd-shadow-2)", fontSize: 12 }}
          />
          <Bar dataKey="value" fill={color} radius={[0, 6, 6, 0]} maxBarSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** The Crop Cycle Dashboard, rebuilt: plants standing, blocks or greenhouses, planted area, cycles and
 *  varieties; plants by farm; top varieties (by name); cycles by status; the unit table. Works for
 *  greenhouse-based cycles (roses) and block-based ones (summer flowers). */
export function FlowerOverview() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const { data, loading, reload } = useFlowerData(crop.name, (m) => toast(m, "error"));
  const waiting = firstLoad(loading, !!data);
  const word = unitWord(data?.mode);

  const d = useMemo(() => {
    const cycles = data?.cycles ?? [];
    const byVar = new Map<string, { value: number; code: string }>();
    cycles.forEach((c) => {
      const k = c.variety_name || c.variety;
      if (!k) return;
      const cur = byVar.get(k) ?? { value: 0, code: c.variety ?? "" };
      cur.value += c.plants;
      byVar.set(k, cur);
    });
    const status = new Map<string, number>();
    cycles.forEach((c) => status.set(c.status || "Not set", (status.get(c.status || "Not set") ?? 0) + 1));
    return {
      vars: [...byVar.entries()].map(([label, v]) => ({ label, value: v.value, code: v.code })).sort((a, b) => b.value - a.value).slice(0, 10),
      status: [...status.entries()].sort(),
      farms: (data?.farms ?? []).map((f) => ({ label: f.farm, value: f.plants })),
      rows: (data?.units ?? []).slice().sort((a, b) => b.plants - a.plants),
    };
  }, [data]);

  const t = data?.totals;
  const util = t && t.gross_area ? Math.round((t.area_planted / t.gross_area) * 100) : 0;
  return (
    <PageShell
      title="Overview"
      eyebrow={crop.name}
      actions={
        <>
          <ClassicLink href="/desk/greenhouse" />
          <RefreshButton onClick={() => void reload()} loading={loading} label="the blocks, beds and crop cycles" />
        </>
      }
      description={t ? `${t.units} ${word.plural.toLowerCase()} · ${compact(t.beds)} beds · ${t.cycles} crop cycles` : undefined}
    >
      <KpiGrid cols={5}>
        <KpiCard label="Plants standing" value={compact(t?.plants ?? 0)} hint={`${n(t?.plants)} across all beds`} tone="accent" loading={waiting} />
        <KpiCard label={word.plural} value={t?.units ?? 0} hint={`${compact(t?.beds ?? 0)} beds`} loading={waiting} />
        <KpiCard label="Planted area" value={`${compact(Math.round(t?.area_planted ?? 0))} m²`} hint={`${util}% of ${compact(Math.round(t?.gross_area ?? 0))} m² gross`} loading={waiting} />
        <KpiCard label="Crop cycles" value={t?.cycles ?? 0} hint={`${t?.active ?? 0} active`} loading={waiting} />
        <KpiCard label="Varieties in ground" value={t?.varieties ?? 0} hint="distinct, from crop cycles" loading={waiting} />
      </KpiGrid>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Plants standing by farm" hint={`From the beds in each ${word.singular.toLowerCase()}`}>
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

      <Panel title={word.plural} hint={`Beds, plants and cycles per ${word.singular.toLowerCase()}`}>
        {d.rows.length === 0 ? (
          <EmptyNote>No {word.plural.toLowerCase()} yet.</EmptyNote>
        ) : (
          <ScrollTable>
            <Table>
              <TableHeader>
                <TableRow>
                  {[word.singular, "Farm", "Beds", "Plants", "Planted m²", "Gross m²", "Varieties", "Cycles"].map((h, i) => (
                    <TableHead key={h} className={`${STICKY_HEAD} ${i > 1 ? "text-right" : ""}`}>{h}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {d.rows.map((g) => (
                  <TableRow key={g.name}>
                    <TableCell><a className="font-medium text-[var(--sd-ink)] hover:underline" href={classicDoc(word.doctype, g.name)}>{g.label}</a></TableCell>
                    <TableCell>{g.farm || "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(g.beds)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(g.plants)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(Math.round(g.area_planted))}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(Math.round(g.gross_area))}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(g.varieties)}</TableCell>
                    <TableCell className="text-right tabular-nums">{g.cycles}</TableCell>
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
