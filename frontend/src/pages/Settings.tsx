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
import { ProtocolsList } from "@/components/settings/ProtocolsList";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listOperations, listProtocols, type Row } from "@/lib/api";
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
  const [protocols, setProtocols] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [o, p] = await Promise.all([listOperations(crop.name), listProtocols(crop.name)]);
    setLoading(false);
    if (isError(o)) toast(o.error, "error");
    if (isError(p)) toast(p.error, "error");
    setOps(isError(o) ? [] : (o.rows ?? []));
    setProtocols(isError(p) ? [] : (p.rows ?? []));
  }, [crop.name, toast]);

  useEffect(() => {
    setOps(null);
    setProtocols(null);
    void load();
  }, [load]);

  const opNames = useMemo(
    () => Object.fromEntries((ops ?? []).map((o) => [String(o.name), String(o.operation_name ?? o.name)])),
    [ops],
  );

  const visibleProtocols = useMemo(
    () =>
      (protocols ?? []).filter(
        (p) => !q || matchesQuery(`${p.protocol_name ?? p.name} ${p.item ?? ""}`, q),
      ),
    [protocols, q],
  );

  const stats = useMemo(() => {
    const list = ops ?? [];
    const rates = list.map((o) => Number(o.default_rate)).filter((n) => Number.isFinite(n) && n > 0);
    const steps = (protocols ?? []).reduce((t, p) => t + ((p.steps as unknown[] | undefined)?.length ?? 0), 0);
    return {
      ops: list.length,
      harvest: list.filter((o) => !!Number(o.is_harvest ?? 0)).length,
      avgRate: rates.length ? rates.reduce((a, b) => a + b, 0) / rates.length : null,
      steps,
    };
  }, [ops, protocols]);

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
            <TabsTrigger value="operations">Operations &amp; rates</TabsTrigger>
            <TabsTrigger value="protocols">Protocols</TabsTrigger>
          </TabsList>
        }
        filters={[
          {
            key: "q",
            node: <SearchInput size="md" value={q} onChange={setQ} placeholder={tab === "protocols" ? "Search protocols" : "Search operations"} className="w-52" />,
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
          <KpiCard loading={first} label="Protocols" value={protocols?.length ?? 0} hint={`${stats.steps} steps in all`} />
          {canSeePay && <KpiCard loading={first} label="Average rate" value={kes(stats.avgRate)} hint="default rate per work unit" />}
        </div>

        <TabsContent value="operations" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Operations &amp; rates</CardTitle>
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
                <CardDescription>Repeating work schedules. Open one to see its steps.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent>
              {!protocols ? <RowsSkeleton rows={4} /> : <ProtocolsList protocols={visibleProtocols} opNames={opNames} />}
            </CardContent>
          </Card>
        </TabsContent>
      </PageShell>
    </Tabs>
  );
}
