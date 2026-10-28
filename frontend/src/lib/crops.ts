import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Apple, Carrot, Fish, Hexagon, Leaf, Sprout } from "lucide-react";
import { getBootstrap, type Boot, type Crop } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { useRoute, type View } from "@/lib/router";

type IconType = React.ComponentType<{ className?: string; style?: React.CSSProperties }>;

/** icon_key (a field on the Crop doc) -> lucide icon. Data, not logic. */
export const CROP_ICONS: Record<string, IconType> = {
  avocado: Leaf,
  fruit: Apple,
  vegetables: Carrot,
  fish: Fish,
  hive: Hexagon,
};
export const FALLBACK_ICON: IconType = Sprout;

export function cropIcon(iconKey: string | null | undefined): IconType {
  return (iconKey && CROP_ICONS[iconKey]) || FALLBACK_ICON;
}


/** Crops that never have crop cycles, used only when the bootstrap lacks the flag. */
const NO_CYCLE_KEYS = ["apiary", "aquaculture"];

/** Does this crop run in crop cycles? Bees and fish do not. Reads the Production Crop
 *  flag `uses_crop_cycles`, falling back to the crop key. */
export function cropUsesCycles(crop?: Pick<Crop, "crop_key" | "uses_crop_cycles"> | null): boolean {
  if (!crop) return true;
  if (crop.uses_crop_cycles != null) return !!crop.uses_crop_cycles;
  return !NO_CYCLE_KEYS.includes(crop.crop_key);
}

export function pluralise(word: string): string {
  if (!word) return word;
  if (/s$/i.test(word)) return word;
  if (/[^aeiou]y$/i.test(word)) return word.slice(0, -1) + "ies";
  return word + "s";
}

/** The label for a view, using the crop's own word for its unit. */
export function viewLabel(view: View, crop?: Pick<Crop, "unit_label"> | null): string {
  switch (view) {
    case "overview":
      return "Overview";
    case "blocks":
      return crop?.unit_label ? pluralise(crop.unit_label) : "Blocks";
    case "cycles":
      return "Crop Cycles";
    case "plan":
      return "Weekly Plan";
    case "value-adders":
      return "Value Adders";
    case "costs":
      return "Block Costs";
    case "establishment":
      return "Setup Costs";
    case "break-even":
      return "Break-even";
    case "forecast":
      return "Forecast";
    case "settings":
      return "Settings";
    case "approvals":
      return "Approvals";
    case "map":
      return "Coverage Map";
    case "outlook":
      return "Season Outlook";
    case "block-forecast":
      return "Block Forecast";
    case "harvest-calendar":
      return "Harvest Calendar";
    case "picking-plan":
      return "Picking Plan";
    case "dry-matter":
      return "Dry Matter";
    case "dry-matter-tests":
      return "Dry Matter Tests";
    case "hive-inspections":
      return "Hive Inspections";
    case "honey-harvest":
      return "Honey Harvest";
    case "pond-batches":
      return "Pond Batches";
    case "water-quality":
      return "Water Quality";
    case "feeding":
      return "Feeding & Mortality";
    case "irrigation":
      return "Pivot Irrigation";
    case "grading":
      return "Harvest Grading";
  }
}

// -- Bootstrap, loaded once --------------------------------------------------

let cache: Promise<Boot | { error: string }> | null = null;

/** One `get_bootstrap` per page load. A failure is not cached, so Retry works. */
export function loadBootstrap(force = false) {
  if (!cache || force) {
    cache = getBootstrap().then((r) => {
      if (isError(r)) cache = null;
      return r as Boot | { error: string };
    });
  }
  return cache;
}

export type BootState =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; boot: Boot };

export function useCrops(): BootState & { reload: () => void } {
  const [state, setState] = useState<BootState>({ status: "loading" });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    if (tick > 0) setState({ status: "loading" });
    void loadBootstrap(tick > 0).then((r) => {
      if (!live) return;
      setState(isError(r) ? { status: "error", error: r.error } : { status: "ready", boot: r as Boot });
    });
    return () => {
      live = false;
    };
  }, [tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}

// -- The crop the route names -------------------------------------------------

export type CurrentCrop = Crop & { crop: Crop; boot: Boot };

const CropContext = createContext<CurrentCrop | null>(null);

/** Provides the route's crop to every page. Rendered by App once the bootstrap
 *  has loaded and the route names a real crop. */
export function CropProvider({
  crop,
  boot,
  children,
}: {
  crop: Crop;
  boot: Boot;
  children: React.ReactNode;
}) {
  const value = useMemo<CurrentCrop>(() => ({ ...crop, crop, boot }), [crop, boot]);
  // display:contents keeps layout untouched; the variable is the crop's highlight colour.
  const style = { display: "contents", ...(crop.accent_color ? { "--crop-accent": crop.accent_color } : {}) } as React.CSSProperties;
  return createElement(CropContext.Provider, { value }, createElement("div", { style }, children));
}

/** The bootstrap crop object for the route's crop_key (its fields are spread
 *  onto the result and also available as `.crop`), plus `boot`. */
export function useCurrentCrop(): CurrentCrop {
  const v = useContext(CropContext);
  if (!v) throw new Error("useCurrentCrop must be used inside <CropProvider>");
  return v;
}

/** Resolve the route's crop against the bootstrap list; null if it names none. */
export function useRouteCrop(boot: Boot | null): Crop | null {
  const [route] = useRoute();
  if (!boot || !route.crop) return null;
  return boot.crops.find((c) => c.crop_key === route.crop) ?? null;
}
