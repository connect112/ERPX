import { describe, expect, it } from "vitest";

import {
  cssFont,
  defaultField,
  fractionFromClick,
  layoutProblem,
  nudgeField,
  placeField,
  removeField,
  sameLayout,
  updateField,
  withinPages,
} from "./offer-layout";

const rect = { left: 100, top: 50, width: 400, height: 600 };

describe("fractionFromClick", () => {
  it("turns a click into fractions of the page", () => {
    expect(fractionFromClick(rect, 300, 350)).toEqual({ x: 0.5, y: 0.5 });
    expect(fractionFromClick(rect, 100, 50)).toEqual({ x: 0, y: 0 });
  });

  it("keeps a click that lands just outside the page on the page, and survives a page with no size yet", () => {
    expect(fractionFromClick(rect, 90, 700)).toEqual({ x: 0, y: 1 });
    expect(fractionFromClick({ left: 0, top: 0, width: 0, height: 0 }, 10, 10)).toEqual({ x: 0, y: 0 });
  });
});

describe("placing details", () => {
  it("places a new detail with a sensible starting look: the name big and centred, the rest small", () => {
    const fields = placeField([], "name", 1, 0.5, 0.4);
    expect(fields).toEqual([defaultField("name", 1, 0.5, 0.4)]);
    expect(fields[0].align).toBe("center");
    expect(defaultField("reference", 1, 0, 0).align).toBe("left");
    expect(defaultField("name", 1, 0, 0).font_size).toBeGreaterThan(defaultField("date", 1, 0, 0).font_size);
  });

  it("moves a detail that is already placed, keeping the look the admin gave it", () => {
    const styled = updateField(placeField([], "name", 1, 0.5, 0.4), "name", { color: "#ff0000", font_size: 0.05 });
    const moved = placeField(styled, "name", 2, 0.25, 0.75);
    expect(moved).toHaveLength(1);
    expect(moved[0]).toMatchObject({ page: 2, x: 0.25, y: 0.75, color: "#ff0000", font_size: 0.05 });
  });

  it("keeps the details in a fixed order however they were placed", () => {
    let fields = placeField([], "reference", 1, 0.1, 0.9);
    fields = placeField(fields, "name", 1, 0.5, 0.4);
    fields = placeField(fields, "date", 1, 0.8, 0.1);
    expect(fields.map((f) => f.key)).toEqual(["name", "date", "reference"]);
  });

  it("rounds positions so a saved layout does not carry 15-digit fractions", () => {
    expect(placeField([], "name", 1, 0.123456789, 0.987654321)[0]).toMatchObject({ x: 0.1235, y: 0.9877 });
  });

  it("nudges a placed detail with the arrow keys, stays on the page and ignores one that is not placed", () => {
    const fields = placeField([], "name", 1, 0.5, 0.4);
    expect(nudgeField(fields, "name", 0.004, -0.004)[0]).toMatchObject({ x: 0.504, y: 0.396 });
    expect(nudgeField(placeField([], "name", 1, 0.001, 0.999), "name", -0.02, 0.02)[0]).toMatchObject({ x: 0, y: 1 });
    expect(nudgeField(fields, "date", 0.1, 0.1)).toEqual(fields);
  });

  it("removes a detail and leaves the others", () => {
    const fields = placeField(placeField([], "name", 1, 0.5, 0.4), "date", 1, 0.8, 0.1);
    expect(removeField(fields, "date").map((f) => f.key)).toEqual(["name"]);
  });
});

describe("layout checks", () => {
  it("needs the name once anything is placed, but an empty layout is just 'not started'", () => {
    expect(layoutProblem([])).toBeNull();
    expect(layoutProblem(placeField([], "date", 1, 0.1, 0.1))).toMatch(/name/);
    expect(layoutProblem(placeField([], "name", 1, 0.5, 0.5))).toBeNull();
  });

  it("knows when the unsaved layout differs from the saved one, whatever order they are held in", () => {
    const a = placeField(placeField([], "name", 1, 0.5, 0.4), "date", 1, 0.8, 0.1);
    expect(sameLayout(a, [...a].reverse())).toBe(true);
    expect(sameLayout(a, updateField(a, "date", { x: 0.9 }))).toBe(false);
  });

  it("drops fields on pages a replacement letter no longer has", () => {
    const fields = placeField(placeField([], "name", 1, 0.5, 0.4), "date", 3, 0.1, 0.1);
    expect(withinPages(fields, 2).map((f) => f.key)).toEqual(["name"]);
  });
});

describe("cssFont", () => {
  it("approximates each PDF font for the on-screen sample", () => {
    expect(cssFont("sans_bold")).toMatchObject({ fontWeight: 700 });
    expect(cssFont("serif").fontFamily).toMatch(/Times/);
    expect(cssFont("serif").fontWeight).toBe(400);
  });
});
