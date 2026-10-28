// @vitest-environment happy-dom
import { describe, expect, it } from "vitest";

import { compareFacts, factsOfDoc, factsOfHtml } from "@/features/email-studio/lib/convert";
import { BUILD_LABEL, buildState } from "@/features/email-studio/lib/react-import";
import type { ReactBuild } from "@/features/email-studio/api/studio-api";

const HTML = `<!DOCTYPE html><html><head><title>T</title><style>p{}</style></head><body>
<div style="display:none">Preview line&nbsp;&zwnj;</div>
<table><tbody><tr><td><h1>Hi {{student_name}}</h1><p>Open <a href="https://x.example/a">the page</a> now.</p>
<img src="https://cdn.example.com/logo.png" alt="Logo"></td></tr></tbody></table></body></html>`;

const doc = (extra: object[] = []) => ({
  type: "doc",
  content: [
    { type: "heading", attrs: { level: 1 }, content: [{ type: "text", text: "Hi {{student_name}}" }] },
    { type: "paragraph", content: [{ type: "text", text: "Open " }, { type: "text", text: "the page", marks: [{ type: "link", attrs: { href: "https://x.example/a" } }] }, { type: "text", text: " now." }] },
    { type: "paragraph", content: [{ type: "text", text: "Preview line" }] },
    ...extra,
  ],
});

describe("conversion report", () => {
  it("lists the text, links, images and tables an email contains, ignoring the page head", () => {
    const facts = factsOfHtml(HTML);
    expect(facts.text).toContain("Hi {{student_name}}");
    expect(facts.text).not.toContain("T");
    expect(facts.links).toEqual(["https://x.example/a"]);
    expect(facts.images).toEqual(["https://cdn.example.com/logo.png"]);
    expect(facts.tables).toBe(1);
  });

  it("reads the same things from an editor document", () => {
    const facts = factsOfDoc(doc([{ type: "image", attrs: { src: "https://cdn.example.com/logo.png" } }]));
    expect(facts.links).toEqual(["https://x.example/a"]);
    expect(facts.images).toEqual(["https://cdn.example.com/logo.png"]);
    expect(facts.text.join(" ")).toContain("Open the page now.".replace("the page", "the page"));
  });

  it("reports nothing lost when everything carried over", () => {
    const report = compareFacts(factsOfHtml(HTML), factsOfDoc(doc([{ type: "image", attrs: { src: "https://cdn.example.com/logo.png" } }])));
    expect(report.lost).toEqual([]);
    expect(report.notes.some((n) => n.includes("code version"))).toBe(true);
  });

  it("names every kind of thing that did not carry over, instead of dropping it silently", () => {
    const report = compareFacts(factsOfHtml(HTML), factsOfDoc({ type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Something else" }] }] }));
    expect(report.lost.join("\n")).toContain("Text that did not carry over");
    expect(report.lost.join("\n")).toContain("Hi {{student_name}}");
    expect(report.lost.join("\n")).toContain("Links that did not carry over (1): https://x.example/a");
    expect(report.lost.join("\n")).toContain("Images that did not carry over (1): https://cdn.example.com/logo.png");
  });
});

describe("build state", () => {
  const ok = { ok: true, errors: [], warnings: [], html: "", text: "", title: "", preheader: "", placeholders: [], unsupported_placeholders: [], components: [] } as ReactBuild;
  it("tracks whether the build still matches the code on screen", () => {
    expect(buildState(null, false, null, "a")).toBe("idle");
    expect(buildState(null, true, null, "a")).toBe("building");
    expect(buildState(ok, false, "a", "a")).toBe("ok");
    expect(buildState(ok, false, "a", "ab")).toBe("stale");
    expect(buildState({ ...ok, ok: false }, false, "a", "a")).toBe("errors");
    expect(BUILD_LABEL.stale.label).toMatch(/Changed/);
  });
});
