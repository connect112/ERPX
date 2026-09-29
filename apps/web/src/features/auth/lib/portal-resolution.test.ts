/**
 * Unit tests for resolveHomePortal() (portal-resolution.ts). This file
 * used to be byte-identical to apps/student-portal's and
 * apps/trainer-portal's own copies (same "duplicated but independently
 * tested" precedent as src/api/client.test.ts) -- as of this change,
 * apps/web's copy is narrower than the other two on purpose (see the
 * function's own docstring), so this test file has diverged from theirs
 * too.
 *
 * Regression coverage for two real bugs found live:
 * 1. (PR #51) A student provisioned the normal way gets the plain
 *    "student" system role assigned alongside their Student record.
 *    Before that fix, ANY assigned role -- including "student" -- made
 *    this resolve to "admin", redirecting a real student to
 *    erp.pentrix.in instead of their own portal.
 * 2. (this change) An ISE-designated employee holding a real, narrow
 *    org-custom role (15 permissions, nowhere near administrative) was
 *    *still* resolving as "admin" here -- "any role except student"
 *    was still too broad. Only "administrator"/"super_admin" now count.
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

  it("resolves as 'admin' for the 'administrator' role", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [{ slug: "administrator" }] });

    await expect(resolveHomePortal()).resolves.toBe("admin");
  });

  it("resolves as 'admin' for the 'super_admin' role", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [{ slug: "super_admin" }] });

    await expect(resolveHomePortal()).resolves.toBe("admin");
  });

  it("does NOT resolve as 'admin' for a narrow org-custom role (e.g. 'ise'), falling through to ownership checks instead", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [{ slug: "ise" }] });
    mock.onGet("/trainers/me").reply(200, {});

    await expect(resolveHomePortal()).resolves.toBe("trainer");
  });

  it("does NOT resolve as 'admin' for the 'staff' role by itself", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [{ slug: "staff" }] });
    mock.onGet("/trainers/me").reply(404);
    mock.onGet("/employees/me").reply(200, {});

    await expect(resolveHomePortal()).resolves.toBe("employee");
  });

  it("resolves as 'admin' when the account holds 'administrator' alongside a narrower role", async () => {
    mock.onGet("/authorization/me").reply(200, { roles: [{ slug: "ise" }, { slug: "administrator" }] });

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
