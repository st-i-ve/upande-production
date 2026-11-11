import { useEffect, useState } from "react";
import { Printer } from "lucide-react";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { bootstrap, isError } from "@/lib/frappe";
import { LABEL_SIZES, labelLayout, labelsHtml, type LabelSizeId } from "@/lib/machine-scan";
import { machineLabels, type MachineLabel } from "@/lib/machines-api";

const SIZE_KEY = "production:machine-label-size";

function savedSize(): LabelSizeId {
  try {
    const v = window.localStorage.getItem(SIZE_KEY);
    if (v && LABEL_SIZES.some((s) => s.id === v)) return v as LabelSizeId;
  } catch {
    /* storage blocked: the default size */
  }
  return LABEL_SIZES[0].id;
}

/**
 * QR labels for machines, one per page at the chosen label size (SCP's Labels page sizes). The
 * preview is the first label; Print opens the labels in a new window and hands it to the printer.
 */
export function LabelPrintDialog({
  open,
  onOpenChange,
  machines,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  /** machine names to print */
  machines: string[];
}) {
  const toast = useToast();
  const [size, setSize] = useState<LabelSizeId>(savedSize);
  const [labels, setLabels] = useState<MachineLabel[] | null>(null);

  useEffect(() => {
    if (!open) return;
    let live = true;
    setLabels(null);
    void machineLabels(machines).then((r) => {
      if (!live) return;
      if (isError(r)) {
        toast(r.error, "error");
        onOpenChange(false);
        return;
      }
      setLabels(r.labels);
    });
    return () => {
      live = false;
    };
  }, [open, machines, toast, onOpenChange]);

  const dims = LABEL_SIZES.find((s) => s.id === size) ?? LABEL_SIZES[0];
  const L = labelLayout(dims.w, dims.h);
  const first = labels?.[0];
  const scale = Math.min(1, 360 / (dims.w * 3.78));

  const print = () => {
    if (!labels?.length) return;
    try {
      window.localStorage.setItem(SIZE_KEY, size);
    } catch {
      /* not remembered */
    }
    const w = window.open("", "_blank");
    if (!w) {
      toast("The browser blocked the print window.", "error", { hint: "Allow pop-ups for this site and try again." });
      return;
    }
    w.document.open();
    w.document.write(labelsHtml(labels, dims.w, dims.h, bootstrap().site_name));
    w.document.close();
    w.onload = () => {
      w.focus();
      w.print();
    };
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Print QR labels</DialogTitle>
          <DialogDescription>
            {machines.length === 1 ? "One label." : `${machines.length} labels, one per page.`} Stick it where the operator
            can scan it from the step: the code opens the scan screen on any phone.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="label-size">Label size</Label>
          <Picker id="label-size" label="Label size" value={size} onChange={(x) => setSize((x || LABEL_SIZES[0].id) as LabelSizeId)} options={LABEL_SIZES.map((s) => ({ value: s.id, label: s.label }))} />
        </div>
        <div className="flex min-h-[180px] items-center justify-center rounded-xl bg-[var(--sd-bg-soft)] p-4">
          {first ? (
            <div
              data-testid="label-preview"
              className="bg-white text-black shadow-[var(--sd-shadow-1)]"
              style={{
                width: `${dims.w}mm`,
                height: `${dims.h}mm`,
                padding: `${L.pad}mm`,
                display: "flex",
                flexDirection: L.orientation === "stack" ? "column" : "row",
                alignItems: "center",
                justifyContent: L.orientation === "stack" ? "center" : "flex-start",
                gap: `${L.pad}mm`,
                textAlign: L.orientation === "stack" ? "center" : "left",
                transform: `scale(${scale})`,
                transformOrigin: "center",
              }}
            >
              {first.image ? (
                <img src={first.image} alt={`QR for ${first.machine_name}`} style={{ width: `${L.qr}mm`, height: `${L.qr}mm`, flex: `0 0 ${L.qr}mm` }} />
              ) : (
                <div style={{ width: `${L.qr}mm`, height: `${L.qr}mm` }} className="border border-dashed border-black" />
              )}
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: `${L.titlePt}pt`, fontWeight: 700, lineHeight: 1.05 }}>{first.machine_name}</div>
                <div style={{ fontSize: `${L.textPt}pt` }}>{first.machine_type}</div>
                <div style={{ fontSize: `${L.textPt}pt`, fontFamily: "ui-monospace, monospace", letterSpacing: "0.08em" }}>{first.qr_code}</div>
              </div>
            </div>
          ) : (
            <p className="text-[13px] text-[var(--sd-muted)]">{labels ? "No machines to print." : "Making the QR codes…"}</p>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button onClick={print} disabled={!labels?.length}>
            <Printer className="h-4 w-4" />
            Print {labels?.length ?? ""} label{labels?.length === 1 ? "" : "s"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
