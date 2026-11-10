import { useState } from "react";
import { RosterView } from "@/components/casuallabourers/RosterView";
import { WorkView } from "@/components/casuallabourers/WorkView";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Tab = "labourers" | "work";

/** Casual labour: the roster with KPIs against daily targets, and the work done by person, day or
 *  block. Pay is per unit of work; there is no hourly pay. */
export function CasualLabourers() {
  const [tab, setTab] = useState<Tab>("labourers");
  const tabs = (
    <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
      <TabsList aria-label="Casual labour view">
        <TabsTrigger value="labourers">Labourers</TabsTrigger>
        <TabsTrigger value="work">Work</TabsTrigger>
      </TabsList>
    </Tabs>
  );
  return tab === "labourers" ? <RosterView tabs={tabs} /> : <WorkView tabs={tabs} />;
}
