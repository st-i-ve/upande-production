import "@testing-library/jest-dom/vitest";
import { render } from "@testing-library/react";
import { ToastProvider } from "@/components/Toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CropProvider } from "@/lib/crops";
import type { Boot, Crop } from "@/lib/api";

export const CROP: Crop = {
  name: "Test Crop",
  crop_key: "test-crop",
  accent_color: "#2a7",
  icon_key: "leaf",
  unit_label: "Block",
  parent_unit_label: "Pivot",
  sub_unit_label: "",
  yield_uom: "Kg",
};

export function renderPage(ui: React.ReactElement, boot: Partial<Boot> = {}, crop: Crop = CROP) {
  const b: Boot = { crops: [crop], farms: [], can_see_pay: true, can_plan: true, can_manage: true, ...boot };
  return render(
    <TooltipProvider>
      <ToastProvider>
        <CropProvider crop={crop} boot={b}>
          {ui}
        </CropProvider>
      </ToastProvider>
    </TooltipProvider>,
  );
}
