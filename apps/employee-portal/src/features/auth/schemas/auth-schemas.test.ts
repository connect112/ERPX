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

import {
  type CompleteRegistrationFormValues,
  completeRegistrationSchema,
  genderValues,
  type LoginFormValues,
  loginSchema,
  type ResetPasswordFormValues,
  resetPasswordSchema,
} from "./auth-schemas";

/** "path: message" for every issue, in the order Zod reports them. */
function issuesOf(schema: { safeParse: (v: unknown) => { success: boolean; error?: { issues: { path: PropertyKey[]; message: string }[] } } }, input: unknown) {
  const result = schema.safeParse(input);
  if (result.success) return [];
  return (result.error?.issues ?? []).map((issue) => `${issue.path.join(".")}: ${issue.message}`);
}

const options = { fields: {}, shouldUseNativeValidation: false } as const;

describe("loginSchema", () => {
  const ok = { email: "employee@example.com", password: "whatever" };

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

describe("resetPasswordSchema", () => {
  const strong = "Abcdef1!";
  const WEAK = {
    length: "newPassword: Password must be at least 8 characters long.",
    upper: "newPassword: Password must contain at least one uppercase letter.",
    lower: "newPassword: Password must contain at least one lowercase letter.",
    digit: "newPassword: Password must contain at least one digit.",
    special: "newPassword: Password must contain at least one special character.",
  };
  const MISMATCH = "confirmPassword: Passwords do not match.";
  const same = (password: string) => ({ newPassword: password, confirmPassword: password });

  it("accepts a strong password that is confirmed", () => {
    expect(issuesOf(resetPasswordSchema, same(strong))).toEqual([]);
    expect(issuesOf(resetPasswordSchema, same("Zz9#zzzzzzzzzzzzzzzz"))).toEqual([]);
  });

  it.each([
    ["no uppercase", "abcdef1!", [WEAK.upper]],
    ["no lowercase", "ABCDEF1!", [WEAK.lower]],
    ["no digit", "Abcdefg!", [WEAK.digit]],
    ["no special character", "Abcdefg1", [WEAK.special]],
    ["too short", "Ab1!", [WEAK.length]],
  ])("rejects a password with %s using exactly one message", (_label, password, expected) => {
    expect(issuesOf(resetPasswordSchema, same(password))).toEqual(expected);
  });

  it("lists every failed rule, in the order the rules are declared (the first one is what the form shows)", () => {
    expect(issuesOf(resetPasswordSchema, same("short"))).toEqual([WEAK.length, WEAK.upper, WEAK.digit, WEAK.special]);
    expect(issuesOf(resetPasswordSchema, same(""))).toEqual([WEAK.length, WEAK.upper, WEAK.lower, WEAK.digit, WEAK.special]);
  });

  it("flags a mismatched confirmation on the confirm field only", () => {
    expect(issuesOf(resetPasswordSchema, { newPassword: strong, confirmPassword: "Different1!" })).toEqual([MISMATCH]);
    expect(issuesOf(resetPasswordSchema, { newPassword: strong, confirmPassword: "" })).toEqual([MISMATCH]);
  });

  it("with a weak password AND a mismatch, reports the weak password first and still the mismatch", () => {
    expect(issuesOf(resetPasswordSchema, { newPassword: "short", confirmPassword: "other" })).toEqual([
      WEAK.length,
      WEAK.upper,
      WEAK.digit,
      WEAK.special,
      MISMATCH,
    ]);
  });

  it("works through the real zodResolver the way the reset page uses it", async () => {
    const good = await zodResolver(resetPasswordSchema)(same(strong) as ResetPasswordFormValues, undefined, options);
    expect(good.errors).toEqual({});

    const weak = await zodResolver(resetPasswordSchema)(same("short") as ResetPasswordFormValues, undefined, options);
    expect(weak.errors?.newPassword?.message).toBe("Password must be at least 8 characters long.");
    expect(weak.errors?.confirmPassword).toBeUndefined();

    const mismatch = await zodResolver(resetPasswordSchema)({ newPassword: strong, confirmPassword: "nope" } as ResetPasswordFormValues, undefined, options);
    expect(mismatch.errors?.confirmPassword?.message).toBe("Passwords do not match.");
    expect(mismatch.errors?.newPassword).toBeUndefined();
  });
});

describe("completeRegistrationSchema", () => {
  const strong = "Abcdef1!";
  const valid = {
    newPassword: strong,
    confirmPassword: strong,
    phone: "9876543210",
    gender: "female",
    dateOfBirth: "1999-04-01",
    addressLine1: "12 Park Street",
    city: "Hyderabad",
    state: "Telangana",
    country: "India",
    postalCode: "500001",
    emergencyContactName: "Asha Rao",
    emergencyContactPhone: "9123456780",
  };

  it("accepts a fully filled registration", () => {
    expect(issuesOf(completeRegistrationSchema, valid)).toEqual([]);
  });

  it.each([...genderValues])("accepts the gender %s", (gender) => {
    expect(issuesOf(completeRegistrationSchema, { ...valid, gender })).toEqual([]);
  });

  it.each([
    ["phone", "phone: Phone is required."],
    ["dateOfBirth", "dateOfBirth: Date of birth is required."],
    ["addressLine1", "addressLine1: Address is required."],
    ["city", "city: City is required."],
    ["state", "state: State is required."],
    ["country", "country: Country is required."],
    ["postalCode", "postalCode: Postal code is required."],
    ["emergencyContactName", "emergencyContactName: Emergency contact name is required."],
    ["emergencyContactPhone", "emergencyContactPhone: Emergency contact phone is required."],
  ])("requires %s with the custom message", (field, expected) => {
    expect(issuesOf(completeRegistrationSchema, { ...valid, [field]: "" })).toEqual([expected]);
  });

  it("rejects an unknown gender with the custom message", () => {
    expect(issuesOf(completeRegistrationSchema, { ...valid, gender: "robot" })).toEqual(["gender: Select a valid gender."]);
  });

  it("rejects an empty gender with BOTH messages, 'required' first (the form shows the first)", () => {
    expect(issuesOf(completeRegistrationSchema, { ...valid, gender: "" })).toEqual(["gender: Gender is required.", "gender: Select a valid gender."]);
  });

  it("applies the same password rules and mismatch check as the reset form", () => {
    expect(issuesOf(completeRegistrationSchema, { ...valid, newPassword: "short", confirmPassword: "short" })).toEqual([
      "newPassword: Password must be at least 8 characters long.",
      "newPassword: Password must contain at least one uppercase letter.",
      "newPassword: Password must contain at least one digit.",
      "newPassword: Password must contain at least one special character.",
    ]);
    expect(issuesOf(completeRegistrationSchema, { ...valid, confirmPassword: "Different1!" })).toEqual(["confirmPassword: Passwords do not match."]);
  });

  it("works through the real zodResolver the way the registration page uses it", async () => {
    const good = await zodResolver(completeRegistrationSchema)(valid as CompleteRegistrationFormValues, undefined, options);
    expect(good.errors).toEqual({});
    expect(good.values).toEqual(valid);

    const bad = await zodResolver(completeRegistrationSchema)({ ...valid, phone: "", gender: "" } as CompleteRegistrationFormValues, undefined, options);
    expect(bad.errors?.phone?.message).toBe("Phone is required.");
    expect(bad.errors?.gender?.message).toBe("Gender is required.");
  });
});
