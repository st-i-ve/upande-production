import type { Bands } from "@/lib/bands";

/** The bands the server seeds (production/demo/bands_seed.py), as a page payload carries them. */
const row = (band_set: string, label: string, min: number, max: number | null, severity: "Good" | "Watch" | "Critical") => ({
  band_set, label, metric: "", min, max, severity,
});

export const BANDS: Bands = {
  "Forecast error": [row("Forecast error", "Within 10%", 0, 10, "Good"), row("Forecast error", "Within 25%", 10, 25, "Watch"), row("Forecast error", "Beyond 25%", 25, null, "Critical")],
  "Estimate accuracy": [row("Estimate accuracy", "Needs review", 0, 90, "Watch"), row("Estimate accuracy", "Accurate", 90, null, "Good")],
  "Irrigation % of target": [
    row("Irrigation % of target", "Under 50% of target", 0, 50, "Critical"), row("Irrigation % of target", "50-90%", 50, 90, "Watch"),
    row("Irrigation % of target", "On target (90-125%)", 90, 125, "Good"), row("Irrigation % of target", "Over 125%", 125, null, "Watch"),
  ],
  "Fish survival": [row("Fish survival", "Low", 0, 90, "Critical"), row("Fish survival", "On track", 90, null, "Good")],
  "Queen status": [row("Queen status", "queenless", 0, 80, "Critical"), row("Queen status", "weak", 80, 95, "Watch"), row("Queen status", "queenright", 95, null, "Good")],
  "Grade A share": [row("Grade A share", "Low", 0, 60, "Watch"), row("Grade A share", "Healthy", 60, null, "Good")],
};
