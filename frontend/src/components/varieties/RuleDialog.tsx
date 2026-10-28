import { useMemo, useState } from "react";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Textarea } from "@/components/ui/textarea";
import { isError } from "@/lib/frappe";
import { CATEGORIES } from "@/lib/rules";
import { RULE_TYPES, saveRule, type ActivityRule, type RuleType, type Variety } from "@/lib/varieties-api";

export interface RuleForm {
  variety: string;
  stage: string;
  operation: string;
  category: string;
  rule_type: string;
  days: string;
  other_operation: string;
  other_category: string;
  enforcement: string;
  reason: string;
}

const STAGE_TYPES: string[] = ["Not in stage", "Only in stage"];
const DAY_TYPES: string[] = ["Not within days before harvest", "Not within days after operation"];

/** The first problem with a rule form, or null. Mirrors the server's checks. */
export function ruleProblem(f: RuleForm, stagesOf: string[]): string | null {
  if (!f.operation && !f.category) return "Pick the operation or the operation category the rule applies to.";
  if (!f.rule_type) return "Pick what the rule says.";
  if (STAGE_TYPES.includes(f.rule_type)) {
    if (!f.stage) return "A stage rule needs a stage.";
    if (f.variety && !stagesOf.includes(f.stage)) return "That stage is not a stage of the chosen variety.";
  }
  if (DAY_TYPES.includes(f.rule_type) && !(Number(f.days) > 0)) return "Days must be greater than zero.";
  if (f.rule_type === "Not within days after operation" && !f.other_operation && !f.other_category) {
    return "Pick the other operation or category this rule waits for.";
  }
  if (!f.enforcement) return "Choose Block or Warn.";
  return null;
}

export function toRuleForm(r: ActivityRule | null): RuleForm {
  return {
    variety: r?.variety ?? "",
    stage: r?.stage ?? "",
    operation: r?.operation ?? "",
    category: r?.operation_category ?? "",
    rule_type: r?.rule_type ?? "Not in stage",
    days: r?.days ? String(r.days) : "",
    other_operation: r?.other_operation ?? "",
    other_category: r?.other_category ?? "",
    enforcement: r?.enforcement ?? "Block",
    reason: r?.reason ?? "",
  };
}

