import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { Bar, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { ActionPill } from "@/components/approvals/ActionPill";
import { ApprovalCard } from "@/components/approvals/ApprovalCard";
import { ProtocolReview } from "@/components/approvals/ProtocolReview";
import { SendBackDialog } from "@/components/approvals/SendBackDialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  approve,
  listApprovals,
  resubmit,
  sendBack,
  type ApprovalGroup,
  type ApprovalList,
  type ApprovalStatus,
  type ResubmitEdit,
} from "@/lib/approvals-api";
import {
  approveProtocol,
  pendingProtocols,
  sendBackProtocol,
  type PendingProtocol,
} from "@/lib/protocols-api";
import { useCurrentCrop } from "@/lib/crops";
import { isError, type Envelope } from "@/lib/frappe";
import { formatUoms, kes, qty } from "@/lib/format";

type Tab = "pending" | "stale" | "sent" | "approved" | "protocols";
const STATUS: Record<Tab, ApprovalStatus> = {
  pending: "Pending",
  stale: "Pending",
  sent: "Sent Back",
  approved: "Approved",
  protocols: "Pending",
};
const EMPTY_RANGE: DateRange = { from: "", to: "" };

/** Tell the app shell (sidebar badge) that approval counts moved. */
export const APPROVALS_CHANGED = "production:approvals-changed";
const announce = () => window.dispatchEvent(new Event(APPROVALS_CHANGED));

const EMPTY: Record<Tab, { title: string; hint: string }> = {
  pending: { title: "Nothing waiting for approval", hint: "When supervisors key in work, it lands here for you to approve." },
  stale: { title: "Nothing is stale", hint: "Every submission has been looked at recently." },
  sent: { title: "Nothing sent back", hint: "Submissions you send back for fixing will wait here for the supervisor." },
  protocols: { title: "No protocol versions waiting", hint: "Submitted protocol versions land here." },
  approved: { title: "No approved work in this period", hint: "Widen the date range to see earlier approvals." },
};

