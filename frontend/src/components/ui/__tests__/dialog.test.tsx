import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

function Harness() {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogTitle>Hello</DialogTitle>
        body
      </DialogContent>
    </Dialog>
  );
}

describe("DialogContent", () => {
  it("stays open on outside pointer-down and Escape", () => {
    render(<Harness />);
    const overlay = document.querySelector("[data-state=open].fixed.inset-0") as HTMLElement;
    fireEvent.pointerDown(overlay);
    fireEvent.click(overlay);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeTruthy();
  });

  it("closes with the close button", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
