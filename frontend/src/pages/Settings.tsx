import { useCallback, useEffect, useMemo, useState } from "react";
import { Lock } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { RowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { SearchInput } from "@/components/SearchInput";
import { useToast } from "@/components/Toast";
import { CATEGORIES, OperationsTable } from "@/components/settings/OperationsTable";
import { ProtocolsList, type ProtocolActions } from "@/components/settings/ProtocolsList";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BlockLinksPanel } from "@/components/settings/BlockLinksPanel";
import { RulesPanel } from "@/components/varieties/RulesPanel";
import { VarietiesPanel } from "@/components/varieties/VarietiesPanel";
import { listOperations, listProtocols, type Row } from "@/lib/api";
import { listRules, listVarieties, type ActivityRule, type Variety } from "@/lib/varieties-api";
import {
  approveProtocol,
  listProtocolFamilies,
  newVersion,
  saveProtocolDraft,
  sendBackProtocol,
  submitForApproval,
  type ProtocolFamily,
} from "@/lib/protocols-api";
import { APPROVALS_CHANGED } from "@/pages/Approvals";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { kes } from "@/lib/format";
import { matchesQuery } from "@/lib/utils";

/**
 * Operations (with their default rates) and protocols for the crop, laid out
 * like SCP's Spray Plan Settings: pill tabs in the toolbar, a short summary
 * row, then one card per section. Editing is for managers; everyone else
 * reads the same lists.
 */
