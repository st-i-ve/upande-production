import { useCallback, useEffect, useRef, useState } from "react";
import { bootstrap } from "@/lib/frappe";

const MAX_AGE_MS = 7 * 24 * 3600 * 1000;
const DEBOUNCE_MS = 1000;

export function draftStorageKey(key: string): string {
  return `draft:${bootstrap().user || "anon"}:${key}`;
}

function read<T>(k: string): T | null {
  try {
    const raw = localStorage.getItem(k);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { at?: number; value?: T };
    if (!parsed || typeof parsed.at !== "number" || Date.now() - parsed.at > MAX_AGE_MS) {
      localStorage.removeItem(k);
      return null;
    }
    return parsed.value ?? null;
  } catch {
    return null;
  }
}

function write(k: string, value: unknown) {
  try {
    localStorage.setItem(k, JSON.stringify({ at: Date.now(), value }));
  } catch {
    /* storage unavailable or full: drafts are best effort */
  }
}

function remove(k: string) {
  try {
    localStorage.removeItem(k);
  } catch {
    /* ignore */
  }
}

export interface DialogDraftOptions<T> {
  key: string;
  open: boolean;
  value: T;
  setValue: (v: T) => void;
  enabled?: boolean;
}

/**
 * Keeps a form dialog's unsaved state in localStorage: restored when the
 * dialog opens, saved on change (debounced) and when it closes, removed by
 * clear() (call after a successful save) or discard().
 */
export function useDialogDraft<T>({ key, open, value, setValue, enabled = true }: DialogDraftOptions<T>) {
  const [restored, setRestored] = useState(false);
  const storageKey = draftStorageKey(key);
  const latest = useRef(value);
  latest.current = value;
  const cleared = useRef(false);
  const clearedValue = useRef("");
  const live = useRef(false); // a restore pass has run for this open
  const setRef = useRef(setValue);
  setRef.current = setValue;
  const initial = useRef<string>("");

  // Restore one render after opening, so a dialog's own reset-on-open effect
  // has already run and the snapshot below is its blank form.
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    if (!enabled || !open) return;
    cleared.current = false;
    initial.current = "";
    setPhase((p) => p + 1);
    return () => {
      live.current = false;
      if (cleared.current || initial.current === "") return;
      const now = JSON.stringify(latest.current);
      if (now !== initial.current || read(storageKey) !== null) write(storageKey, latest.current);
    };
  }, [open, enabled, storageKey]);

  useEffect(() => {
    if (!enabled || !open || phase === 0 || live.current) return;
    initial.current = JSON.stringify(latest.current);
    const saved = read<T>(storageKey);
    if (saved !== null) {
      setRef.current(saved);
      setRestored(true);
    } else {
      setRestored(false);
    }
    live.current = true;
  }, [phase, open, enabled, storageKey]);

  // While open: debounced save on change.
  useEffect(() => {
    if (!enabled || !open || !live.current) return;
    // Editing again after a save (a dialog that stays open) starts a new draft.
    if (cleared.current && JSON.stringify(value) !== clearedValue.current) cleared.current = false;
    if (cleared.current) return;
    if (JSON.stringify(value) === initial.current && read(storageKey) === null) return;
    const t = setTimeout(() => {
      if (!cleared.current) write(storageKey, latest.current);
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [value, open, enabled, storageKey]);

  const clear = useCallback(() => {
    cleared.current = true;
    clearedValue.current = JSON.stringify(latest.current);
    remove(storageKey);
    setRestored(false);
  }, [storageKey]);

  const discard = useCallback(() => {
    remove(storageKey);
    setRestored(false);
    try {
      setRef.current(JSON.parse(initial.current) as T);
    } catch {
      /* ignore */
    }
  }, [storageKey]);

  return { restored, discard, clear };
}

type Field = readonly [unknown, (v: never) => void];

/**
 * Draft for a dialog whose state lives in several useState calls: list the
 * fields as { name: [value, setValue] }. Fields left out (Files, derived
 * state) are not kept. Restored values are applied through each setter.
 */
export function useDraftFields(opts: {
  key: string;
  open: boolean;
  fields: Record<string, Field>;
  enabled?: boolean;
}) {
  const value: Record<string, unknown> = {};
  for (const [k, f] of Object.entries(opts.fields)) value[k] = f[0];
  const fieldsRef = useRef(opts.fields);
  fieldsRef.current = opts.fields;
  const setValue = useCallback((v: Record<string, unknown>) => {
    for (const [k, f] of Object.entries(fieldsRef.current)) {
      if (k in v) (f[1] as (x: unknown) => void)(v[k]);
    }
  }, []);
  return useDialogDraft<Record<string, unknown>>({
    key: opts.key,
    open: opts.open,
    enabled: opts.enabled,
    value,
    setValue,
  });
}
