import { describe, expect, it } from "vitest";

import { formatBytes, insertAt, placeholdersIn, unknownPlaceholders } from "@/features/bulk-downloads/lib/template";

describe("file name format helpers", () => {
  it("inserts a placeholder at the cursor and moves the cursor after it", () => {
    expect(insertAt("_.pdf", "student_name", 0, 0)).toEqual({ text: "{{student_name}}_.pdf", cursor: 16 });
    expect(insertAt("ab", "x", null, null)).toEqual({ text: "ab{{x}}", cursor: 7 });
  });

  it("replaces selected text", () => {
    expect(insertAt("NAME.pdf", "student_name", 0, 4).text).toBe("{{student_name}}.pdf");
  });

  it("finds placeholders, tolerating spaces inside the braces", () => {
    expect(placeholdersIn("{{ a }}_{{b}}.pdf")).toEqual(["a", "b"]);
  });

  it("spots unknown placeholders once each", () => {
    expect(unknownPlaceholders("{{a}}{{roll}}{{roll}}", ["a"])).toEqual(["roll"]);
    expect(unknownPlaceholders("{{a}}", ["a"])).toEqual([]);
  });

  it("formats sizes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});
