import { useCallback, useEffect, useMemo, useState } from "react";
import { firstLoad, TableRowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { SearchInput } from "@/components/SearchInput";
import { useToast } from "@/components/Toast";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCurrentCrop } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { classicDoc, classicList, getList, type Row } from "@/lib/flowers-api";
import { ClassicLink } from "./ClassicLink";

interface Column {
  key: string;
  label: string;
  num?: boolean;
  fmt?: (v: unknown, row: Row) => React.ReactNode;
}

interface ListConfig {
  title: string;
  doctype: string;
  description: string;
  fields: string[];
  columns: Column[];
  filters?: unknown;
  order_by?: string;
  /** Where "Classic view" goes; defaults to the doctype's desk list. */
  classic?: string;
  /** The row's name column is a link to the classic form. */
  link?: boolean;
}

const num = (v: unknown) => (v == null || v === "" ? "—" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 1 }));
const text = (v: unknown) => (v == null || v === "" ? "—" : String(v));

function FlowerList({ cfg }: { cfg: ListConfig }) {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getList(cfg.doctype, cfg.fields, { filters: cfg.filters, order_by: cfg.order_by });
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setRows(r.rows);
  }, [cfg, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows ?? [];
    return (rows ?? []).filter((r) => Object.values(r).some((v) => String(v ?? "").toLowerCase().includes(needle)));
  }, [rows, q]);
  const waiting = firstLoad(loading, !!rows);

  return (
    <PageShell
      title={cfg.title}
      eyebrow={crop.name}
      description={cfg.description}
      actions={
        <>
          <SearchInput value={q} onChange={setQ} placeholder={`Search ${cfg.title.toLowerCase()}`} className="w-56" />
          <ClassicLink href={cfg.classic ?? classicList(cfg.doctype)} />
          <RefreshButton onClick={() => void load()} loading={loading} label={cfg.title.toLowerCase()} />
        </>
      }
    >
      <Panel title={cfg.title} hint={rows ? `${shown.length} of ${rows.length}` : undefined}>
        {waiting ? (
          <Table><TableBody><TableRowsSkeleton rows={6} cols={cfg.columns.length} /></TableBody></Table>
        ) : shown.length === 0 ? (
          <EmptyNote>{rows?.length ? "Nothing matches the search." : `No ${cfg.title.toLowerCase()} yet.`}</EmptyNote>
        ) : (
          <ScrollTable tall>
            <Table>
              <TableHeader>
                <TableRow>
                  {cfg.columns.map((c) => (
                    <TableHead key={c.key} className={`${STICKY_HEAD} ${c.num ? "text-right" : ""}`}>{c.label}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((r) => (
                  <TableRow key={String(r.name)}>
                    {cfg.columns.map((c, i) => {
                      const v = r[c.key];
                      const cell = c.fmt ? c.fmt(v, r) : c.num ? num(v) : text(v);
                      return (
                        <TableCell key={c.key} className={c.num ? "text-right tabular-nums" : ""}>
                          {i === 0 && cfg.link !== false ? (
                            <a className="font-medium text-[var(--sd-ink)] hover:underline" href={classicDoc(cfg.doctype, String(r.name))}>
                              {cell}
                            </a>
                          ) : (
                            cell
                          )}
                        </TableCell>
                      );
                    })}
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

const date = (v: unknown) => (v ? String(v).slice(0, 10) : "—");

const GREENHOUSES: ListConfig = {
  title: "Greenhouses",
  doctype: "Greenhouse",
  description: "Greenhouses and their beds, with the plants standing in them.",
  fields: ["name", "farm", "number_of_beds", "number_of_plants", "area_planted", "gross_area", "varieties", "last_replanting_date"],
  order_by: "name asc",
  columns: [
    { key: "name", label: "Greenhouse" },
    { key: "farm", label: "Farm" },
    { key: "number_of_beds", label: "Beds", num: true },
    { key: "number_of_plants", label: "Plants", num: true },
    { key: "area_planted", label: "Planted m²", num: true },
    { key: "gross_area", label: "Gross m²", num: true },
    { key: "varieties", label: "Varieties", num: true },
    { key: "last_replanting_date", label: "Last replanting", fmt: date },
  ],
};

const CYCLES: ListConfig = {
  title: "Crop Cycles",
  doctype: "Crop Cycle",
  description: "Each cycle is one variety planted in one bed range of a greenhouse, from planting to uprooting.",
  fields: ["name", "greenhouse", "farm", "variety", "status", "planting_date", "qty_planted", "plants_standing", "planted_area", "bed_range"],
  order_by: "modified desc",
  columns: [
    { key: "name", label: "Cycle" },
    { key: "greenhouse", label: "Greenhouse" },
    { key: "variety", label: "Variety" },
    { key: "status", label: "Status" },
    { key: "planting_date", label: "Planted", fmt: date },
    { key: "qty_planted", label: "Planted qty", num: true },
    { key: "plants_standing", label: "Standing", num: true },
    { key: "planted_area", label: "Area m²", num: true },
    { key: "bed_range", label: "Beds" },
  ],
};

const PROTOCOLS: ListConfig = {
  title: "Crop Protocols",
  doctype: "Crop Protocol",
  description: "What a variety should produce: density, weeks to bending, flushes and stems per plant.",
  fields: ["name", "variety_item", "crop_type", "plants_per_sqm", "weeks_to_first_bending", "productive_life_weeks", "weeks_between_cuts", "total_stems_per_plant_life"],
  order_by: "name asc",
  columns: [
    { key: "name", label: "Protocol" },
    { key: "variety_item", label: "Variety" },
    { key: "crop_type", label: "Crop type" },
    { key: "plants_per_sqm", label: "Plants /m²", num: true },
    { key: "weeks_to_first_bending", label: "Weeks to 1st bend", num: true },
    { key: "productive_life_weeks", label: "Life (weeks)", num: true },
    { key: "weeks_between_cuts", label: "Weeks between cuts", num: true },
    { key: "total_stems_per_plant_life", label: "Stems /plant life", num: true },
  ],
};

const CUT_STAGES: ListConfig = {
  title: "Cut Stages",
  doctype: "Cut Stage",
  description: "Harvest cut definitions: the stage at which a stem is cut.",
  fields: ["name", "cutstage", "modified"],
  order_by: "name asc",
  columns: [
    { key: "name", label: "Cut stage" },
    { key: "cutstage", label: "Description" },
    { key: "modified", label: "Changed", fmt: date },
  ],
};

const PLAN_FORMS: ListConfig = {
  title: "Weekly Plan",
  doctype: "Production Plan Form",
  description: "The weekly production plan per greenhouse (the Production Plan Form).",
  fields: ["name", "plan_period", "greenhouse", "plan_year", "plan_week", "docstatus", "modified"],
  order_by: "plan_year desc, plan_week desc",
  columns: [
    { key: "name", label: "Plan" },
    { key: "plan_period", label: "Period" },
    { key: "greenhouse", label: "Greenhouse" },
    { key: "plan_year", label: "Year" },
    { key: "plan_week", label: "Week" },
    { key: "docstatus", label: "Status", fmt: (v) => (v === 1 ? "Submitted" : v === 2 ? "Cancelled" : "Draft") },
    { key: "modified", label: "Changed", fmt: date },
  ],
};

const HARVESTING: ListConfig = {
  title: "Harvesting",
  doctype: "Stock Entry",
  description: "Stock entries of type Harvesting: the cut coming in from the greenhouses.",
  fields: ["name", "posting_date", "stock_entry_type", "to_warehouse", "total_amount", "docstatus"],
  filters: [["Stock Entry", "stock_entry_type", "=", "Harvesting"]],
  order_by: "posting_date desc, creation desc",
  classic: "/desk/stock-entry?stock_entry_type=Harvesting",
  columns: [
    { key: "name", label: "Entry" },
    { key: "posting_date", label: "Date", fmt: date },
    { key: "to_warehouse", label: "To warehouse" },
    { key: "total_amount", label: "Amount", num: true },
    { key: "docstatus", label: "Status", fmt: (v) => (v === 1 ? "Submitted" : v === 2 ? "Cancelled" : "Draft") },
  ],
};

export const Greenhouses = () => <FlowerList cfg={GREENHOUSES} />;
export const FlowerCycles = () => <FlowerList cfg={CYCLES} />;
export const Protocols = () => <FlowerList cfg={PROTOCOLS} />;
export const CutStages = () => <FlowerList cfg={CUT_STAGES} />;
export const PlanForm = () => <FlowerList cfg={PLAN_FORMS} />;
export const Harvesting = () => <FlowerList cfg={HARVESTING} />;
