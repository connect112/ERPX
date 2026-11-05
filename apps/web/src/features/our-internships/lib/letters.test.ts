import { describe, expect, it } from "vitest";

import { asksAboutLinks, moveBy, releaseBlockedBy, releaseOptions, removeAt, replaceAt, safeFileName, setPath } from "@/features/our-internships/lib/letters";

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

describe("the release options for the email", () => {
  const withLink = { uses_link: true, link_available: true, problem: null };
  const keep = { linkPolicy: "keep_existing", useLegacy: false } as const;
  const replace = { linkPolicy: "replace", useLegacy: false } as const;

  it("keeps students' existing links unless the administrator asked for new ones", () => {
    expect(releaseOptions(withLink, keep)).toEqual({ link_policy: "keep_existing", fallback: "none" });
    expect(releaseOptions(withLink, replace)).toEqual({ link_policy: "replace", fallback: "none" });
  });

  it("never asks for new links when the email has no link or onboarding is manual", () => {
    expect(releaseOptions({ uses_link: false, link_available: true, problem: null }, replace).link_policy).toBe("keep_existing");
    expect(releaseOptions({ uses_link: true, link_available: false, problem: null }, replace).link_policy).toBe("keep_existing");
    expect(releaseOptions(undefined, replace).link_policy).toBe("keep_existing");
    expect(asksAboutLinks({ uses_link: true, link_available: false, problem: null })).toBe(false);
  });

  it("asks for the legacy email only when the template is unusable and it was chosen", () => {
    const broken = { uses_link: false, link_available: true, problem: "The template was deleted" };
    expect(releaseOptions(broken, { linkPolicy: "keep_existing", useLegacy: true }).fallback).toBe("legacy_letter_settings");
    expect(releaseOptions(broken, keep).fallback).toBe("none");
    expect(releaseOptions(withLink, { linkPolicy: "keep_existing", useLegacy: true }).fallback).toBe("none");
  });

  it("blocks a release with an unusable template until the legacy email is chosen", () => {
    const broken = { uses_link: false, link_available: true, problem: "The template was deleted" };
    expect(releaseBlockedBy(broken, keep)).toContain("The template was deleted");
    expect(releaseBlockedBy(broken, { linkPolicy: "keep_existing", useLegacy: true })).toBeNull();
    expect(releaseBlockedBy(withLink, keep)).toBeNull();
    expect(releaseBlockedBy(undefined, keep)).toBeNull();
  });
});
