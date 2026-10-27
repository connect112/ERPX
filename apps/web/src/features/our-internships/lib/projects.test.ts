import { describe, expect, it } from "vitest";

import { allowedMethods, submissionProblem } from "@/features/our-internships/lib/projects";

const ok = { allowFile: true, allowEmail: false, allowRepo: false, email: "", startsAt: "", deadlineAt: "" };

describe("submissionProblem", () => {
  it("accepts a project that takes files", () => {
    expect(submissionProblem(ok)).toBeNull();
  });
  it("needs at least one way of handing in", () => {
    expect(submissionProblem({ ...ok, allowFile: false })).toContain("at least one way");
  });
  it("needs a valid address when email is allowed", () => {
    expect(submissionProblem({ ...ok, allowEmail: true })).toContain("email address");
    expect(submissionProblem({ ...ok, allowEmail: true, email: "nope" })).toContain("email address");
    expect(submissionProblem({ ...ok, allowEmail: true, email: "projects@pentrix.in" })).toBeNull();
  });
  it("needs the deadline after the opening time", () => {
    expect(submissionProblem({ ...ok, startsAt: "2026-12-02T10:00", deadlineAt: "2026-12-01T10:00" })).toContain("after the opening");
    expect(submissionProblem({ ...ok, startsAt: "2026-12-01T10:00", deadlineAt: "2026-12-02T10:00" })).toBeNull();
  });
});

describe("allowedMethods", () => {
  it("lists only what is allowed", () => {
    expect(allowedMethods({ allow_file: true, allow_email: false, allow_repository: true })).toBe("Files, Repository");
    expect(allowedMethods({ allow_file: false, allow_email: true, allow_repository: false })).toBe("Email");
  });
});
