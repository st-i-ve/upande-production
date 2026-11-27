import { useCallback, useEffect, useState } from "react";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Switch } from "@/components/ui/switch";
import { isError } from "@/lib/frappe";
import { getLabourSettings, labourModeStatus, saveLabourSettings, type LabourModeStatus, type LabourSettings } from "@/lib/labourpay-api";

/** The one-line state of the Work Management link, in plain words. */
export function modeLine(s: Pick<LabourModeStatus, "wm_installed" | "wm_active">): string {
  if (s.wm_active) return "Work Management is installed — labour runs through it";
  if (s.wm_installed) return "Work Management is installed but switched off (Built-in only)";
  return "Work Management is not installed — production handles pay on its own";
}

type Draft = Record<string, string>;

const toDraft = (s: LabourSettings): Draft => ({
  labour_mode: s.labour_mode ?? "",
  pay_period: s.pay_period ?? "",
  pay_week_starts_on: s.pay_week_starts_on ?? "",
  pay_day: s.pay_day ?? "",
  daily_wage: s.daily_wage == null ? "" : String(s.daily_wage),
  duplicate_rule: s.duplicate_rule ?? "",
  multiple_jobs_per_day: s.multiple_jobs_per_day ?? "",
  attendance_required: String(Number(s.attendance_required) ? 1 : 0),
  attendance_source: s.attendance_source ?? "",
  max_backdate_days: String(s.max_backdate_days ?? 0),
  pay_reference_prefix: s.pay_reference_prefix ?? "",
});

const SELECTS: { key: string; label: string; help: string }[] = [
  { key: "labour_mode", label: "Labour mode", help: "Automatic uses Work Management for approvals and pay whenever it is installed. Built-in only keeps everything in production." },
  { key: "pay_period", label: "Pay period", help: "How often casual labour is paid. New pay runs default to this length." },
  { key: "pay_week_starts_on", label: "Pay week starts on", help: "The first day of the pay week, so a weekly or fortnightly run covers whole weeks." },
  { key: "pay_day", label: "Pay day", help: "The day people are paid." },
  { key: "duplicate_rule", label: "Duplicate work", help: "What happens when the same person, day, operation and block is keyed twice. Block refuses it, Warn lets it through with a message, Off ignores it." },
  { key: "multiple_jobs_per_day", label: "Several jobs in one day", help: "Whether one person may be recorded on different jobs in the same day. Warn allows it but tells the supervisor." },
  { key: "attendance_source", label: "Attendance source", help: "Where attendance comes from when it is required: marked in production, read from HRMS Attendance, or either." },
];

/**
 * The Labour & Pay settings: pay period, wages, the guards on keyed work and where attendance comes
 * from. Managers edit; everyone with the pay role reads. Values come from the server together with
 * the allowed choices for each dropdown.
 */
export function LabourPayPanel({ canEdit, canSeePay }: { canEdit: boolean; canSeePay: boolean }) {
  const toast = useToast();
  const [status, setStatus] = useState<LabourModeStatus | null>(null);
  const [options, setOptions] = useState<Record<string, string[]>>({});
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saved, setSaved] = useState<Draft | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const apply = useCallback((s: LabourSettings) => {
    const d = toDraft(s);
    setDraft(d);
    setSaved(d);
    setOptions(s.options ?? {});
    if (s.wm_installed !== undefined) setStatus({ mode: s.labour_mode as LabourModeStatus["mode"], wm_installed: !!s.wm_installed, wm_active: !!s.wm_active });
  }, []);

  useEffect(() => {
    let live = true;
    void Promise.all([labourModeStatus(), getLabourSettings()]).then(([m, s]) => {
      if (!live) return;
      if (!isError(m)) setStatus(m);
      if (isError(s)) {
        setFailure(s.error);
        return;
      }
      apply(s);
    });
    return () => {
      live = false;
    };
  }, [apply]);

  if (failure) return <p role="alert" className="text-[13px] text-[var(--sd-muted)]">{failure}</p>;
  if (!draft) return <RowsSkeleton rows={5} />;

  const set = (k: string, v: string) => setDraft((d) => (d ? { ...d, [k]: v } : d));
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);

  async function save() {
    if (!draft) return;
    setSaving(true);
    const values: Record<string, unknown> = {
      ...draft,
      attendance_required: Number(draft.attendance_required),
      max_backdate_days: Number(draft.max_backdate_days) || 0,
    };
    if (!canSeePay || draft.daily_wage === "") delete values.daily_wage;
    else values.daily_wage = Number(draft.daily_wage);
    const r = await saveLabourSettings(values);
    setSaving(false);
    if (isError(r)) return void toast(r.error, "error");
    apply(r);
    toast("Labour & Pay settings saved.");
  }

  const field = (key: string, label: string, help: string, control: React.ReactNode) => (
    <div key={key} className="flex flex-col gap-1.5">
      <Label htmlFor={`lp-${key}`}>{label}</Label>
      {control}
      <p className="text-[12px] text-[var(--sd-quiet)]">{help}</p>
    </div>
  );

  return (
    <div className="space-y-5" data-testid="labour-pay-panel">
      {status && (
        <div role="status" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-info)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          {modeLine(status)}
        </div>
      )}
      <div className="grid gap-5 md:grid-cols-2">
        {SELECTS.map((f) =>
          field(
            f.key,
            f.label,
            f.help,
            <Picker id={`lp-${f.key}`} label={f.label} value={draft[f.key] ?? ""} onChange={(v) => set(f.key, v)} options={options[f.key] ?? []} disabled={!canEdit} />,
          ),
        )}
        {canSeePay &&
          field(
            "daily_wage",
            "Daily wage",
            "A full day's pay. An operation with a daily target and no rate of its own is paid at the daily wage divided by the target.",
            <Input id="lp-daily_wage" type="number" min="0" inputMode="decimal" value={draft.daily_wage} disabled={!canEdit} onChange={(e) => set("daily_wage", e.target.value)} />,
          )}
        {field(
          "max_backdate_days",
          "Backdating limit (days)",
          "How many days back work may be keyed. 0 means no limit. Future dates are always refused.",
          <Input id="lp-max_backdate_days" type="number" min="0" step="1" value={draft.max_backdate_days} disabled={!canEdit} onChange={(e) => set("max_backdate_days", e.target.value)} />,
        )}
        {field(
          "pay_reference_prefix",
          "Payment reference prefix",
          "Put in front of the payment reference when a pay run is marked paid, for example MPESA-.",
          <Input id="lp-pay_reference_prefix" value={draft.pay_reference_prefix} disabled={!canEdit} onChange={(e) => set("pay_reference_prefix", e.target.value)} />,
        )}
        {field(
          "attendance_required",
          "Attendance required",
          "When on, work can only be keyed for a day the person was marked Present or Half Day.",
          <Switch id="lp-attendance_required" aria-label="Attendance required" checked={draft.attendance_required === "1"} disabled={!canEdit} onCheckedChange={(v) => set("attendance_required", v ? "1" : "0")} />,
        )}
      </div>
      {canEdit && (
        <div className="flex justify-end">
          <Button type="button" onClick={() => void save()} disabled={!dirty || saving}>
            {saving ? "Saving" : "Save labour settings"}
          </Button>
        </div>
      )}
    </div>
  );
}
