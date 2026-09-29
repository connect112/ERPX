/**
 * Unit tests for resolveHomePortal() (portal-resolution.ts) — this file is
 * byte-identical to apps/student-portal's and apps/web's own copies, same
 * "duplicated but independently tested" precedent as src/api/client.test.ts.
 *
 * Regression coverage for two real bugs found live:
 * 1. A student provisioned the normal way (modules/provisioning or
 *    modules/students::create_login_account) gets the plain "student"
 *    system role assigned alongside their Student record. Before that
 *    fix, ANY assigned role -- including "student" -- made this resolve
 *    to "admin", redirecting a real student to erp.pentrix.in instead
 *    of their own portal.
 * 2. An ISE-designated trainer holding a real, narrow org-custom role
 *    (15 permissions, nowhere near administrative) was *still*
 *    resolving as "admin" here -- "any role except student" was still
 *    too broad. Only "administrator"/"super_admin" now count. This one
 *    additionally caused an infinite redirect loop once apps/web's own
 *    copy was fixed first and this one wasn't: apps/web correctly
 *    resolved the account as "trainer" and bounced it here, and this
 *    portal's still-unfixed check then treated the same ISE role as
 *    "admin" and bounced it straight back.
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
