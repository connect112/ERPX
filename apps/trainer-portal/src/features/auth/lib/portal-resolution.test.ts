/**
 * Unit tests for resolveHomePortal() (portal-resolution.ts) — this file is
 * byte-identical to apps/trainer-portal's and apps/web's own copies, same
 * "duplicated but independently tested" precedent as src/api/client.test.ts.
 *
 * Regression coverage for a real bug found while live-testing the new
 * student-trainer messaging feature: a student provisioned the normal way
 * (modules/provisioning or modules/students::create_login_account) gets
 * the plain "student" system role assigned alongside their Student
 * record. Before the fix, ANY assigned role -- including "student" --
 * made this resolve to "admin", redirecting a real student to
 * erp.pentrix.in instead of their own portal.
 */

import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { apiClient } from "@/api/client";
import { resolveHomePortal } from "./portal-resolution";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
});

afterEach(() => {
  mock.restore();
});

describe("resolveHomePortal", () => {
  it("resolves a plain student (only the 'student' system role) as 'student', not 'admin'", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [{ slug: "student" }] });
    mock.onGet("/trainers/me").reply(404);
    mock.onGet("/employees/me").reply(404);
    mock.onGet("/students/me").reply(200, {});

    await expect(resolveHomePortal()).resolves.toBe("student");
  });

  it("still resolves as 'admin' for a genuinely administrative role", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [{ slug: "administrator" }] });

    await expect(resolveHomePortal()).resolves.toBe("admin");
  });

  it("resolves as 'admin' when the account holds an administrative role alongside the student role", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [{ slug: "student" }, { slug: "staff" }] });

    await expect(resolveHomePortal()).resolves.toBe("admin");
  });

  it("falls through to 'trainer' when there are no roles at all", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [] });
    mock.onGet("/trainers/me").reply(200, {});

    await expect(resolveHomePortal()).resolves.toBe("trainer");
  });

  it("falls through to 'employee' when there's no role and no Trainer record", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [] });
    mock.onGet("/trainers/me").reply(404);
    mock.onGet("/employees/me").reply(200, {});

    await expect(resolveHomePortal()).resolves.toBe("employee");
  });

  it("resolves to null when the account has no role and no linked record at all", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [] });
    mock.onGet("/trainers/me").reply(404);
    mock.onGet("/employees/me").reply(404);
    mock.onGet("/students/me").reply(404);

    await expect(resolveHomePortal()).resolves.toBeNull();
  });

  it("falls through past a failed /authorization/me call (e.g. a 401) to the ownership checks", async () => {
    mock.onGet("/authorization/me").reply(401);
    mock.onGet("/trainers/me").reply(404);
    mock.onGet("/employees/me").reply(404);
    mock.onGet("/students/me").reply(200, {});

    await expect(resolveHomePortal()).resolves.toBe("student");
  });
});
