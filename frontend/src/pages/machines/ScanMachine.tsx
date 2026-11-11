import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, Keyboard, MapPin, ScanLine } from "lucide-react";
import { PageShell } from "@/components/PageShell";
import { useToast } from "@/components/Toast";
import { QrCamera } from "@/components/machines/QrCamera";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Textarea } from "@/components/ui/textarea";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import {
  durationLabel,
  fixPayload,
  parseScanCode,
  readFixOnce,
  searchWithoutToken,
  tokenFromSearch,
  type Fix,
} from "@/lib/machine-scan";
import {
  allocationForm,
  closeAllocation,
  scanMachine,
  startAllocation,
  type Allocation,
  type AllocationForm,
  type ScanResult,
} from "@/lib/machines-api";
import { routeHash } from "@/lib/router";

type Stage =
  | { kind: "pick" }
  | { kind: "looking" }
  | { kind: "start" | "close"; token: string; scan: ScanResult; fix: Fix | null; reason: string | null }
  | { kind: "done"; allocation: Allocation; action: "started" | "closed" | "posted" };

function Field({ id, label, children, hint }: { id?: string; label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-[12px] text-[var(--sd-quiet)]">{hint}</p>}
    </div>
  );
}

function Position({ fix, reason }: { fix: Fix | null; reason: string | null }) {
  return (
    <p className="flex items-start gap-2 text-[12.5px] text-[var(--sd-muted)]" data-testid="scan-position">
      <MapPin className="mt-0.5 h-4 w-4 shrink-0" />
      {fix
        ? `Position at the scan: ${fix.latitude.toFixed(5)}, ${fix.longitude.toFixed(5)}${fix.accuracy != null ? ` (±${Math.round(fix.accuracy)} m)` : ""}`
        : reason ?? "No position."}
    </p>
  );
}

/**
 * Scan to allocate. A machine's QR code (read here with the camera, typed, or opened from the label
 * with any phone camera) starts an allocation when the machine is free and closes it when it is
 * running. The GPS position is read once, at that scan, and at no other time.
 */
