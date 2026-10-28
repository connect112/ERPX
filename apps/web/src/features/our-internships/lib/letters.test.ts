import { describe, expect, it } from "vitest";

import { moveBy, removeAt, replaceAt, safeFileName, setPath } from "@/features/our-internships/lib/letters";

describe("list helpers", () => {
  it("replaces, removes and moves entries without changing the original", () => {
    const list = ["a", "b", "c"];
    expect(replaceAt(list, 1, "x")).toEqual(["a", "x", "c"]);
    expect(removeAt(list, 0)).toEqual(["b", "c"]);
    expect(moveBy(list, 2, -1)).toEqual(["a", "c", "b"]);
    expect(moveBy(list, 0, 1)).toEqual(["b", "a", "c"]);
    expect(list).toEqual(["a", "b", "c"]);
  });
  it("leaves the list alone when a move would fall off either end", () => {
    const list = [1, 2];
    expect(moveBy(list, 0, -1)).toBe(list);
    expect(moveBy(list, 1, 1)).toBe(list);
    expect(moveBy(list, 5, -1)).toBe(list);
  });
});

describe("setPath", () => {
  it("replaces a nested value and keeps everything else", () => {
    const config = { a: { b: { c: 1, d: 2 }, e: 3 }, list: [{ x: 1 }, { x: 2 }] };
    const next = setPath(config, ["a", "b", "c"], 9);
    expect(next).toEqual({ a: { b: { c: 9, d: 2 }, e: 3 }, list: [{ x: 1 }, { x: 2 }] });
    expect(config.a.b.c).toBe(1);
    expect(setPath(config, ["list", 1, "x"], 7).list).toEqual([{ x: 1 }, { x: 7 }]);
  });
});

describe("safeFileName", () => {
  it("keeps letters and digits and turns anything else into an underscore", () => {
    expect(safeFileName("Asha Rao / B.Tech")).toBe("Asha_Rao_B.Tech");
    expect(safeFileName("///")).toBe("file");
  });
});
