import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/api", () => ({ listOperations: vi.fn(), saveOperation: vi.fn(), listProtocols: vi.fn() }));
vi.mock("@/lib/varieties-api", async (orig) => ({
  ...(await orig<typeof import("@/lib/varieties-api")>()),
  listVarieties: vi.fn(),
  listRules: vi.fn(),
}));
vi.mock("@/lib/protocols-api", () => ({ listProtocolFamilies: vi.fn() }));
vi.mock("@/lib/blockcost-api", () => ({ blockLinks: vi.fn() }));
import { listOperations, listProtocols } from "@/lib/api";
import { blockLinks } from "@/lib/blockcost-api";
import { listProtocolFamilies } from "@/lib/protocols-api";
import { listRules, listVarieties } from "@/lib/varieties-api";
import { Settings } from "@/pages/Settings";
import { fireEvent } from "@testing-library/react";

describe("Settings block links", () => {
  beforeEach(() => {
    vi.mocked(listOperations).mockResolvedValue({ rows: [] } as never);
    vi.mocked(listProtocols).mockResolvedValue({ rows: [] } as never);
    vi.mocked(listProtocolFamilies).mockResolvedValue({ families: [] } as never);
    vi.mocked(listVarieties).mockResolvedValue({ varieties: [] } as never);
    vi.mocked(listRules).mockResolvedValue({ rules: [] } as never);
    vi.mocked(blockLinks).mockReset().mockResolvedValue({
      rows: [
        { unit: "Block A", cost_center: "Block A - MUT", warehouse: "Block A", ok: true, problems: [] },
        { unit: "Block B", cost_center: "Block B - MUT", warehouse: "Blk B - MUT", ok: false, problems: ["Warehouse 'Blk B - MUT' and cost centre 'Block B - MUT' differ — chemicals issued to this block are charged elsewhere"] },
      ],
    } as never);
  });

  it("block links shows mismatch", async () => {
    renderPage(<Settings />);
    fireEvent.mouseDown(await screen.findByRole("tab", { name: "Block links" }), { button: 0 });
    fireEvent.click(screen.getByRole("tab", { name: "Block links" }));
    expect(await screen.findByTestId("link-Block B")).toHaveTextContent(/differ/);
    expect(screen.getByTestId("link-Block B")).toHaveAttribute("data-ok", "false");
    expect(screen.getByTestId("link-Block A")).toHaveAttribute("data-ok", "true");
    expect(screen.getByTestId("links-summary")).toHaveTextContent("1 of 2 blocks need attention");
  });
});