/** The manager's desk: review what supervisors keyed in, approve it so it counts, or send it back. */
export function Approvals() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const showPay = crop.boot.can_see_pay;
  const [tab, setTab] = useState<Tab>("pending");
  const [range, setRange] = useState<DateRange>(EMPTY_RANGE);
  const [unit, setUnit] = useState("");
  const [operation, setOperation] = useState("");
  const [supervisor, setSupervisor] = useState("");
  const [pending, setPending] = useState<ApprovalList | null>(null);
  const [other, setOther] = useState<ApprovalList | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<Set<string>>(new Set());
  const [dialog, setDialog] = useState<ApprovalGroup[] | null>(null);
  const [sending, setSending] = useState(false);
  const [opts, setOpts] = useState({ units: new Map<string, string>(), ops: new Map<string, string>(), sups: new Map<string, string>() });
  const [protos, setProtos] = useState<PendingProtocol[] | null>(null);
  const [protoBusy, setProtoBusy] = useState<Set<string>>(new Set());
  const seq = useRef(0);

  const filters = useMemo(
    () => ({ fromDate: range.from || null, toDate: range.to || null, unit: unit || null, operation: operation || null, supervisor: supervisor || null }),
    [range, unit, operation, supervisor],
  );
  const dirty = !!(range.from || range.to || unit || operation || supervisor);
  const needsOther = tab === "sent" || tab === "approved";

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    const [p, o, pr] = await Promise.all([
      listApprovals(crop.name, { ...filters, status: "Pending" }),
      needsOther ? listApprovals(crop.name, { ...filters, status: STATUS[tab] }) : Promise.resolve(null),
      pendingProtocols(crop.name),
    ]);
    if (mine !== seq.current) return;
    setLoading(false);
    for (const r of [p, o]) {
      if (r && isError(r)) toast(r.error, "error");
    }
    if (isError(pr)) toast(pr.error, "error");
    else setProtos(pr.rows);
    if (!isError(p)) setPending(p as ApprovalList);
    if (o && !isError(o)) setOther(o as ApprovalList);
    const lists = [p, o].filter((r): r is ApprovalList => !!r && !isError(r));
    setOpts((prev) => {
      const next = { units: new Map(prev.units), ops: new Map(prev.ops), sups: new Map(prev.sups) };
      for (const l of lists)
        for (const g of l.groups) {
          next.units.set(g.unit, g.unit_name);
          next.ops.set(g.operation, g.operation_name);
          next.sups.set(g.submitted_by, g.submitted_by_name || g.submitted_by);
        }
      return next;
    });
  }, [crop.name, filters, tab, needsOther, toast]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => setSelected(new Set()), [tab, crop.name]);

  const list = needsOther ? other : pending;
  const groups = useMemo(() => {
    const gs = list?.groups ?? [];
    return tab === "stale" ? gs.filter((g) => g.stale) : gs;
  }, [list, tab]);
  const counts = (needsOther ? other : pending)?.counts ?? pending?.counts ?? other?.counts;
  const waiting = firstLoad(loading, !!list);

  // KPI row is always about what is awaiting the manager.
  const awaiting = pending?.groups ?? [];
  const qtyAwaiting = useMemo(() => {
    const byUom = new Map<string, number>();
    for (const g of awaiting) byUom.set(g.uom || "", (byUom.get(g.uom || "") ?? 0) + g.total_qty);
    return formatUoms([...byUom].map(([uom, n]) => ({ uom, qty: n })));
  }, [awaiting]);
  const payAwaiting = awaiting.reduce((s, g) => s + (g.total_pay ?? 0), 0);

  const removeFromView = (keys: Set<string>) => {
    const strip = (l: ApprovalList | null) => (l ? { ...l, groups: l.groups.filter((g) => !keys.has(g.key)) } : l);
    setPending(strip);
    setOther(strip);
    setSelected((s) => new Set([...s].filter((k) => !keys.has(k))));
  };

  /** Optimistic: cards leave at once; on failure they come back and the error is toasted. */
  const act = async (gs: ApprovalGroup[], run: () => Promise<Envelope<unknown>>, done: string) => {
    const keys = new Set(gs.map((g) => g.key));
    const snap = { pending, other, selected };
    setBusy((b) => new Set([...b, ...keys]));
    removeFromView(keys);
    const r = await run();
    setBusy((b) => new Set([...b].filter((k) => !keys.has(k))));
    if (isError(r)) {
      setPending(snap.pending);
      setOther(snap.other);
      setSelected(snap.selected);
      toast(r.error, "error");
      return false;
    }
    toast(done);
    announce();
    void load();
    return true;
  };

  const actProtocol = async (p: PendingProtocol, run: () => Promise<Envelope<unknown>>, done: string) => {
    const snap = protos;
    setProtoBusy((b) => new Set([...b, p.name]));
    setProtos((rows) => (rows ?? []).filter((r) => r.name !== p.name));
    const r = await run();
    setProtoBusy((b) => new Set([...b].filter((k) => k !== p.name)));
    if (isError(r)) {
      setProtos(snap);
      toast(r.error, "error");
      return;
    }
    toast(done);
    announce();
    void load();
  };
  const doApproveProtocol = (p: PendingProtocol) =>
    actProtocol(p, () => approveProtocol(p.name), `${p.protocol_name} is now the active protocol.`);
  const doSendBackProtocol = (p: PendingProtocol, note: string) =>
    actProtocol(p, () => sendBackProtocol(p.name, note), `Sent ${p.protocol_name} back to the supervisor.`);

  const plural = (n: number) => `${n} ${n === 1 ? "submission" : "submissions"}`;
  const names = (gs: ApprovalGroup[]) => gs.flatMap((g) => g.names);
  const doApprove = (gs: ApprovalGroup[]) => act(gs, () => approve(names(gs)), `Approved ${plural(gs.length)}. It now counts toward done work.`);
  const doSendBack = async (note: string) => {
    if (!dialog) return;
    setSending(true);
    setDialog(null);
    await act(dialog, () => sendBack(names(dialog), note), `Sent back ${plural(dialog.length)}.`);
    setSending(false);
  };
  const doResubmit = (g: ApprovalGroup, edits: ResubmitEdit[]) =>
    act([g], () => resubmit(g.names, edits.length ? edits : undefined), "Resubmitted. It is back with the manager for approval.");

  const chosen = groups.filter((g) => selected.has(g.key));
  const selectable = tab === "pending" || tab === "stale";
  const clear = () => {
    setRange(EMPTY_RANGE);
    setUnit("");
    setOperation("");
    setSupervisor("");
  };
  const sorted = (m: Map<string, string>) => [...m].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label));
  const c = counts;

  return (
    <PageShell
      title="Approvals"
      eyebrow={crop.name}
      tabs={
        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
          <TabsList aria-label="Approval status">
            {(
              [
                ["pending", "Pending", c?.Pending],
                ["stale", "Stale", c?.stale],
                ["sent", "Sent back", c?.["Sent Back"]],
                ["approved", "Approved", c?.Approved],
                ["protocols", "Protocols", protos?.length],
              ] as const
            ).map(([id, label, n]) => (
              <TabsTrigger key={id} value={id}>
                {label}
                {n != null && (
                  <span
                    data-testid={`count-${id}`}
                    className={`tabular-nums opacity-70 ${id === "stale" && n > 0 ? "text-[var(--sd-data-red)] opacity-100" : ""}`}
                  >
                    {n}
                  </span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      }
      actions={
        <>
          <DateRangePicker label="Period" value={range} onChange={setRange} />
          <FilterSelect label="Block" allLabel="All blocks" value={unit} onChange={setUnit} options={sorted(opts.units)} />
          <FilterSelect label="Operation" allLabel="All operations" value={operation} onChange={setOperation} options={sorted(opts.ops)} />
          <FilterSelect label="Supervisor" allLabel="All supervisors" value={supervisor} onChange={setSupervisor} options={sorted(opts.sups)} />
          <ClearFiltersPill active={dirty} onClear={clear} />
          <RefreshButton label="approvals" loading={loading} onClick={() => void load()} />
        </>
      }
    >
      <KpiGrid cols={showPay ? 4 : 3}>
        <KpiCard label="Awaiting approval" value={c?.Pending ?? 0} hint="submissions" loading={!pending} />
        <KpiCard
          label="Stale"
          value={c?.stale ?? 0}
          tone={(c?.stale ?? 0) > 0 ? "critical" : "default"}
          hint={pending ? `waiting ${pending.stale_days}+ days` : undefined}
          loading={!pending}
        />
        <KpiCard label="Quantity awaiting" value={qtyAwaiting} hint="not yet counted" loading={!pending} />
        {showPay && <KpiCard label="Pay awaiting" value={kes(payAwaiting)} hint="not yet in costs" loading={!pending} />}
      </KpiGrid>

      {tab === "protocols" ? (
        <ProtocolReview
          rows={protos}
          busy={protoBusy}
          canReview={crop.boot.can_manage}
          loading={loading}
          onApprove={(p) => void doApproveProtocol(p)}
          onSendBack={(p, n) => void doSendBackProtocol(p, n)}
        />
      ) : (
      <div className="flex flex-col gap-4" data-testid="approval-list">
        {waiting ? (
          [0, 1, 2].map((i) => (
            <div key={i} className="space-y-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] p-5 shadow-[var(--sd-shadow-1)]">
              <Bar className="h-5 w-56" />
              <Bar className="h-2 w-full" />
              <Bar className="h-16 w-full" />
            </div>
          ))
        ) : groups.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] px-6 py-14 text-center shadow-[var(--sd-shadow-1)]">
            <CheckCircle2 className="h-7 w-7 text-[var(--sd-quiet)]" />
            <h2 className="text-[15px] font-semibold text-[var(--sd-ink)]">{EMPTY[tab].title}</h2>
            <p className="max-w-sm text-[13px] text-[var(--sd-muted)]">{EMPTY[tab].hint}</p>
          </div>
        ) : (
          groups.map((g) => (
            <ApprovalCard
              key={g.key}
              group={g}
              showPay={showPay}
              selectable={selectable}
              selected={selected.has(g.key)}
              busy={busy.has(g.key)}
              onSelect={(on) =>
                setSelected((s) => {
                  const n = new Set(s);
                  if (on) n.add(g.key);
                  else n.delete(g.key);
                  return n;
                })
              }
              onApprove={() => void doApprove([g])}
              onSendBack={() => setDialog([g])}
              onResubmit={(e) => void doResubmit(g, e)}
            />
          ))
        )}
      </div>
      )}

      <ActionPill
        count={chosen.length}
        busy={sending || chosen.some((g) => busy.has(g.key))}
        onApprove={() => void doApprove(chosen)}
        onSendBack={() => setDialog(chosen)}
        onClear={() => setSelected(new Set())}
      />
      <SendBackDialog open={!!dialog} cards={dialog?.length ?? 0} busy={sending} onCancel={() => setDialog(null)} onConfirm={(n) => void doSendBack(n)} />
    </PageShell>
  );
}
