/**
 * Typed wrappers for `upande_production.api.protocols`.
 *
 * A protocol is a family of versions. Draft -> Pending Approval -> Active (the previous Active becomes
 * Superseded); a manager can send a version back to Draft with a note or reject it. Only Active
 * versions plan work; running cycles keep the version they started with. Every function resolves to an
 * `Envelope<T>`; check `isError(r)` first.
 */

import { call, type Envelope } from "@/lib/frappe";
import type { Breach } from "@/lib/rules";

const PREFIX = "upande_production.api.protocols.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

export type VersionStatus = "Draft" | "Pending Approval" | "Active" | "Superseded" | "Rejected";

export type ProtocolTable = "key_activities" | "cultural_activities" | "capital_activities";

/** A key activity: done in a given week of the cycle, in week order. */
export interface KeyActivity {
  operation: string | null;
  week: number | null;
  repeats: "Every cycle" | "First cycle only";
  planned_qty: number | null;
  description: string | null;
}

/** A cultural activity: repeated at an interval, or done as needed, after an establishment period. */
export interface CulturalActivity {
  operation: string | null;
  schedule: "Interval" | "As needed";
  interval_weeks: number | null;
  /** Weeks after planting / last harvest. */
  establishment_period_weeks: number | null;
  /** Days before harvest. */
  pre_harvest_interval_days: number | null;
  /** Stop after this many repeats; empty repeats until the cycle ends. */
  occurrences?: number | null;
  planned_qty: number | null;
  description: string | null;
}

/** A capital (set-up) activity with its budget per hectare. */
export interface CapitalActivity {
  operation: string | null;
  description: string | null;
  budget_per_ha: number | null;
}

/** Template values the protocol reads from its variety. */
export interface ProtocolTemplate {
  lifespan_years?: number | null;
  harvest_pattern?: string | null;
  harvest_interval_weeks?: number | null;
  is_flowering?: 0 | 1 | boolean;
  weeks_to_first_flowering?: number | null;
  weeks_flowering_to_harvest?: number | null;
  weeks_to_reflower_after_harvest?: number | null;
  plants_per_m2?: number | null;
  weeks_to_maturity?: number | null;
  flowering_pattern?: "Seasonal" | "Interval" | string | null;
  flowering_interval_weeks?: number | null;
  flowering_seasons?: { season_name: string; start_month: string }[];
}

export interface ProtocolTables {
  key_activities: KeyActivity[];
  cultural_activities: CulturalActivity[];
  capital_activities: CapitalActivity[];
}

export interface ProtocolVersion extends ProtocolTemplate, ProtocolTables {
  /** Document name; pass to every action. */
  name: string;
  protocol_name: string;
  crop: string;
  item: string | null;
  version: number;
  version_status: VersionStatus;
  protocol_family: string;
  previous_version: string | null;
  submitted_by: string | null;
  submitted_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  review_note: string | null;
  variety?: string | null;
}

export interface ProtocolFamily {
  family: string;
  /** The v1 name. */
  label: string;
  crop: string;
  item: string | null;
  /** Name of the Active version, if any. */
  active: string | null;
  has_pending: boolean;
  /** Newest first. */
  versions: ProtocolVersion[];
}

export type ProtocolRow = KeyActivity | CulturalActivity | CapitalActivity;

export interface StepChange {
  /** Which table the row belongs to. */
  table: ProtocolTable;
  change: "added" | "removed" | "changed";
  operation: string;
  operation_name: string;
  before?: ProtocolRow;
  after?: ProtocolRow;
  changes?: { field: string; before: unknown; after: unknown }[];
}

/** A protocol step that would land in a forbidden stage or window for the variety. */
export interface RuleCheckProblem {
  operation: string;
  operation_name: string;
  repeat: number;
  /** Days from the cycle start (or the step's anchor stage). */
  day: number;
  stage: string | null;
  rule_status: "OK" | "Warn" | "Block";
  breaches: Breach[];
}

export interface ProtocolDiff {
  rule_check?: RuleCheckProblem[];
  name: string;
  previous: string | null;
  fields: { field: string; before: unknown; after: unknown }[];
  /** Row changes of all three tables, each with its `table`. */
  steps: StepChange[];
}

export interface PendingProtocol extends ProtocolVersion {
  submitted_by_name: string | null;
  diff: ProtocolDiff;
}

export const listProtocolFamilies = (crop: string) => rpc<{ families: ProtocolFamily[] }>("list_protocols", { crop });
export const pendingProtocols = (crop?: string | null) =>
  rpc<{ rows: PendingProtocol[] }>("pending_protocols", { crop: crop ?? null });
export const newVersion = (name: string) => rpc<{ name: string; version: number }>("new_version", { name });
export const submitForApproval = (name: string) => rpc<{ name: string }>("submit_for_approval", { name });
/** Managers only. */
export const approveProtocol = (name: string) => rpc<{ name: string }>("approve", { name });
/** Managers only; the note is required. Goes back to Draft. */
export const sendBackProtocol = (name: string, note: string) => rpc<{ name: string }>("send_back", { name, note });
/** Managers only; the note is required. */
export const rejectProtocol = (name: string, note: string) => rpc<{ name: string }>("reject", { name, note });
export const protocolDiff = (name: string) => rpc<ProtocolDiff>("diff", { name });
/** Edit a Draft's item and its three activity tables. */
export const saveProtocolDraft = (data: { name: string; item?: string | null } & Partial<ProtocolTables>) =>
  rpc<{ name: string }>("save_draft", { data });

/** Steps of a version that break an activity rule for its variety. */
export const protocolRuleCheck = (name: string) => rpc<RuleCheckProblem[]>("rule_check", { name });
