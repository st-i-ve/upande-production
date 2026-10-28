/**
 * Typed wrappers for `upande_production.api.protocols`.
 *
 * A protocol is a family of versions. Draft -> Pending Approval -> Active (the previous Active becomes
 * Superseded); a manager can send a version back to Draft with a note or reject it. Only Active
 * versions plan work; running cycles keep the version they started with. Every function resolves to an
 * `Envelope<T>`; check `isError(r)` first.
 */

import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.protocols.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

export type VersionStatus = "Draft" | "Pending Approval" | "Active" | "Superseded" | "Rejected";

export interface ProtocolStep {
  operation: string | null;
  day_offset: number | null;
  repeat_every_days: number | null;
  repeat_count: number | null;
  planned_qty: number | null;
  note: string | null;
}

export interface ProtocolVersion {
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
  steps: ProtocolStep[];
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

export interface StepChange {
  change: "added" | "removed" | "changed";
  operation: string;
  operation_name: string;
  before?: ProtocolStep;
  after?: ProtocolStep;
  changes?: { field: string; before: unknown; after: unknown }[];
}

export interface ProtocolDiff {
  name: string;
  previous: string | null;
  fields: { field: string; before: unknown; after: unknown }[];
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
/** Edit a Draft's item and steps. */
export const saveProtocolDraft = (data: { name: string; item?: string | null; steps?: Partial<ProtocolStep>[] }) =>
  rpc<{ name: string }>("save_draft", { data });
