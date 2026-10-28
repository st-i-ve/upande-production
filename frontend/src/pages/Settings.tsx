import { useCallback, useEffect, useMemo, useState } from "react";
import { Lock } from "lucide-react";
import { RowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { OperationsTable } from "@/components/settings/OperationsTable";
import { ProtocolsList } from "@/components/settings/ProtocolsList";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listOperations, listProtocols, type Row } from "@/lib/api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";

/**
 * Operations (with their default rates) and protocols for the crop. Editing is
 * for managers; everyone else reads the same lists.
 */
export function Settings() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const canManage = crop.boot.can_manage;
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

  return (
    <PageShell
      title={viewLabel("settings", crop)}
      eyebrow={crop.name}
      description={`The operations, default rates and protocols used to plan work on ${crop.name.toLowerCase()}.`}
      actions={<RefreshButton onClick={load} loading={loading} label="the settings" />}
    >
      {!canManage && (
        <div role="note" className="flex items-center gap-2.5 rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-info)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          <Lock className="h-4 w-4 shrink-0 text-[var(--sd-quiet)]" />
          You can read these settings but not change them.
        </div>
      )}

      <Card>
        <CardContent className="pt-5">
          <Tabs defaultValue="operations" className="flex flex-col gap-4">
            <TabsList className="self-start">
              <TabsTrigger value="operations">Operations &amp; rates</TabsTrigger>
              <TabsTrigger value="protocols">Protocols</TabsTrigger>
            </TabsList>
            <TabsContent value="operations">
              <CardHeaderRow className="px-0 pt-0">
                <CardHeading>
                  <CardTitle>Operations &amp; rates</CardTitle>
                  <CardDescription>
                    {canManage ? "Edit a row, then save it. Rates are in KES per work unit." : "Rates are in KES per work unit."}
                  </CardDescription>
                </CardHeading>
              </CardHeaderRow>
              {!ops ? (
                <RowsSkeleton rows={6} />
              ) : (
                <OperationsTable crop={crop.name} rows={ops} canEdit={canManage} canSeePay={crop.boot.can_see_pay} onSaved={load} />
              )}
            </TabsContent>
            <TabsContent value="protocols">
              <CardHeaderRow className="px-0 pt-0">
                <CardHeading>
                  <CardTitle>Protocols</CardTitle>
                  <CardDescription>Repeating work schedules. Open one to see its steps.</CardDescription>
                </CardHeading>
              </CardHeaderRow>
              {!protocols ? <RowsSkeleton rows={4} /> : <ProtocolsList protocols={protocols} opNames={opNames} />}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </PageShell>
  );
}
