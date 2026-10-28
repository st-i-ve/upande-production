import { useState } from "react";
import { Ban, Pencil, Plus, RotateCcw } from "lucide-react";
import { EnforcementPill } from "@/components/rules/RuleParts";
import { RuleDialog } from "@/components/varieties/RuleDialog";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { isError } from "@/lib/frappe";
import { RULE_TYPES, setRuleEnabled, type ActivityRule, type Variety } from "@/lib/varieties-api";

const CARD = "rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] shadow-[var(--sd-shadow-1)]";
const CHIP = "inline-flex items-center rounded-full bg-[var(--sd-bg-soft)] px-2.5 py-0.5 text-[11.5px] font-medium text-[var(--sd-muted)]";

/** Scope chips of a rule: variety, stage, operation or category. */
export function ruleScope(r: ActivityRule, varietyName: (id: string) => string, opName: (id: string) => string): string[] {
  const chips = [r.variety ? varietyName(r.variety) : "All varieties"];
  if (r.stage) chips.push(`Stage: ${r.stage}`);
  chips.push(r.operation ? opName(r.operation) : r.operation_category ? `Any ${r.operation_category.toLowerCase()}` : "Any operation");
  if (r.rule_type === "Not within days after operation") {
    chips.push(`After ${r.other_operation ? opName(r.other_operation) : (r.other_category ?? "other work")}`);
  }
  return chips;
}

/** The crop's activity rules grouped by type. */
export function RulesPanel({
  crop,
  rules,
  varieties,
  operations,
  canEdit,
  onChanged,
}: {
  crop: string;
  rules: ActivityRule[];
  varieties: Variety[];
  operations: { value: string; label: string }[];
  canEdit: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState<ActivityRule | null | undefined>(undefined);
  const varietyName = (id: string) => varieties.find((v) => v.name === id)?.variety_name ?? id;
  const opName = (id: string) => operations.find((o) => o.value === id)?.label ?? id;

  async function toggle(r: ActivityRule) {
    const res = await setRuleEnabled(r.name, !Number(r.enabled));
    if (isError(res)) {
      toast(res.error, "error");
      return;
    }
    toast(Number(r.enabled) ? "Rule disabled." : "Rule enabled.");
    onChanged();
  }

  return (
    <div className="flex flex-col gap-4">
      {canEdit && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setEditing(null)}>
            <Plus className="h-4 w-4" /> New rule
          </Button>
        </div>
      )}
      {rules.length === 0 && <p className="text-[13px] text-[var(--sd-muted)]">No activity rules for {crop} yet.</p>}
      {RULE_TYPES.map((t) => {
        const list = rules.filter((r) => r.rule_type === t);
        if (!list.length) return null;
        return (
          <section key={t} className={CARD} aria-label={t}>
            <h3 className="px-4 pb-1 pt-3.5 text-[13px] font-semibold uppercase tracking-[0.08em] text-[var(--sd-quiet)]">{t}</h3>
            <ul className="divide-y divide-[var(--sd-line-soft)] px-1.5 pb-1.5">
              {list.map((r) => (
                <li key={r.name} data-testid={`rule-${r.name}`} className={"flex flex-wrap items-center gap-x-3 gap-y-2 px-2.5 py-2.5 " + (Number(r.enabled) ? "" : "opacity-55")}>
                  <EnforcementPill status={r.enforcement} />
                  <span className="flex min-w-[12rem] flex-1 flex-wrap gap-1.5">
                    {ruleScope(r, varietyName, opName).map((c) => (
                      <span key={c} className={CHIP}>
                        {c}
                      </span>
                    ))}
                    {r.days ? <span className={CHIP}>{r.days} days</span> : null}
                  </span>
                  <span className="min-w-[10rem] max-w-[24rem] flex-1 break-words text-[12.5px] text-[var(--sd-muted)]">{r.reason || "No reason given"}</span>
                  {!Number(r.enabled) && <span className={CHIP}>Disabled</span>}
                  {canEdit && (
                    <span className="flex gap-1">
                      <Button variant="outline" size="sm" aria-label={`Edit rule ${r.name}`} onClick={() => setEditing(r)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="outline" size="sm" aria-label={`${Number(r.enabled) ? "Disable" : "Enable"} rule ${r.name}`} onClick={() => void toggle(r)}>
                        {Number(r.enabled) ? <Ban className="h-3.5 w-3.5" /> : <RotateCcw className="h-3.5 w-3.5" />}
                      </Button>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      {editing !== undefined && (
        <RuleDialog
          crop={crop}
          rule={editing}
          varieties={varieties}
          operations={operations}
          onClose={() => setEditing(undefined)}
          onSaved={() => {
            setEditing(undefined);
            onChanged();
          }}
        />
      )}
    </div>
  );
}
