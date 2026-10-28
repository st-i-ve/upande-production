import { render } from "@testing-library/react";
import { ToastProvider } from "@/components/Toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Boot, Crop } from "@/lib/api";
import { CropProvider } from "@/lib/crops";

export const CROP: Crop = {
  name: "Avocado",
  crop_key: "avocado",
  accent_color: "#3f8f4f",
  icon_key: "avocado",
  unit_label: "Orchard Block",
  parent_unit_label: "Farm",
  sub_unit_label: "Tree",
  yield_uom: "Kg",
};

export const bootFor = (canSeePay = true): Boot => ({
  crops: [CROP],
  farms: ["Mutara"],
  can_see_pay: canSeePay,
  can_plan: true,
  can_manage: true,
});

export function renderPage(ui: React.ReactElement, canSeePay = true) {
  return render(
    <TooltipProvider>
      <ToastProvider>
        <CropProvider crop={CROP} boot={bootFor(canSeePay)}>
          {ui}
        </CropProvider>
      </ToastProvider>
    </TooltipProvider>,
  );
}
