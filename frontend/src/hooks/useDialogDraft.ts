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
  const live = useRef(false); // a restore pass has run for this open
  const setRef = useRef(setValue);
  setRef.current = setValue;
  const initial = useRef<string>("");

  // Open: restore. Close: persist unless cleared.
  useEffect(() => {
    if (!enabled || !open) return;
    cleared.current = false;
    const saved = read<T>(storageKey);
    initial.current = JSON.stringify(latest.current);
    if (saved !== null) {
      setRef.current(saved);
      setRestored(true);
    } else {
      setRestored(false);
    }
    live.current = true;
    return () => {
      live.current = false;
      if (cleared.current) return;
      const now = JSON.stringify(latest.current);
      if (now !== initial.current || read(storageKey) !== null) write(storageKey, latest.current);
    };
  }, [open, enabled, storageKey]);

  // While open: debounced save on change.
  useEffect(() => {
    if (!enabled || !open || !live.current || cleared.current) return;
    if (JSON.stringify(value) === initial.current && read(storageKey) === null) return;
    const t = setTimeout(() => {
      if (!cleared.current) write(storageKey, latest.current);
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [value, open, enabled, storageKey]);

  const clear = useCallback(() => {
    cleared.current = true;
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
