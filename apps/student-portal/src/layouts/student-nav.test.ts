import { beforeEach, describe, expect, it, vi } from "vitest";

import { GROUPS_KEY, activeGroupId, readOpenGroups, saveOpenGroups, studentGroups, visibleStudentNav } from "@/layouts/student-nav";

const ALL = ["pentrix.labs.view", "pentrix.leaderboard.view", "pentrix.achievements.view"];
const labels = (v: ReturnType<typeof visibleStudentNav>) => Object.fromEntries(v.groups.map((g) => [g.title, g.items.map((i) => i.label)]));

describe("student navigation", () => {
  it("is Learning, Cyber Range, Updates, with Dashboard first and Placements after the groups", () => {
    const v = visibleStudentNav({ permissions: ALL, participantOnly: false, hasInternship: true });
    expect(v.top.map((i) => i.label)).toEqual(["Dashboard"]);
    expect(labels(v)).toEqual({
      Learning: ["My Courses", "My Internships", "My Schedule", "Bookmarks", "Transcript"],
      "Cyber Range": ["Cyber Range", "Leaderboard", "Achievements"],
      Updates: ["Announcements", "Messages"],
    });
    expect(v.bottom.map((i) => i.label)).toEqual(["Placements"]);
  });

  it("keeps every page the old flat menu had", () => {
    const v = visibleStudentNav({ permissions: ALL, participantOnly: false, hasInternship: true });
    const paths = [...v.top, ...v.groups.flatMap((g) => g.items), ...v.bottom].map((i) => i.to).sort();
    expect(paths).toEqual(["/", "/achievements", "/announcements", "/bookmarks", "/courses", "/cyber-range", "/leaderboard", "/messages", "/my-internship", "/placements", "/schedule", "/transcript"].sort());
  });

  it("hides the internship link until the student has an internship, and the Pentrix pages without their permissions", () => {
    const v = visibleStudentNav({ permissions: [], participantOnly: false, hasInternship: false });
    expect(labels(v)).toEqual({ Learning: ["My Courses", "My Schedule", "Bookmarks", "Transcript"], Updates: ["Announcements", "Messages"] }); // Cyber Range group has nothing left, so it is gone
    const some = visibleStudentNav({ permissions: ["pentrix.leaderboard.view"], participantOnly: false, hasInternship: false });
    expect(labels(some)["Cyber Range"]).toEqual(["Leaderboard"]);
  });

  it("gives a hackathon participant the hackathon links and nothing else", () => {
    const v = visibleStudentNav({ permissions: ALL, participantOnly: true, hasInternship: true });
    expect(v.top.map((i) => i.to)).toEqual(["/hackathons", "/hackathon-leaderboard", "/hackathon-achievements"]);
    expect(v.groups).toEqual([]);
    expect(v.bottom).toEqual([]);
  });

  it("finds the group of the current page, detail pages included", () => {
    expect(activeGroupId("/courses/abc")).toBe("learning");
    expect(activeGroupId("/my-internship/xyz")).toBe("learning");
    expect(activeGroupId("/leaderboard")).toBe("cyber-range");
    expect(activeGroupId("/messages")).toBe("updates");
    expect(activeGroupId("/")).toBeUndefined();
    expect(activeGroupId("/placements")).toBeUndefined();
    expect(activeGroupId("/courses-extra")).toBeUndefined(); // a path that only starts with the same letters is not that page
  });

  it("has no page listed twice", () => {
    const all = studentGroups.flatMap((g) => g.items.map((i) => i.to));
    expect(new Set(all).size).toBe(all.length);
  });
});

describe("remembered groups", () => {
  // this package's tests run without a DOM, so give them a small in-memory store
  beforeEach(() => {
    const data = new Map<string, string>();
    vi.stubGlobal("localStorage", { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v), clear: () => data.clear() });
  });
  it("round-trips, and survives garbage", () => {
    expect(readOpenGroups()).toEqual([]);
    saveOpenGroups(["learning", "updates"]);
    expect(readOpenGroups()).toEqual(["learning", "updates"]);
    localStorage.setItem(GROUPS_KEY, "{not json");
    expect(readOpenGroups()).toEqual([]);
    localStorage.setItem(GROUPS_KEY, JSON.stringify([1, "x", null]));
    expect(readOpenGroups()).toEqual(["x"]);
  });
});

describe("a blocked store", () => {
  it("is not an error, the choice is just not remembered", () => {
    vi.stubGlobal("localStorage", { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } });
    expect(readOpenGroups()).toEqual([]);
    expect(() => saveOpenGroups(["learning"])).not.toThrow();
  });
});
