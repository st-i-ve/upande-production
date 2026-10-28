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

/** Links to the standalone avocado pages, shown under Forecast for the crops
 *  listed here. Keyed by crop_key: this is the only place a crop is named. */
export const EXTERNAL_LINKS: Record<string, { label: string; href: string }[]> = {
  avocado: [
    { label: "Production", href: "/avocado-production" },
    { label: "Outlook", href: "/avocado-outlook" },
    { label: "Calendar", href: "/avocado-calendar" },
    { label: "Maturity", href: "/avocado-maturity" },
  ],
};

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
    case "forecast":
      return "Forecast";
    case "settings":
      return "Settings";
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
  return createElement(CropContext.Provider, { value }, children);
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
