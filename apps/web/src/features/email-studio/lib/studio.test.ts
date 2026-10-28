import { describe, expect, it } from "vitest";

import type { Brand, LibraryItem, Placeholder } from "@/features/email-studio/api/studio-api";
import { brandTheme, filterLibrary, formatBytes, groupByCategory, groupPlaceholders, htmlIssues, token } from "@/features/email-studio/lib/studio";

const item = (over: Partial<LibraryItem>): LibraryItem => ({
  id: "1", key: null, name: "A", description: "", category: "Custom Emails", creation_method: "Visual editor", source_type: "visual", module: null,
  status: "draft", updated_at: null, updated_by_name: null, is_system: false, assigned_to: [], customised: false, has_attachment: false, has_draft: false,
  can_delete: true, delete_blocked_reason: null, used_by: [], deleted_at: null, deleted_by_name: null, ...over,
});

describe("filterLibrary", () => {
  const items = [
    item({ id: "1", name: "Welcome", category: "Internship Onboarding", updated_at: "2026-10-01T00:00:00Z" }),
    item({ id: "2", name: "Offer", category: "Internship Offer Letters", source_type: "code", status: "published", updated_at: "2026-10-20T00:00:00Z" }),
    item({ id: "3", name: "Reset", category: "Password Reset", source_type: "default", status: "active", is_system: true }),
  ];
  const base = { q: "", category: "", status: "", method: "", sort: "name" as const };
  it("searches name, description and category, case-insensitively", () => {
    expect(filterLibrary(items, { ...base, q: "offer" }).map((i) => i.id)).toEqual(["2"]);
    expect(filterLibrary(items, { ...base, q: "ONBOARDING" }).map((i) => i.id)).toEqual(["1"]);
  });
  it("filters by category, status and creation method", () => {
    expect(filterLibrary(items, { ...base, status: "published" }).map((i) => i.id)).toEqual(["2"]);
    expect(filterLibrary(items, { ...base, method: "default" }).map((i) => i.id)).toEqual(["3"]);
    expect(filterLibrary(items, { ...base, category: "Password Reset" }).map((i) => i.id)).toEqual(["3"]);
  });
  it("sorts by name, last update or category", () => {
    expect(filterLibrary(items, base).map((i) => i.name)).toEqual(["Offer", "Reset", "Welcome"]);
    expect(filterLibrary(items, { ...base, sort: "updated" }).map((i) => i.id)).toEqual(["2", "1", "3"]);
    expect(filterLibrary(items, { ...base, sort: "category" }).map((i) => i.category)).toEqual(["Internship Offer Letters", "Internship Onboarding", "Password Reset"]);
  });
  it("groups by category", () => {
    expect(groupByCategory(items).map(([c]) => c)).toEqual(["Internship Onboarding", "Internship Offer Letters", "Password Reset"]);
  });
});

describe("placeholders", () => {
  const list: Placeholder[] = [
    { name: "student_name", group: "Student", description: "The student's name", sample: "Asha" },
    { name: "reset_url", group: "Account", description: "The reset link", sample: "" },
    { name: "student_email", group: "Student", description: "Their address", sample: "" },
  ];
  it("groups and searches them", () => {
    expect(groupPlaceholders(list, "").map(([g, p]) => [g, p.length])).toEqual([["Student", 2], ["Account", 1]]);
    expect(groupPlaceholders(list, "link").map(([g]) => g)).toEqual(["Account"]);
    expect(groupPlaceholders(list, "nothing")).toEqual([]);
  });
  it("writes a token", () => expect(token("student_name")).toBe("{{student_name}}"));
});

describe("htmlIssues", () => {
  it("accepts clean HTML", () => expect(htmlIssues("<table><tr><td>Hi {{student_name}}</td></tr></table>")).toEqual([]));
  it("warns about what will be removed", () => {
    const issues = htmlIssues('<script>x</script><iframe></iframe><style>a{}</style><p onclick="x()">hi</p>');
    expect(issues.join(" ")).toMatch(/Scripts/);
    expect(issues.join(" ")).toMatch(/Frames/);
    expect(issues.join(" ")).toMatch(/style/);
    expect(issues.join(" ")).toMatch(/Event handlers/);
  });
  it("finds unclosed and stray tags and an empty document", () => {
    expect(htmlIssues("<div><span>x</div>").join(" ")).toMatch(/never closed/);
    expect(htmlIssues("</div>").join(" ")).toMatch(/no opening tag/);
    expect(htmlIssues("   ")).toEqual(["The HTML is empty."]);
  });
});

describe("brandTheme", () => {
  it("is the basic theme without a brand and carries a brand's colours with one", () => {
    expect(brandTheme(null)).toBe("basic");
    const theme = brandTheme({ primary_color: "#111111", secondary_color: "#222222", background_color: "#333333", text_color: "#444444" } as Brand);
    if (typeof theme === "string") throw new Error("expected a theme object");
    expect(theme.styles.button.backgroundColor).toBe("#111111");
    expect(theme.styles.body.backgroundColor).toBe("#333333");
    expect(theme.styles.h3.color).toBe("#222222");
  });
});

describe("formatBytes", () => {
  it("is readable", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});
