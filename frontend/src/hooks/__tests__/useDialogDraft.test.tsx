import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { draftStorageKey, useDialogDraft } from "@/hooks/useDialogDraft";

function useForm(key: string, open: boolean, enabled = true) {
  const [v, setV] = useState({ a: "" });
  const d = useDialogDraft({ key, open, value: v, setValue: setV, enabled });
  return { v, setV, ...d };
}

beforeEach(() => {
  localStorage.clear();
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

describe("useDialogDraft", () => {
  it("saves on close and restores on reopen", () => {
    const { result, rerender } = renderHook(({ open }) => useForm("k1", open), { initialProps: { open: true } });
    act(() => result.current.setV({ a: "hello" }));
    rerender({ open: false });
    expect(localStorage.getItem(draftStorageKey("k1"))).toContain("hello");
    rerender({ open: true });
    expect(result.current.v.a).toBe("hello");
    expect(result.current.restored).toBe(true);
  });

  it("saves while open after the debounce", () => {
    const { result } = renderHook(() => useForm("k2", true));
    act(() => result.current.setV({ a: "x" }));
    expect(localStorage.getItem(draftStorageKey("k2"))).toBeNull();
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    expect(localStorage.getItem(draftStorageKey("k2"))).toContain("x");
  });

  it("clear() removes the draft and stops the close save", () => {
    const { result, rerender } = renderHook(({ open }) => useForm("k3", open), { initialProps: { open: true } });
    act(() => result.current.setV({ a: "y" }));
    act(() => result.current.clear());
    rerender({ open: false });
    expect(localStorage.getItem(draftStorageKey("k3"))).toBeNull();
  });

  it("discard() drops the draft and resets the value", () => {
    localStorage.setItem(draftStorageKey("k4"), JSON.stringify({ at: Date.now(), value: { a: "old" } }));
    const { result } = renderHook(() => useForm("k4", true));
    expect(result.current.v.a).toBe("old");
    act(() => result.current.discard());
    expect(result.current.v.a).toBe("");
    expect(result.current.restored).toBe(false);
    expect(localStorage.getItem(draftStorageKey("k4"))).toBeNull();
  });

  it("drops drafts older than 7 days", () => {
    localStorage.setItem(
      draftStorageKey("k5"),
      JSON.stringify({ at: Date.now() - 8 * 24 * 3600 * 1000, value: { a: "stale" } }),
    );
    const { result } = renderHook(() => useForm("k5", true));
    expect(result.current.v.a).toBe("");
    expect(result.current.restored).toBe(false);
  });

  it("does nothing when disabled and survives broken storage", () => {
    const { result } = renderHook(() => useForm("k6", true, false));
    act(() => result.current.setV({ a: "z" }));
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(localStorage.getItem(draftStorageKey("k6"))).toBeNull();
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("full");
    });
    const r2 = renderHook(() => useForm("k7", true));
    act(() => r2.result.current.setV({ a: "q" }));
    expect(() => act(() => void vi.advanceTimersByTime(2000))).not.toThrow();
    spy.mockRestore();
  });
});