export function RuleDialog({
  crop,
  rule,
  varieties,
  operations,
  onClose,
  onSaved,
}: {
  crop: string;
  /** Null to create. */
  rule: ActivityRule | null;
  varieties: Variety[];
  operations: { value: string; label: string }[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState<RuleForm>(() => toRuleForm(rule));
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const set = (p: Partial<RuleForm>) => {
    setF((x) => ({ ...x, ...p }));
    setFailure(null);
  };

  // Stage options come from the chosen variety; with none chosen, every stage name in the crop.
  const stageOptions = useMemo(() => {
    const pool = f.variety ? varieties.filter((v) => v.name === f.variety) : varieties;
    return [...new Set(pool.flatMap((v) => v.stages.map((s) => s.stage)))];
  }, [varieties, f.variety]);
  const stagesOf = stageOptions;
  const problem = ruleProblem(f, stagesOf);
  const isStage = STAGE_TYPES.includes(f.rule_type);
  const isDays = DAY_TYPES.includes(f.rule_type);

  async function save() {
    setBusy(true);
    const r = await saveRule({
      ...(rule ? { name: rule.name } : {}),
      crop,
      variety: f.variety || null,
      stage: isStage ? f.stage : null,
      operation: f.operation || null,
      operation_category: f.category || null,
      rule_type: f.rule_type as RuleType,
      days: isDays ? Number(f.days) : null,
      other_operation: f.rule_type === "Not within days after operation" ? f.other_operation || null : null,
      other_category: f.rule_type === "Not within days after operation" ? f.other_category || null : null,
      enforcement: f.enforcement as "Block" | "Warn",
      reason: f.reason.trim() || null,
      enabled: 1,
    });
    setBusy(false);
    if (isError(r)) {
      setFailure(r.error);
      return;
    }
    toast("Rule saved.");
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" aria-describedby="rule-desc">
        <DialogHeader>
          <DialogTitle>{rule ? "Edit rule" : "New activity rule"}</DialogTitle>
          <DialogDescription id="rule-desc">
            Block refuses the work outright. Warn lets it through once a reason is given, and flags it to the manager.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="r-type">The rule</Label>
            <Picker id="r-type" label="Rule type" value={f.rule_type} onChange={(v) => set({ rule_type: v })} options={RULE_TYPES} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="r-variety">Variety</Label>
            <Picker
              id="r-variety"
              label="Variety"
              value={f.variety}
              onChange={(v) => set({ variety: v, stage: "" })}
              options={varieties.map((v) => ({ value: v.name, label: v.variety_name }))}
              clearable
              clearLabel="Every variety"
              placeholder="Every variety"
            />
          </div>
          {isStage && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="r-stage">Stage</Label>
              <Picker id="r-stage" label="Stage" value={f.stage} onChange={(v) => set({ stage: v })} options={stageOptions} placeholder="Choose a stage" />
            </div>
          )}
          {isDays && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="r-days">Days</Label>
              <Input id="r-days" inputMode="numeric" className="tabular-nums" value={f.days} onChange={(e) => set({ days: e.target.value })} />
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="r-op">Operation</Label>
            <Picker id="r-op" label="Operation" value={f.operation} onChange={(v) => set({ operation: v })} options={operations} clearable clearLabel="Any (use category)" placeholder="Any (use category)" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="r-cat">Operation category</Label>
            <Picker id="r-cat" label="Operation category" value={f.category} onChange={(v) => set({ category: v })} options={[...CATEGORIES]} clearable clearLabel="None" placeholder="None" />
          </div>
          {f.rule_type === "Not within days after operation" && (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="r-oop">After operation</Label>
                <Picker id="r-oop" label="After operation" value={f.other_operation} onChange={(v) => set({ other_operation: v })} options={operations} clearable clearLabel="Any (use category)" placeholder="Any (use category)" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="r-ocat">After category</Label>
                <Picker id="r-ocat" label="After category" value={f.other_category} onChange={(v) => set({ other_category: v })} options={[...CATEGORIES]} clearable clearLabel="None" placeholder="None" />
              </div>
            </>
          )}
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label>When broken</Label>
            <div role="radiogroup" aria-label="Enforcement" className="flex gap-1 rounded-full bg-[var(--sd-bg-soft)] p-1 shadow-[var(--sd-shadow-inset)] sm:w-64">
              {["Block", "Warn"].map((e) => (
                <button
                  key={e}
                  type="button"
                  role="radio"
                  aria-checked={f.enforcement === e}
                  onClick={() => set({ enforcement: e })}
                  className={
                    "h-8 flex-1 rounded-full px-3 text-[12.5px] font-medium transition-colors " +
                    (f.enforcement === e ? "bg-[var(--sd-card)] text-[var(--sd-ink)] shadow-[var(--sd-shadow-1)]" : "text-[var(--sd-muted)] hover:text-[var(--sd-ink)]")
                  }
                >
                  {e}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="r-reason">Reason (shown to the person)</Label>
            <Textarea id="r-reason" value={f.reason} onChange={(e) => set({ reason: e.target.value })} placeholder="e.g. Pre-harvest interval of the chemical" />
          </div>
        </div>
        {failure && (
          <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px] text-[var(--sd-ink)]">
            {failure}
          </p>
        )}
        <div className="flex items-center justify-end gap-3">
          {problem && <span role="note" className="text-[12px] text-[var(--sd-amber)]">{problem}</span>}
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={save} disabled={busy || !!problem}>
            {busy ? "Saving…" : "Save rule"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
