import { describe, expect, it } from "vitest";

import { validStudent } from "@/features/our-internships/lib/students";

const ok = { name: "Asha Rao", email: "asha@example.com", score: "", event: "e1" };

describe("validStudent", () => {
  it("accepts a name, an email and an event, with no score", () => {
    expect(validStudent(ok)).toBe(true);
  });
  it("needs each of name, a real-looking email and an event", () => {
    expect(validStudent({ ...ok, name: "  " })).toBe(false);
    expect(validStudent({ ...ok, email: "asha" })).toBe(false);
    expect(validStudent({ ...ok, email: "a b@example.com" })).toBe(false);
    expect(validStudent({ ...ok, event: "" })).toBe(false);
  });
  it("accepts a score from 0 to 9999 and refuses anything else", () => {
    expect(validStudent({ ...ok, score: "7.5" })).toBe(true);
    expect(validStudent({ ...ok, score: "0" })).toBe(true);
    expect(validStudent({ ...ok, score: "-1" })).toBe(false);
    expect(validStudent({ ...ok, score: "10000" })).toBe(false);
    expect(validStudent({ ...ok, score: "abc" })).toBe(false);
  });
});
