import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FilterSelect } from "@/components/FilterSelect";

describe("FilterSelect", () => {
  it("lists grouped options under their group heading", async () => {
    render(
      <FilterSelect
        label="Crop"
        value=""
        onChange={() => {}}
        allLabel="All crops"
        options={[
          { value: "Cabbage", label: "Cabbage", group: "Vegetable Crops" },
          { value: "Rose", label: "Rose", group: "Floriculture" },
        ]}
      />,
    );
    fireEvent.click(screen.getByRole("combobox", { name: "Crop" }));
    expect(await screen.findByText("Vegetable Crops")).toBeTruthy();
    expect(screen.getByText("Floriculture")).toBeTruthy();
    expect(screen.getByRole("option", { name: "Rose" })).toBeTruthy();
  });
});
