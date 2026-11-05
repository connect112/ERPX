/**
 * What react-hook-form actually receives from the real `zodResolver` for a few representative forms, plus the
 * email rules every form shares. Recorded on Zod 3 + @hookform/resolvers 3 and kept unchanged across the move
 * to Zod 4 + resolvers 5: a failure here is a user-visible form regression.
 *
 * (schemas.test.ts covers every schema exhaustively through safeParse; this file covers the layer in between,
 * the resolver, where the first message per field, the nested `lines.0.x` paths and the coerced/defaulted
 * values that reach the submit handler are decided.)
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { describe, expect, it } from "vitest";

import { loginSchema, registerSchema } from "@/features/auth/schemas/auth-schemas";
import { eventFormSchema } from "@/features/events/schemas/event-schemas";
import { invoiceFormSchema } from "@/features/accounting/invoices/schemas/invoice-schemas";
import { itemFormSchema } from "@/features/inventory/items/schemas/item-schemas";
import { installZodMessages } from "@/lib/zod-messages";

installZodMessages();

const options = { fields: {}, shouldUseNativeValidation: false } as const;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function resolve(schema: any, values: unknown) {
  const result = await zodResolver(schema)(values as never, undefined, options as never);
  return result as { values: unknown; errors: Record<string, unknown> };
}

/** `field: message` for every top-level field the resolver reports (the first message per field). */
function messages(errors: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(Object.entries(errors).map(([k, v]) => [k, (v as { message?: string }).message ?? JSON.stringify(v)]));
}

describe("email rules shared by every .email() field", () => {
  const ok = { password: "x" };
  const accepted = ["a@b.co", "john+tag@example.com", "first.last@sub.example.org", "A@B.COM", "x@y.museum", "o'brien@example.ie", "a_b-c@example.co.uk"];
  const rejected = ["", "not-an-email", "a@b", "user@localhost", "a b@c.com", "a@b..com", ".a@b.com", "a.@b.com", "a@-b.com", "a@b.c", "x@192.168.0.1", "@example.com", "user@", "user@@example.com"];

  it.each(accepted)("accepts %s", (email) => {
    expect(loginSchema.safeParse({ ...ok, email }).success).toBe(true);
  });
  it.each(rejected)("rejects %j", (email) => {
    expect(loginSchema.safeParse({ ...ok, email }).success).toBe(false);
  });
});

describe("zodResolver with the event form (enum message, trim, cross-field rule)", () => {
  const valid = { title: "  Annual day ", description: "Everyone", eventType: "meeting", startAt: "2025-06-15T10:00", endAt: "2025-06-15T12:00", location: "Hall", isAllDay: false };

  it("hands over trimmed values and no errors for a valid form", async () => {
    const r = await resolve(eventFormSchema, valid);
    expect(r.errors).toEqual({});
    expect(r.values).toEqual({ ...valid, title: "Annual day" });
  });

  it("reports the first message per field for an empty form", async () => {
    const r = await resolve(eventFormSchema, { title: "", description: "", eventType: "", startAt: "", endAt: "", location: "", isAllDay: false });
    expect(messages(r.errors)).toEqual({
      title: "Title is required.",
      description: "Description is required.",
      eventType: "Type is required.",
      startAt: "Start date/time is required.",
      endAt: "End date/time is required.",
      location: "Location is required.",
    });
  });

  it("uses the custom enum message even when nothing was chosen at all", async () => {
    const r = await resolve(eventFormSchema, { ...valid, eventType: undefined });
    expect(messages(r.errors)).toEqual({ eventType: "Type is required." });
  });

  it("puts the end-before-start rule on endAt", async () => {
    const r = await resolve(eventFormSchema, { ...valid, endAt: "2025-06-15T09:00" });
    expect(messages(r.errors)).toEqual({ endAt: "End must be after the start." });
  });
});

describe("zodResolver with the item form (z.coerce.number + default)", () => {
  const base = { sku: "SKU-1", name: "Widget", unitOfMeasure: "pcs" };

  it("turns the numbers typed as text into numbers", async () => {
    const r = await resolve(itemFormSchema, { ...base, reorderLevel: "5", reorderQuantity: "12.5", standardCost: "100" });
    expect(r.errors).toEqual({});
    expect(r.values).toMatchObject({ reorderLevel: 5, reorderQuantity: 12.5, standardCost: 100 });
  });

  it("fills the default when the field is missing, and reads an empty box as zero", async () => {
    const missing = await resolve(itemFormSchema, base);
    expect(missing.values).toMatchObject({ reorderLevel: 0, reorderQuantity: 0, standardCost: 0 });
    const empty = await resolve(itemFormSchema, { ...base, reorderLevel: "", standardCost: "" });
    expect(empty.errors).toEqual({});
    expect(empty.values).toMatchObject({ reorderLevel: 0, standardCost: 0 });
  });

  it("shows the custom message for a negative number and Zod's own wording for text", async () => {
    const r = await resolve(itemFormSchema, { ...base, reorderLevel: "-1", reorderQuantity: "abc" });
    expect(messages(r.errors)).toEqual({ reorderLevel: "Must be zero or more.", reorderQuantity: "Expected number, received nan" });
  });
});

describe("zodResolver with the register form (refine on another field)", () => {
  const valid = { fullName: "Asha Rao", email: "asha@example.com", password: "Passw0rd!x", confirmPassword: "Passw0rd!x" };

  it("accepts matching passwords", async () => {
    const r = await resolve(registerSchema, valid);
    expect(r.errors).toEqual({});
  });

  it("reports the mismatch on confirmPassword", async () => {
    const r = await resolve(registerSchema, { ...valid, confirmPassword: "different" });
    expect(messages(r.errors)).toEqual({ confirmPassword: "Passwords do not match." });
  });

  it("shows only the first password rule that fails", async () => {
    const r = await resolve(registerSchema, { ...valid, password: "abc", confirmPassword: "abc" });
    expect(messages(r.errors)).toEqual({ password: "Password must be at least 8 characters long." });
  });
});

describe("zodResolver with the invoice form (array of lines)", () => {
  const line = { revenueAccountId: "acc1", description: "Consulting", quantity: "1", unitPrice: "100" };
  const valid = {
    customerId: "c1",
    invoiceNumber: "INV-1",
    invoiceDate: "2025-06-01",
    dueDate: "2025-06-30",
    receivableAccountId: "r1",
    isInterstate: false,
    lines: [line],
  };

  it("accepts a valid invoice", async () => {
    expect((await resolve(invoiceFormSchema, valid)).errors).toEqual({});
  });

  it("asks for at least one line", async () => {
    const r = await resolve(invoiceFormSchema, { ...valid, lines: [] });
    expect(messages(r.errors)).toEqual({ lines: "At least one line is required." });
  });

  it("reports a missing line field under lines[index].field", async () => {
    const r = await resolve(invoiceFormSchema, { ...valid, lines: [line, { ...line, description: "" }] });
    const lines = r.errors.lines as unknown as { message?: string }[];
    expect(lines[0]).toBeUndefined();
    expect((lines[1] as unknown as Record<string, { message: string }>).description.message).toBe("Description is required.");
  });
});
