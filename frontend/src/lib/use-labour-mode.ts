import { useEffect, useState } from "react";
import { isError } from "@/lib/frappe";
import { labourModeStatus, type LabourModeStatus } from "@/lib/labourpay-api";

/** Whether Work Management is driving labour (`wm_active`). Null until the server answers; a failed read counts as built-in. */
export function useLabourMode(): LabourModeStatus | null {
  const [status, setStatus] = useState<LabourModeStatus | null>(null);
  useEffect(() => {
    let live = true;
    void labourModeStatus().then((r) => {
      if (live) setStatus(isError(r) ? { mode: "Built-in only", wm_installed: false, wm_active: false } : r);
    });
    return () => {
      live = false;
    };
  }, []);
  return status;
}
