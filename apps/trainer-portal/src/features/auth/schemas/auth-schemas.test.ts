/**
 * Characterization tests for the auth form schemas (src/features/auth/schemas/auth-schemas.ts).
 *
 * They pin what the user sees today: which inputs are accepted, which are rejected, the exact (custom) error
 * messages, the ORDER of the messages for one field (react-hook-form shows the first), and what the real
 * `zodResolver` hands to react-hook-form. They were written against Zod 3 + @hookform/resolvers 3 and must keep
 * passing unchanged across the Zod 4 / resolvers 5 upgrade — a failure here means a user-visible form regression.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { describe, expect, it } from "vitest";

import { type LoginFormValues, loginSchema } from "./auth-schemas";

/** "path: message" for every issue, in the order Zod reports them. */
function issuesOf(schema: { safeParse: (v: unknown) => { success: boolean; error?: { issues: { path: PropertyKey[]; message: string }[] } } }, input: unknown) {
  const result = schema.safeParse(input);
  if (result.success) return [];
  return (result.error?.issues ?? []).map((issue) => `${issue.path.join(".")}: ${issue.message}`);
}

const options = { fields: {}, shouldUseNativeValidation: false } as const;

describe("loginSchema", () => {
  const ok = { email: "trainer@example.com", password: "whatever" };

  it("accepts a normal login, with and without a one-time code", () => {
    expect(issuesOf(loginSchema, ok)).toEqual([]);
    expect(issuesOf(loginSchema, { ...ok, otpCode: "123456" })).toEqual([]);
    expect(issuesOf(loginSchema, { ...ok, otpCode: "" })).toEqual([]);
  });

  it.each(["a@b.co", "john+tag@example.com", "first.last@sub.example.org", "A@B.COM", "x@y.museum"])("accepts the email %s", (email) => {
    expect(issuesOf(loginSchema, { ...ok, email })).toEqual([]);
  });

  it.each(["", "not-an-email", "a@b", "user@localhost", "a b@c.com", "a@b..com", ".a@b.com", "a.@b.com", "a@-b.com", "x@192.168.0.1"])(
    "rejects the email %j with the custom message",
    (email) => {
      expect(issuesOf(loginSchema, { ...ok, email })).toEqual(["email: Enter a valid email address."]);
    },
  );

  it("requires a password with the custom message", () => {
    expect(issuesOf(loginSchema, { ...ok, password: "" })).toEqual(["password: Password is required."]);
  });

  it("reports both fields when both are bad, email first", () => {
    expect(issuesOf(loginSchema, { email: "nope", password: "" })).toEqual(["email: Enter a valid email address.", "password: Password is required."]);
  });

  it("passes the parsed values through unchanged", () => {
    expect(loginSchema.parse({ ...ok, otpCode: "9" })).toEqual({ ...ok, otpCode: "9" });
  });

  it("works through the real zodResolver the way the login page uses it", async () => {
    const good = await zodResolver(loginSchema)(ok as LoginFormValues, undefined, options);
    expect(good.errors).toEqual({});
    expect(good.values).toEqual(ok);

    const bad = await zodResolver(loginSchema)({ email: "nope", password: "" } as LoginFormValues, undefined, options);
    expect(bad.values).toEqual({});
    expect(Object.keys(bad.errors ?? {}).sort()).toEqual(["email", "password"]);
    expect(bad.errors?.email?.message).toBe("Enter a valid email address.");
    expect(bad.errors?.password?.message).toBe("Password is required.");
  });
});
