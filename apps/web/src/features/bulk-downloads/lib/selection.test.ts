import { describe, expect, it } from "vitest";

import {
  count,
  emptySelection,
  isSelected,
  pageState,
  selectAllMatching,
  setPage,
  toPayload,
  toggle,
} from "@/features/bulk-downloads/lib/selection";

describe("bulk download selection", () => {
  it("keeps ticks made on different pages", () => {
    let s = emptySelection();
    s = setPage(s, ["a", "b"], true); // page 1
    s = toggle(s, "z"); // page 3
    expect(count(s, 100)).toBe(3);
    expect(toPayload(s, {})).toEqual({ mode: "selected", ids: ["a", "b", "z"] });
  });

  it("unticking a page only removes that page", () => {
    let s = setPage(emptySelection(), ["a", "b", "c"], true);
    s = setPage(s, ["b", "c"], false);
    expect(isSelected(s, "a")).toBe(true);
    expect(isSelected(s, "b")).toBe(false);
  });

  it("all matching sends the filters and the exceptions, not every id", () => {
    let s = selectAllMatching();
    s = toggle(s, "x");
    expect(isSelected(s, "anything")).toBe(true);
    expect(isSelected(s, "x")).toBe(false);
    expect(count(s, 2000)).toBe(1999);
    expect(toPayload(s, { search: "asha", status: "" })).toEqual({
      mode: "filtered",
      search: "asha",
      status: undefined,
      exclude_ids: ["x"],
    });
  });

  it("reports whether a page is fully, partly or not chosen", () => {
    const s = setPage(emptySelection(), ["a"], true);
    expect(pageState(s, ["a"])).toBe("all");
    expect(pageState(s, ["a", "b"])).toBe("some");
    expect(pageState(s, ["c"])).toBe("none");
  });

  it("never counts below zero", () => {
    const s = setPage(selectAllMatching(), ["a", "b", "c"], false);
    expect(count(s, 2)).toBe(0);
  });
});
