import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PlanTask, ProgressLog } from "@/lib/api";

vi.mock("@/lib/api", () => ({ logTaskProgress: vi.fn(), listTaskProgress: vi.fn() }));
vi.mock("@/lib/frappe", async (orig) => ({ ...(await orig<typeof import("@/lib/frappe")>()), uploadFile: vi.fn() }));

import * as api from "@/lib/api";
import * as frappe from "@/lib/frappe";
import { LogProgressDialog } from "@/components/plan/LogProgressDialog";
import { ProgressTimeline } from "@/components/plan/ProgressTimeline";

const mocked = vi.mocked(api);
const upload = vi.mocked(frappe.uploadFile);
const task = { name: "T-1", operation_name: "Spraying", due_date: "2026-11-24", uom: "Ha", work: [] } as unknown as PlanTask;

const log = (over: Partial<ProgressLog>): ProgressLog => ({
  name: "TPL-1", plan: "P", task: "T-1", log_date: "2026-11-25", logged_at: "2026-11-25 08:00:00",
  logged_by: "a@x.com", logged_by_name: "Ann", qty: 0, uom: "Ha", notes: "", attachments: [], ...over,
});

beforeEach(() => vi.resetAllMocks());

describe("LogProgressDialog", () => {
  it("needs a note, a quantity or a file", () => {
    render(<LogProgressDialog plan="P" task={task} onClose={vi.fn()} onLogged={vi.fn()} />);
    const save = screen.getByRole("button", { name: "Log progress" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "Done the east side" } });
    expect(save).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "  " } });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Quantity (Ha)"), { target: { value: "2" } });
    expect(save).toBeEnabled();
  });

  it("uploads private files and sends their urls", async () => {
    upload.mockResolvedValue({ file_url: "/private/files/a.jpg" });
    mocked.logTaskProgress.mockResolvedValue(log({}));
    const onLogged = vi.fn();
    render(<LogProgressDialog plan="P" task={task} onClose={vi.fn()} onLogged={onLogged} />);
    const f = new File(["x"], "a.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText("Attach files"), { target: { files: [f] } });
    fireEvent.change(screen.getByLabelText("Quantity (Ha)"), { target: { value: "1.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Log progress" }));
    await waitFor(() => expect(mocked.logTaskProgress).toHaveBeenCalledWith("P", "T-1", "", 1.5, ["/private/files/a.jpg"]));
    expect(upload).toHaveBeenCalledWith(f, true);
    await waitFor(() => expect(onLogged).toHaveBeenCalled());
  });

  it("shows the server error and stays open", async () => {
    mocked.logTaskProgress.mockResolvedValue({ error: "Add a note, a quantity or a file to log progress." });
    const onLogged = vi.fn();
    render(<LogProgressDialog plan="P" task={task} onClose={vi.fn()} onLogged={onLogged} />);
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Log progress" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Add a note");
    expect(onLogged).not.toHaveBeenCalled();
  });
});

describe("ProgressTimeline", () => {
  it("renders newest first with attachments", async () => {
    mocked.listTaskProgress.mockResolvedValue([
      log({ name: "TPL-1", logged_at: "2026-11-24 08:00:00", notes: "older note" }),
      log({
        name: "TPL-2", logged_at: "2026-11-25 09:00:00", notes: "newer note", qty: 2,
        attachments: [
          { file_url: "/private/files/a.jpg", file_name: "a.jpg", is_image: 1 },
          { file_url: "/private/files/b.pdf", file_name: "b.pdf", is_image: 0 },
        ],
      }),
    ]);
    render(<ProgressTimeline plan="P" task="T-1" />);
    const items = await screen.findAllByRole("listitem");
    expect(items[0]).toHaveTextContent("newer note");
    expect(items[1]).toHaveTextContent("older note");
    expect(items[0]).toHaveTextContent("2 Ha");
    expect(items[0].querySelector("img")).toHaveAttribute("src", "/private/files/a.jpg");
    expect(screen.getByRole("link", { name: /b\.pdf/ })).toHaveAttribute("href", "/private/files/b.pdf");
  });

  it("says when nothing is logged", async () => {
    mocked.listTaskProgress.mockResolvedValue([]);
    render(<ProgressTimeline plan="P" task="T-1" />);
    expect(await screen.findByText("No progress logged yet.")).toBeInTheDocument();
  });
});
