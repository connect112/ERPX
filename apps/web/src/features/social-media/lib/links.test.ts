import { describe, expect, it } from "vitest";

import { safeHref } from "@/features/social-media/lib/links";

describe("safeHref", () => {
  it("lets a plain https address through", () => {
    expect(safeHref("https://www.instagram.com/p/abc/")).toBe("https://www.instagram.com/p/abc/");
    expect(safeHref("https://nvd.nist.gov/vuln/detail/CVE-2026-1")).toBeDefined();
  });

  it("gives no link for anything else", () => {
    for (const bad of ["javascript:alert(1)", "data:text/html,<script>1</script>", "http://example.com", "//example.com", "https://user:pw@example.com/", "https://localhost/", "not a url", "https://exa mple.com", "", null, undefined]) {
      expect(safeHref(bad as string | null | undefined)).toBeUndefined();
    }
    expect(safeHref(`https://example.com/${"a".repeat(1100)}`)).toBeUndefined();
  });
});