export function Settings() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const canManage = crop.boot.can_manage;
  const canSeePay = crop.boot.can_see_pay;
  const [tab, setTab] = useState("operations");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [ops, setOps] = useState<Row[] | null>(null);
  const [protocols, setProtocols] = useState<ProtocolFamily[] | null>(null);
  const [varieties, setVarieties] = useState<Variety[] | null>(null);
  const [rules, setRules] = useState<ActivityRule[] | null>(null);
  const [activeProtocols, setActiveProtocols] = useState<{ value: string; label: string }[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [o, p, v, r, ap] = await Promise.all([
      listOperations(crop.name),
      listProtocolFamilies(crop.name),
      listVarieties(crop.name),
      listRules(crop.name),
      listProtocols(crop.name),
    ]);
    setLoading(false);
    if (isError(o)) toast(o.error, "error");
    if (isError(p)) toast(p.error, "error");
    if (isError(v)) toast(v.error, "error");
    if (isError(r)) toast(r.error, "error");
    setVarieties(isError(v) ? [] : (v.varieties ?? []));
    setRules(isError(r) ? [] : (r.rules ?? []));
    setActiveProtocols(isError(ap) ? [] : (ap.rows ?? []).map((x) => ({ value: String(x.name), label: String(x.protocol_name ?? x.name) })));
    setOps(isError(o) ? [] : (o.rows ?? []));
    setProtocols(isError(p) ? [] : (p.families ?? []));
  }, [crop.name, toast]);

  useEffect(() => {
    setOps(null);
    setProtocols(null);
    setVarieties(null);
    setRules(null);
    void load();
  }, [load]);

  const protocolOps = useMemo(
    () => (ops ?? []).map((o) => ({ value: String(o.name), label: String(o.operation_name ?? o.name), type: String(o.activity_type ?? "Cultural") })),
    [ops],
  );

  const opOptions = useMemo(() => (ops ?? []).map((o) => ({ value: String(o.name), label: String(o.operation_name ?? o.name) })), [ops]);
  const visibleVarieties = useMemo(
    () => (varieties ?? []).filter((v) => !q || matchesQuery(`${v.variety_name} ${v.item}`, q)),
    [varieties, q],
  );
  const visibleRules = useMemo(
    () =>
      (rules ?? []).filter(
        (r) => !q || matchesQuery(`${r.rule_type} ${r.variety ?? ""} ${r.stage ?? ""} ${r.operation ?? ""} ${r.operation_category ?? ""} ${r.reason ?? ""}`, q),
      ),
    [rules, q],
  );

  const visibleProtocols = useMemo(
    () =>
      (protocols ?? []).filter(
        (p) => !q || matchesQuery(`${p.label} ${p.item ?? ""}`, q),
      ),
    [protocols, q],
  );

  const stats = useMemo(() => {
    const list = ops ?? [];
    const rates = list.map((o) => Number(o.default_rate)).filter((n) => Number.isFinite(n) && n > 0);
    const steps = (protocols ?? []).reduce(
      (t, p) => {
        const v = p.versions.find((x) => x.name === p.active) ?? p.versions[0];
        return t + (v ? (v.key_activities?.length ?? 0) + (v.cultural_activities?.length ?? 0) : 0);
      },
      0,
    );
    return {
      ops: list.length,
      harvest: list.filter((o) => !!Number(o.is_harvest ?? 0)).length,
      avgRate: rates.length ? rates.reduce((a, b) => a + b, 0) / rates.length : null,
      steps,
    };
  }, [ops, protocols]);

  const run = useCallback(
    async (r: Promise<{ error: string } | object>, done: string) => {
      const res = await r;
      if (isError(res as never)) {
        toast((res as { error: string }).error, "error");
        return;
      }
      toast(done);
      window.dispatchEvent(new Event(APPROVALS_CHANGED));
      await load();
    },
    [load, toast],
  );
  const actions = useMemo<ProtocolActions>(
    () => ({
      newVersion: (v) => void run(newVersion(v.name), "New draft version created."),
      submit: (v) => void run(submitForApproval(v.name), "Submitted for approval."),
      approve: (v) => void run(approveProtocol(v.name), "Approved. This version is now active."),
      sendBack: (v, note) => void run(sendBackProtocol(v.name, note), "Sent back to draft."),
      saveDraft: (v, tables) => void run(saveProtocolDraft({ name: v.name, ...tables }), "Draft saved."),
    }),
    [run],
  );

  const first = firstLoad(loading, !!ops && !!protocols);
  const dirty = !!q || !!category;
  const categories = useMemo(() => {
    const seen = new Set((ops ?? []).map((o) => String(o.category ?? "")).filter(Boolean));
    return CATEGORIES.filter((c) => seen.has(c)).concat([...seen].filter((c) => !CATEGORIES.includes(c)));
  }, [ops]);

  return (
    <Tabs value={tab} onValueChange={setTab} className="flex min-w-0 flex-1 flex-col">
      <PageShell
        title={viewLabel("settings", crop)}
        eyebrow={crop.name}
        tab={tab}
        description={`The operations, default rates and protocols used to plan work on ${crop.name.toLowerCase()}.`}
        tabs={
          <TabsList>
            <TabsTrigger value="operations">Activities &amp; rates</TabsTrigger>
            <TabsTrigger value="protocols">Protocols</TabsTrigger>
            <TabsTrigger value="varieties">Varieties</TabsTrigger>
            <TabsTrigger value="rules">Activity rules</TabsTrigger>
            <TabsTrigger value="links">Block links</TabsTrigger>
          </TabsList>
        }
        filters={[
          {
            key: "q",
            node: <SearchInput size="md" value={q} onChange={setQ} placeholder={tab === "protocols" ? "Search protocols" : tab === "varieties" ? "Search varieties" : tab === "rules" ? "Search rules" : "Search operations"} className="w-52" />,
          },
          {
            key: "category",
            tabs: ["operations"],
            node: <FilterSelect label="Category" value={category} onChange={setCategory} options={categories} allLabel="All categories" />,
          },
        ]}
        actions={
          <>
            <ClearFiltersPill
              active={dirty}
              onClear={() => {
                setQ("");
                setCategory("");
              }}
            />
            <RefreshButton onClick={load} loading={loading} label="the settings" />
          </>
        }
      >
        {!canManage && (
          <div role="note" className="flex items-center gap-2.5 rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-info)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
            <Lock className="h-4 w-4 shrink-0 text-[var(--sd-quiet)]" />
            You can read these settings but not change them.
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <KpiCard loading={first} label="Operations" value={stats.ops} hint="defined for this crop" />
          <KpiCard loading={first} label="Harvest operations" value={stats.harvest} hint="count toward harvest quantity" />
          <KpiCard loading={first} label="Protocols" value={protocols?.length ?? 0} hint={`${stats.steps} activities in all`} />
          {canSeePay && <KpiCard loading={first} label="Average rate" value={kes(stats.avgRate)} hint="default rate per work unit" />}
        </div>

        <TabsContent value="operations" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Activities &amp; rates</CardTitle>
                <CardDescription>
                  {canManage ? "Edit a row, then save it. Rates are in KES per work unit." : "Rates are in KES per work unit."}
                </CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent>
              {!ops ? (
                <RowsSkeleton rows={6} />
              ) : (
                <OperationsTable crop={crop.name} rows={ops} canEdit={canManage} canSeePay={canSeePay} onSaved={load} query={q} category={category} />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="protocols" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Protocols</CardTitle>
                <CardDescription>Repeating work schedules, versioned. Only the active version plans work; changes need a manager's approval.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent>
              {!protocols ? <RowsSkeleton rows={4} /> : <ProtocolsList families={visibleProtocols} operations={protocolOps} canPlan={crop.boot.can_plan} canManage={canManage} actions={actions} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="varieties" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Varieties</CardTitle>
                <CardDescription>Each variety is its own stock item, with growth stages that restrict what work can happen when.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent>
              {!varieties ? (
                <RowsSkeleton rows={4} />
              ) : (
                <VarietiesPanel crop={crop.name} accent={crop.accent_color || "#3f7d3a"} varieties={visibleVarieties} protocols={activeProtocols} canEdit={canManage} onChanged={load} />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rules" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Activity rules</CardTitle>
                <CardDescription>What a stage or the harvest date forbids. Block refuses the work; Warn needs a reason and is flagged to the manager.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent>
              {!rules || !varieties ? (
                <RowsSkeleton rows={4} />
              ) : (
                <RulesPanel crop={crop.name} rules={visibleRules} varieties={varieties} operations={opOptions} canEdit={canManage} onChanged={load} />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="links" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Block links</CardTitle>
                <CardDescription>Each block needs a cost centre and a warehouse of the same name, so chemicals issued to it are costed to it.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent>
              <BlockLinksPanel crop={crop.name} unitLabel={crop.unit_label || "Block"} query={q} />
            </CardContent>
          </Card>
        </TabsContent>
      </PageShell>
    </Tabs>
  );
}
