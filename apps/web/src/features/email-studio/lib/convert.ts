import type { EditorDoc } from "@/features/email-studio/api/studio-api";

/**
 * Turning an imported (code) email into a visual-editor design must not lose anything silently. These helpers list what an email
 * contains -- its text, links and images -- before and after, so the person is told exactly what did not make it across.
 */
export interface Facts {
  text: string[];
  links: string[];
  images: string[];
  tables: number;
}

export interface ConversionReport {
  /** Things that are in the original but not in the design. Empty means nothing was lost. */
  lost: string[];
  /** Things that change shape but still look the same. */
  notes: string[];
}

const squash = (value: string) => value.replace(/[\u200b-\u200d\u2060\ufeff]/g, "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();

export function factsOfHtml(html: string): Facts {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const text: string[] = [];
  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const value = squash(node.textContent ?? "");
      if (value) text.push(value);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const tag = (node as Element).tagName.toLowerCase();
    if (tag === "script" || tag === "style" || tag === "title") return;
    node.childNodes.forEach(walk);
  };
  walk(doc.body);
  return {
    text,
    links: [...new Set([...doc.querySelectorAll("a[href]")].map((a) => a.getAttribute("href") ?? "").filter(Boolean))],
    images: [...new Set([...doc.querySelectorAll("img[src]")].map((i) => i.getAttribute("src") ?? "").filter(Boolean))],
    tables: doc.querySelectorAll("table").length,
  };
}

export function factsOfDoc(doc: EditorDoc): Facts {
  const text: string[] = [];
  const links = new Set<string>();
  const images = new Set<string>();
  let tables = 0;
  const walk = (node: Record<string, unknown>) => {
    const type = node.type as string;
    const attrs = (node.attrs ?? {}) as Record<string, unknown>;
    if (type === "text" && typeof node.text === "string") {
      const value = squash(node.text);
      if (value) text.push(value);
    }
    for (const mark of (node.marks ?? []) as { type: string; attrs?: Record<string, unknown> }[]) {
      if (mark.type === "link" && typeof mark.attrs?.href === "string" && mark.attrs.href) links.add(mark.attrs.href);
    }
    if (typeof attrs.href === "string" && attrs.href) links.add(attrs.href);
    if ((type === "image" || type === "img") && typeof attrs.src === "string" && attrs.src) images.add(attrs.src);
    if (type === "table") tables += 1;
    for (const child of (node.content ?? []) as Record<string, unknown>[]) walk(child);
  };
  walk(doc as Record<string, unknown>);
  return { text, links: [...links], images: [...images], tables };
}

export function compareFacts(before: Facts, after: Facts): ConversionReport {
  const lost: string[] = [];
  const everything = squash(after.text.join(" "));
  const missingText = before.text.filter((t) => !everything.includes(t));
  if (missingText.length) lost.push(`Text that did not carry over (${missingText.length}): ${missingText.slice(0, 5).map((t) => `"${t.length > 60 ? `${t.slice(0, 57)}...` : t}"`).join(", ")}${missingText.length > 5 ? ", ..." : ""}`);
  const missingLinks = before.links.filter((l) => !after.links.includes(l));
  if (missingLinks.length) lost.push(`Links that did not carry over (${missingLinks.length}): ${missingLinks.slice(0, 4).join(", ")}${missingLinks.length > 4 ? ", ..." : ""}`);
  const missingImages = before.images.filter((i) => !after.images.includes(i));
  if (missingImages.length) lost.push(`Images that did not carry over (${missingImages.length}): ${missingImages.slice(0, 3).join(", ")}${missingImages.length > 3 ? ", ..." : ""}`);

  const notes: string[] = [];
  if (before.tables > 0) notes.push("Layout tables stay tables. Their widths and spacing are kept as written, but the visual editor's inspector may not offer controls for every one.");
  notes.push("Buttons become styled links that look the same; edit them as links.");
  notes.push("The original code is not changed: the design is saved as a new template, and the code version stays in your library.");
  return { lost, notes };
}
