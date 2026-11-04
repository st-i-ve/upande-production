import { useMemo, useState } from "react";
import { firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { SearchInput } from "@/components/SearchInput";
import { useToast } from "@/components/Toast";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCurrentCrop } from "@/lib/crops";
import { classicDoc, classicList } from "@/lib/flowers-api";
import { useFlowerData } from "@/lib/use-flower-data";
import { ClassicLink } from "./ClassicLink";
import { unitWord } from "./unit-words";

const n = (v: number | null | undefined) => (v ?? 0).toLocaleString("en-US", { maximumFractionDigits: 1 });
const match = (q: string, ...vals: (string | null | undefined)[]) =>
  !q.trim() || vals.some((v) => (v ?? "").toLowerCase().includes(q.trim().toLowerCase()));

/** Blocks & Beds (block-based crops) or Greenhouses: beds, plants, area and cycles per unit. */
export function Greenhouses() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const { data, loading, reload } = useFlowerData(crop.name, (m) => toast(m, "error"));
  const [q, setQ] = useState("");
  const word = unitWord(data?.mode);
  const title = data?.mode === "block" ? "Blocks & Beds" : "Greenhouses";
  const rows = useMemo(() => (data?.units ?? []).filter((u) => match(q, u.name, u.farm)), [data, q]);
  const waiting = firstLoad(loading, !!data);
  return (
    <PageShell
      title={title}
      eyebrow={crop.name}
      description={`${word.plural} and their beds, with the plants standing in them.`}
      actions={
        <>
          <SearchInput value={q} onChange={setQ} placeholder={`Search ${word.plural.toLowerCase()}`} className="w-56" />
          <ClassicLink href={classicList(word.doctype)} />
          <RefreshButton onClick={() => void reload()} loading={loading} label={word.plural.toLowerCase()} />
        </>
      }
    >
      <Panel title={word.plural} hint={data ? `${rows.length} of ${data.units.length}` : undefined}>
        {waiting ? (
          <EmptyNote>Loading…</EmptyNote>
        ) : rows.length === 0 ? (
          <EmptyNote>No {word.plural.toLowerCase()} yet.</EmptyNote>
        ) : (
          <ScrollTable tall>
            <Table>
              <TableHeader>
                <TableRow>
                  {[word.singular, "Farm", "Beds", "Plants", "Planted m²", "Gross m²", "Varieties", "Cycles"].map((h, i) => (
                    <TableHead key={h} className={`${STICKY_HEAD} ${i > 1 ? "text-right" : ""}`}>{h}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((u) => (
                  <TableRow key={u.name}>
                    <TableCell><a className="font-medium text-[var(--sd-ink)] hover:underline" href={classicDoc(word.doctype, u.name)}>{u.label}</a></TableCell>
                    <TableCell>{u.farm || "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(u.beds)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(u.plants)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(u.area_planted)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(u.gross_area)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(u.varieties)}</TableCell>
                    <TableCell className="text-right tabular-nums">{u.cycles}</TableCell>
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

/** Crop cycles of this crop: variety (by name), unit, farm, planting, plants, area and beds. */
export function FlowerCycles() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const { data, loading, reload } = useFlowerData(crop.name, (m) => toast(m, "error"));
  const [q, setQ] = useState("");
  const word = unitWord(data?.mode);
  const rows = useMemo(
    () => (data?.cycles ?? []).filter((c) => match(q, c.name, c.variety_name, c.variety, c.unit, c.farm, c.product)),
    [data, q],
  );
  const waiting = firstLoad(loading, !!data);
  return (
    <PageShell
      title="Crop Cycles"
      eyebrow={crop.name}
      description={`Each cycle is one variety planted in one ${word.singular.toLowerCase()}'s bed range, from planting to uprooting.`}
      actions={
        <>
          <SearchInput value={q} onChange={setQ} placeholder="Search crop cycles" className="w-56" />
          <ClassicLink href={classicList("Crop Cycle")} />
          <RefreshButton onClick={() => void reload()} loading={loading} label="crop cycles" />
        </>
      }
    >
      <Panel title="Crop Cycles" hint={data ? `${rows.length} of ${data.cycles.length}` : undefined}>
        {waiting ? (
          <EmptyNote>Loading…</EmptyNote>
        ) : rows.length === 0 ? (
          <EmptyNote>No crop cycles yet.</EmptyNote>
        ) : (
          <ScrollTable tall>
            <Table>
              <TableHeader>
                <TableRow>
                  {["Cycle", "Variety", "Product", word.singular, "Farm", "Status", "Planted", "Plants", "Area m²", "Beds"].map((h, i) => (
                    <TableHead key={h} className={`${STICKY_HEAD} ${i >= 7 ? "text-right" : ""}`}>{h}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((c) => (
                  <TableRow key={c.name}>
                    <TableCell><a className="font-medium text-[var(--sd-ink)] hover:underline" href={classicDoc("Crop Cycle", c.name)}>{c.name}</a></TableCell>
                    <TableCell title={c.variety ? `Item ${c.variety}` : undefined}>{c.variety_name || "—"}</TableCell>
                    <TableCell>{c.product || "—"}</TableCell>
                    <TableCell>{c.unit || "—"}</TableCell>
                    <TableCell>{c.farm || "—"}</TableCell>
                    <TableCell>{c.status || "—"}</TableCell>
                    <TableCell>{c.planting_date || "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(c.plants)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(c.area)}</TableCell>
                    <TableCell className="text-right tabular-nums">{n(c.beds)}</TableCell>
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
