import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { DATA_DELETION, PRIVACY_POLICY } from "@/features/legal/lib/legal-content";
import { renderLegalHtml } from "@/features/legal/lib/render-html";

const read = (file: string) => readFileSync(`public/${file}`, "utf-8").replace(/\r\n/g, "\n");

describe("static legal pages", () => {
  it("are exactly what the content file renders (run `npx vite-node scripts/generate-legal-html.ts` after editing it)", () => {
    expect(read("privacy.html")).toBe(renderLegalHtml(PRIVACY_POLICY, "privacy"));
    expect(read("data-deletion.html")).toBe(renderLegalHtml(DATA_DELETION, "data-deletion"));
  });

  it("are plain HTML a crawler can read: real text, no scripts", () => {
    for (const [file, heading] of [["privacy.html", "Privacy Policy"], ["data-deletion.html", "Data Deletion"]] as const) {
      const html = read(file);
      expect(html).toContain(`<h1>${heading}</h1>`);
      expect(html).toContain("mailto:info@girtechnologies.com");
      expect(html.toLowerCase()).not.toContain("<script");
    }
  });

  it("escapes text instead of trusting it", () => {
    const html = renderLegalHtml({ title: "T", updated: "x", intro: "a <b>bold</b> & \"quoted\"", sections: [] }, "privacy");
    expect(html).toContain("a &lt;b&gt;bold&lt;/b&gt; &amp; &quot;quoted&quot;");
    expect(html).not.toContain("<b>bold</b>");
  });
});
