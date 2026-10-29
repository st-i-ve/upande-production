import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, TriangleAlert } from "lucide-react";
import { RowsSkeleton } from "@/components/Loading";
import { blockLinks, type BlockLink } from "@/lib/blockcost-api";
import { isError } from "@/lib/frappe";
import { matchesQuery } from "@/lib/utils";

/** Every leaf block with its cost centre and warehouse; problems first. */
export function BlockLinksPanel({ crop, unitLabel, query }: { crop: string; unitLabel: string; query: string }) {
  const [rows, setRows] = useState<BlockLink[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setRows(null);
    void blockLinks(crop).then((r) => {
      if (!live) return;
      if (isError(r)) {
        setFailure(r.error);
        setRows([]);
      } else {
        setFailure(null);
        setRows(r.rows ?? []);
      }
    });
    return () => {
      live = false;
    };
  }, [crop]);

  const visible = useMemo(
    () =>
      (rows ?? [])
        .filter((r) => !query || matchesQuery(`${r.unit} ${r.cost_center ?? ""} ${r.warehouse ?? ""} ${r.problems.join(" ")}`, query))
        .sort((a, b) => Number(a.ok) - Number(b.ok) || a.unit.localeCompare(b.unit)),
    [rows, query],
  );
  const bad = (rows ?? []).filter((r) => !r.ok).length;

  if (!rows) return <RowsSkeleton rows={4} />;
  if (failure) return <p role="alert" className="text-[13px] text-[var(--sd-muted)]">{failure}</p>;
  if (rows.length === 0) return <p className="py-6 text-center text-[13px] text-[var(--sd-muted)]">No {unitLabel.toLowerCase()}s to check.</p>;
  return (
    <>
      <p data-testid="links-summary" className="mb-3 text-[13px] text-[var(--sd-muted)]">
        {bad === 0 ? `All ${rows.length} blocks are linked correctly.` : `${bad} of ${rows.length} blocks need attention.`}
      </p>
      <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
        <table className="w-full min-w-[40rem] text-[13px]">
          <thead>
            <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
              <th className="px-3 py-2.5 font-medium">{unitLabel}</th>
              <th className="px-3 py-2.5 font-medium">Cost centre</th>
              <th className="px-3 py-2.5 font-medium">Warehouse</th>
              <th className="px-3 py-2.5 font-medium">Check</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.unit} data-testid={`link-${r.unit}`} data-ok={r.ok ? "true" : "false"} className="border-b border-[var(--sd-line-soft)] align-top last:border-0">
                <td className="px-3 py-2.5 font-medium text-[var(--sd-ink)]">{r.unit}</td>
                <td className="px-3 py-2.5 text-[var(--sd-muted)]">{r.cost_center || "—"}</td>
                <td className="px-3 py-2.5 text-[var(--sd-muted)]">{r.warehouse || "—"}</td>
                <td className="px-3 py-2.5">
                  {r.ok ? (
                    <span className="inline-flex items-center gap-1.5 text-[var(--sd-sev-moderate)]">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Linked
                    </span>
                  ) : (
                    <ul className="space-y-1 text-[var(--sd-sev-high)]">
                      {r.problems.map((p) => (
                        <li key={p} className="flex items-start gap-1.5">
                          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          <span>{p}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
