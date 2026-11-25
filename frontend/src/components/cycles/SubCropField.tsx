import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";

/** The sub-crop of a chosen crop (Spray rose of Rose). Renders nothing for a crop that has none. */
export function SubCropField({
  id,
  subCrops,
  value,
  onChange,
}: {
  id: string;
  subCrops: { name: string; harvest_uom?: string }[];
  value: string;
  onChange: (next: string) => void;
}) {
  if (!subCrops.length) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>Sub-crop</Label>
      <Picker id={id} label="Sub-crop" value={value} onChange={onChange} options={subCrops.map((s) => ({ value: s.name, label: s.name }))} placeholder="Choose a sub-crop…" />
    </div>
  );
}
