import { describe, expect, it } from "vitest";

import { courseDialogSchema } from "@/features/courses/lib/dialog-schema";
import { feeText, money } from "@/features/courses/lib/fee";

const base = { courseType: "regular" as const, showInternshipFee: false, title: "Linux Basics", slug: "linux-basics", level: "beginner" as const, categoryId: "", shortDescription: "", description: "", thumbnailUrl: "", durationHours: "", price: "" };

describe("the course dialog's rules", () => {
  it("accepts a regular course with a price exactly as before", () => {
    expect(courseDialogSchema.safeParse({ ...base, price: "2500" }).success).toBe(true);
    expect(courseDialogSchema.safeParse({ ...base, slug: "Bad Slug" }).success).toBe(false);
  });

  it("gives an internship course no price of its own", () => {
    expect(courseDialogSchema.safeParse({ ...base, courseType: "internship" }).success).toBe(true);
    expect(courseDialogSchema.safeParse({ ...base, courseType: "internship", price: "0" }).success).toBe(true);
    const priced = courseDialogSchema.safeParse({ ...base, courseType: "internship", price: "500" });
    expect(priced.success).toBe(false);
    expect(priced.error?.issues[0].message).toContain("no price of its own");
  });
});

describe("how a fee is written", () => {
  it("formats rupees the Indian way and mentions the tax it includes", () => {
    expect(money("5900.00", "INR")).toBe("₹5,900.00");
    expect(feeText({ currency: "INR", total: "5900.00", base: "5000.00", discount: "0.00", tax_mode: "exclusive", tax_label: "GST", tax: "900.00" })).toBe("₹5,900.00 (includes GST ₹900.00)");
    expect(feeText({ currency: "INR", total: "2000.00", base: "2000.00", discount: "0.00", tax_mode: "none", tax_label: "GST", tax: "0.00" })).toBe("₹2,000.00");
  });
});