export function ScanMachine() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [form, setForm] = useState<AllocationForm | null>(null);
  const [stage, setStage] = useState<Stage>({ kind: "pick" });
  const [camera, setCamera] = useState(false);
  const [cameraNote, setCameraNote] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [v, setV] = useState({ operator: "", allocated_to: "Feedlot", reference: "", cost_center: "", notes: "", litres: "" });
  const fromLink = useRef(false);

  useEffect(() => {
    let live = true;
    void allocationForm().then((r) => {
      if (!live) return;
      if (isError(r)) {
        toast(r.error, "error");
        return;
      }
      setForm(r as AllocationForm);
    });
    return () => {
      live = false;
    };
  }, [toast]);

  /** A code was scanned (or typed): read the ONE GPS fix now, and find the machine. */
  const handleCode = useCallback(
    async (text: string) => {
      const token = parseScanCode(text);
      setCamera(false);
      if (!token) {
        toast("That QR code is not a machine label.", "error");
        return;
      }
      setStage({ kind: "looking" });
      const [fixResult, scan] = await Promise.all([readFixOnce(), scanMachine(token)]);
      if (isError(scan)) {
        toast(scan.error, "error");
        setStage({ kind: "pick" });
        return;
      }
      const s = scan as ScanResult;
      setV((p) => ({ ...p, litres: "", notes: "" }));
      setStage({
        kind: s.open_allocation ? "close" : "start",
        token,
        scan: s,
        fix: fixResult.fix,
        reason: fixResult.fix ? null : fixResult.reason,
      });
    },
    [toast],
  );

  // Opened from a label with the phone's camera app: /production_app?machine=TOKEN#/…/scan.
  useEffect(() => {
    if (fromLink.current) return;
    const token = tokenFromSearch(window.location.search);
    if (!token) return;
    fromLink.current = true;
    window.history.replaceState(null, "", window.location.pathname + searchWithoutToken(window.location.search) + window.location.hash);
    void handleCode(token);
  }, [handleCode]);

  useEffect(() => {
    if (form) setV((p) => ({ ...p, operator: p.operator || form.me || "" }));
  }, [form]);

  const onUnavailable = useCallback((reason: string) => {
    setCamera(false);
    setCameraNote(reason);
  }, []);

  const refDoctype = form?.reference_doctypes[v.allocated_to];
  const refOptions = (refDoctype && form?.references[refDoctype]) || [];

  const start = async () => {
    if (stage.kind !== "start") return;
    if (!v.operator) {
      toast("Choose who is operating the machine.", "error");
      return;
    }
    setBusy(true);
    const r = await startAllocation({
      code: stage.token,
      operator: v.operator,
      allocated_to: v.allocated_to,
      reference_doctype: v.reference ? refDoctype : undefined,
      reference_name: v.reference || undefined,
      cost_center: v.cost_center || undefined,
      notes: v.notes.trim() || undefined,
      ...fixPayload(stage.fix),
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setStage({ kind: "done", allocation: r.allocation, action: "started" });
  };

  const litres = v.litres.trim() === "" ? null : Number(v.litres);
  const badLitres = litres != null && (!Number.isFinite(litres) || litres < 0);

  const close = async (submit: boolean) => {
    if (stage.kind !== "close" || badLitres) return;
    setBusy(true);
    const r = await closeAllocation({
      code: stage.token,
      diesel_litres: litres,
      notes: v.notes.trim() || undefined,
      submit: submit ? 1 : 0,
      ...fixPayload(stage.fix),
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setStage({ kind: "done", allocation: r.allocation, action: submit ? "posted" : "closed" });
  };

  const again = () => {
    setStage({ kind: "pick" });
    setTyped("");
  };

  return (
    <PageShell title={viewLabel("scan", crop)} eyebrow="Machines">
      <div className="flex max-w-xl flex-col gap-4">
        {stage.kind === "pick" && (
          <Card className="p-5">
            <div className="flex flex-col gap-4">
              <p className="text-[13px] text-[var(--sd-muted)]">
                Scan the QR label on the machine. A free machine is allocated to the operator; a running one is closed. Your location is read once, when the code is scanned.
              </p>
              {form && !form.can_allocate && (
                <p className="rounded-xl bg-[var(--sd-alert-warn)] px-4 py-3 text-[13px] text-[var(--sd-sev-high)]">You can see allocations but not start or close them.</p>
              )}
              {camera ? (
                <>
                  <QrCamera onCode={handleCode} onUnavailable={onUnavailable} />
                  <Button variant="outline" onClick={() => setCamera(false)}>
                    Stop the camera
                  </Button>
                </>
              ) : (
                <Button
                  size="lg"
                  onClick={() => {
                    setCameraNote(null);
                    setCamera(true);
                  }}
                  disabled={!form?.can_allocate}
                >
                  <Camera className="h-5 w-5" />
                  Scan with the camera
                </Button>
              )}
              {cameraNote && <p className="text-[12.5px] text-[var(--sd-sev-high)]">{cameraNote}</p>}
              <form
                className="flex items-end gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (typed.trim()) void handleCode(typed);
                }}
              >
                <div className="flex-1">
                  <Field id="scan-typed" label="Or type the code under the QR">
                    <Input id="scan-typed" value={typed} onChange={(e) => setTyped(e.target.value.toUpperCase())} autoCapitalize="characters" autoComplete="off" placeholder="e.g. 7F3A9C21B0" />
                  </Field>
                </div>
                <Button type="submit" variant="outline" disabled={!typed.trim() || !form?.can_allocate}>
                  <Keyboard className="h-4 w-4" />
                  Find
                </Button>
              </form>
            </div>
          </Card>
        )}

        {stage.kind === "looking" && (
          <Card className="p-5">
            <p className="flex items-center gap-2 text-[13px] text-[var(--sd-muted)]">
              <ScanLine className="h-4 w-4 animate-pulse" />
              Finding the machine and reading your position…
            </p>
          </Card>
        )}

        {stage.kind === "start" && form && (
          <Card className="overflow-hidden">
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>{stage.scan.machine.machine_name}</CardTitle>
                <CardDescription>{stage.scan.machine.machine_type} · free. Allocate it to start the clock.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <div className="flex flex-col gap-4 px-5 pb-5">
              <Position fix={stage.fix} reason={stage.reason} />
              <Field id="sa-op" label="Operator">
                <Picker id="sa-op" label="Operator" value={v.operator} onChange={(x) => setV({ ...v, operator: x })} options={form.employees} placeholder="Who drives it" />
              </Field>
              <Field id="sa-to" label="Allocated to">
                <Picker id="sa-to" label="Allocated to" value={v.allocated_to} onChange={(x) => setV({ ...v, allocated_to: x || "Feedlot", reference: "" })} options={form.allocated_to} />
              </Field>
              {refDoctype && (
                <Field id="sa-ref" label={refDoctype}>
                  <Picker id="sa-ref" label={refDoctype} value={v.reference} onChange={(x) => setV({ ...v, reference: x })} options={refOptions} clearable placeholder={`Which ${refDoctype.toLowerCase()}`} />
                </Field>
              )}
              <Field
                id="sa-cc"
                label="Cost centre"
                hint={
                  v.allocated_to === "Feedlot" && form.settings.feedlot_cost_center && !v.cost_center
                    ? `Charged to ${form.settings.feedlot_cost_center} unless you pick another.`
                    : "Left empty: the target's own cost centre, else the machine's default."
                }
              >
                <Picker id="sa-cc" label="Cost centre" value={v.cost_center} onChange={(x) => setV({ ...v, cost_center: x })} options={form.cost_centers} clearable clearLabel="Default" placeholder="Default" />
              </Field>
              <Field id="sa-notes" label="Notes">
                <Textarea id="sa-notes" rows={2} value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />
              </Field>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={again}>
                  Cancel
                </Button>
                <Button onClick={start} disabled={busy || !form.can_allocate}>
                  {busy ? "Allocating…" : "Allocate machine"}
                </Button>
              </div>
            </div>
          </Card>
        )}

        {stage.kind === "close" && stage.scan.open_allocation && (
          <Card className="overflow-hidden">
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>{stage.scan.machine.machine_name}</CardTitle>
                <CardDescription>
                  With {stage.scan.open_allocation.operator_name ?? stage.scan.open_allocation.operator} for {stage.scan.open_allocation.allocated_to}
                  {stage.scan.open_allocation.reference_name ? ` (${stage.scan.open_allocation.reference_name})` : ""} · running{" "}
                  {durationLabel(stage.scan.open_allocation.running_hours)}. Close it to stop the clock.
                </CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <div className="flex flex-col gap-4 px-5 pb-5">
              <Position fix={stage.fix} reason={stage.reason} />
              <Field id="sc-litres" label="Diesel used (litres)" hint={badLitres ? "Litres must be a number, 0 or more." : "Issued from the fuel warehouse when the allocation is posted."}>
                <Input id="sc-litres" type="number" min={0} step="0.1" inputMode="decimal" value={v.litres} onChange={(e) => setV({ ...v, litres: e.target.value })} />
              </Field>
              <Field id="sc-notes" label="Notes">
                <Textarea id="sc-notes" rows={2} value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />
              </Field>
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="outline" onClick={again}>
                  Cancel
                </Button>
                <Button variant="outline" onClick={() => close(false)} disabled={busy || badLitres || !form?.can_allocate}>
                  Close
                </Button>
                {form?.can_submit && (
                  <Button onClick={() => close(true)} disabled={busy || badLitres}>
                    {busy ? "Posting…" : "Close and post diesel"}
                  </Button>
                )}
              </div>
            </div>
          </Card>
        )}

        {stage.kind === "done" && (
          <Card className="p-5" data-testid="scan-done">
            <div className="flex flex-col gap-3">
              <p className="flex items-center gap-2 text-[15px] font-semibold">
                <CheckCircle2 className="h-5 w-5 text-[var(--sd-data-green)]" />
                {stage.action === "started"
                  ? `${stage.allocation.machine} allocated to ${stage.allocation.operator_name ?? stage.allocation.operator}.`
                  : stage.action === "posted"
                    ? `${stage.allocation.machine} closed after ${durationLabel(stage.allocation.duration_hours)}${stage.allocation.diesel_stock_entry ? "; diesel issued from stock" : ""}.`
                    : `${stage.allocation.machine} closed after ${durationLabel(stage.allocation.duration_hours)}. A manager posts its diesel.`}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button onClick={again}>Scan another machine</Button>
                <Button variant="outline" asChild>
                  <a href={routeHash(crop.crop_key, "allocations")}>See allocations</a>
                </Button>
              </div>
            </div>
          </Card>
        )}
      </div>
    </PageShell>
  );
}
