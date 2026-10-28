/**
 * What an activity rule says when it is broken, and how to read it off an endpoint's error.
 *
 * The envelope's `{error}` also carries `breaches`, `rule_status` and `needs_override_reason` when a
 * rule was the cause: Block means refused outright, Warn means "allowed with a reason" (resend the
 * same call with `override_reason`).
 */

export interface Breach {
  rule: string;
  rule_type: string;
  enforcement: "Block" | "Warn";
  message: string;
}

export interface RuleFailure {
  error: string;
  breaches: Breach[];
  status: "Block" | "Warn";
  /** True when the call can be resent with an override reason. */
  needsReason: boolean;
}

/** The rule details of an error envelope, or null when the failure was something else. */
export function ruleFailure(r: unknown): RuleFailure | null {
  const e = r as { error?: unknown; breaches?: unknown; rule_status?: unknown; needs_override_reason?: unknown } | null;
  if (!e || typeof e.error !== "string" || !Array.isArray(e.breaches) || e.breaches.length === 0) return null;
  const status = e.rule_status === "Warn" ? "Warn" : "Block";
  return { error: e.error, breaches: e.breaches as Breach[], status, needsReason: !!e.needs_override_reason || status === "Warn" };
}

export const CATEGORIES = ["Spraying", "Weeding", "Fertilising", "Irrigation", "Harvesting", "Pruning", "Feeding", "Other"] as const;
