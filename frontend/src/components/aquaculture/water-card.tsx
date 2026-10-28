import { Card } from "@/components/ui/card";
import type { Bands, Measures, WaterPond } from "@/lib/aquaculture-api";
import { cn } from "@/lib/utils";
import { dayTime, fmtNum, TONE } from "./format";
import { Chip } from "./ui";
import { MiniDo } from "./water-charts";

type Cell = { key: string; label: string; value: number | null; unit: string; bad: boolean; band: string; d: number };

export function cells(m: Measures, b: Bands): Cell[] {
  const out = (v: number | null, bad: boolean) => v != null && bad;
  return [
    { key: "do", label: "Oxygen", value: m.dissolved_oxygen_mg_l, unit: "mg/L", d: 1, band: `min ${b.do_min}`, bad: out(m.dissolved_oxygen_mg_l, (m.dissolved_oxygen_mg_l ?? 0) < b.do_min) },
    { key: "ph", label: "pH", value: m.ph, unit: "", d: 1, band: `${b.ph_min} to ${b.ph_max}`, bad: out(m.ph, (m.ph ?? 7) < b.ph_min || (m.ph ?? 7) > b.ph_max) },
    { key: "temp", label: "Temp", value: m.temperature_c, unit: "°C", d: 1, band: `${b.temp_min} to ${b.temp_max}`, bad: out(m.temperature_c, (m.temperature_c ?? 27) < b.temp_min || (m.temperature_c ?? 27) > b.temp_max) },
    { key: "ammonia", label: "Ammonia", value: m.ammonia_mg_l, unit: "mg/L", d: 2, band: `under ${b.ammonia_max}`, bad: out(m.ammonia_mg_l, (m.ammonia_mg_l ?? 0) >= b.ammonia_max) },
    { key: "nitrite", label: "Nitrite", value: m.nitrite_mg_l, unit: "mg/L", d: 2, band: `under ${b.nitrite_max}`, bad: out(m.nitrite_mg_l, (m.nitrite_mg_l ?? 0) >= b.nitrite_max) },
    { key: "secchi", label: "Secchi", value: m.secchi_cm, unit: "cm", d: 0, band: "", bad: false },
  ];
}

export function WaterCard({ pond, bands, color }: { pond: WaterPond; bands: Bands; color: string }) {
  const l = pond.latest;
  return (
    <Card className="flex flex-col gap-3 p-5" data-testid={`water-card-${pond.label}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 truncate text-[15px] font-semibold">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color }} />
            {pond.label}
          </div>
          <div className="text-[12px] text-[var(--sd-quiet)]">{l ? `Latest ${dayTime(l.at)}` : "No reading in this period"}</div>
        </div>
        {pond.status === "alert" && <Chip className={TONE.bad}>Out of band</Chip>}
        {pond.status === "ok" && <Chip className={TONE.ok}>In band</Chip>}
        {pond.status === "none" && <Chip className={TONE.quiet}>No data</Chip>}
      </div>
      {l ? (
        <div className="grid grid-cols-3 gap-x-3 gap-y-2.5">
          {cells(l, bands).map((c) => (
            <div key={c.key} title={c.band ? `Safe: ${c.band}` : undefined}>
              <div className="text-[10.5px] font-medium uppercase tracking-[0.12em] text-[var(--sd-quiet)]">{c.label}</div>
              <div className={cn("mt-0.5 text-[15px] font-semibold tabular-nums", c.bad && "text-[var(--sd-data-red)]")} data-bad={c.bad ? "true" : undefined}>
                {c.value == null ? "—" : fmtNum(c.value, c.d)}
                {c.value != null && c.unit && <span className="ml-0.5 text-[11px] font-normal text-[var(--sd-quiet)]">{c.unit}</span>}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <MiniDo pond={pond} bands={bands} color={color} />
      <div className="text-[12px] text-[var(--sd-quiet)]">
        {pond.readings} reading{pond.readings === 1 ? "" : "s"}
        {pond.min_do_mg_l != null && ` · lowest oxygen ${fmtNum(pond.min_do_mg_l, 1)}`}
        {pond.out_of_band_count > 0 && ` · ${pond.out_of_band_count} out of band`}
      </div>
    </Card>
  );
}
