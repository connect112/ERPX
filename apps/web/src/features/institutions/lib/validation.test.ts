import { describe, expect, it } from "vitest";

import type { StudentCandidate } from "@/features/institutions/api/institutions-api";
import { addable, buildItems, sourceLine } from "@/features/institutions/lib/validation";

const person = (over: Partial<StudentCandidate>): StudentCandidate => ({
  email: "asha@example.com",
  name: "Asha Rao",
  phone: null,
  name_variants: [],
  sources: [{ kind: "exam", title: "Day 1 MCQ" }],
  entries: 1,
  status: "new",
  existing_name: null,
  issues: [],
  addable: true,
  ...over,
});

describe("addable", () => {
  it("lists only the people who can still be added", () => {
    expect(addable([person({}), person({ email: "b@example.com", addable: false })])).toEqual(["asha@example.com"]);
  });
});

describe("buildItems", () => {
  const list = [person({}), person({ email: "meera@example.com", name: "Meera Iyer", phone: "111" }), person({ email: "done@example.com", status: "registered", addable: false })];
  it("sends only verified, addable people", () => {
    const items = buildItems(list, new Set(["asha@example.com", "done@example.com"]), {});
    expect(items.map((i) => i.email)).toEqual(["asha@example.com"]);
  });
  it("sends a corrected name or phone and leaves untouched ones for the server to keep", () => {
    const items = buildItems(list, new Set(["asha@example.com", "meera@example.com"]), { "asha@example.com": { name: "  Asha R. Rao " }, "meera@example.com": { name: "Meera Iyer", phone: "111" } });
    expect(items).toEqual([
      { email: "asha@example.com", name: "Asha R. Rao", phone: null },
      { email: "meera@example.com", name: null, phone: null },
    ]);
  });
  it("can clear a phone number", () => {
    expect(buildItems(list, new Set(["meera@example.com"]), { "meera@example.com": { phone: "" } })[0].phone).toBeNull();
  });
});

describe("sourceLine", () => {
  it("names where someone was found", () => {
    expect(sourceLine([{ kind: "exam", title: "Day 1 MCQ" }, { kind: "hackathon", title: "DevSecStorm" }])).toBe("Exam: Day 1 MCQ · Hackathon: DevSecStorm");
  });
});
