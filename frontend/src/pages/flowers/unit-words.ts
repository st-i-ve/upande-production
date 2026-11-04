/** What a crop's units are called: Margin Par's summer flowers are planted per block, roses per greenhouse. */
export function unitWord(mode?: "block" | "greenhouse") {
  return mode === "block"
    ? { singular: "Block", plural: "Blocks", doctype: "Block" }
    : { singular: "Greenhouse", plural: "Greenhouses", doctype: "Greenhouse" };
}
