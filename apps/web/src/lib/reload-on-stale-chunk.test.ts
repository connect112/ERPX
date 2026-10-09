import { describe, expect, it } from "vitest";

import { shouldReload } from "@/lib/reload-on-stale-chunk";

describe("shouldReload", () => {
  const at = (value: string | null) => ({ getItem: () => value });
  it("reloads the first time and not again within 30 seconds", () => {
    expect(shouldReload(at(null), 100_000)).toBe(true);
    expect(shouldReload(at("90000"), 100_000)).toBe(false);
    expect(shouldReload(at("50000"), 100_000)).toBe(true);
  });
  it("still reloads when storage is blocked", () => {
    expect(shouldReload({ getItem: () => { throw new Error("blocked"); } }, 1)).toBe(true);
  });
});
