import type { Brand, DraftPayload, LibraryItem, Placeholder, TemplateOut } from "@/features/email-studio/api/studio-api";

export const EMPTY_DOC = { type: "doc", content: [{ type: "paragraph" }] };

export const SOURCE_LABEL: Record<string, string> = {
  visual: "Visual editor",
  html: "HTML import",
  code: "React Email component",
  markdown: "Markdown (built-in)",
  default: "Built-in",
};

export const STATUS_LABEL: Record<string, { label: string; variant: "success" | "warning" | "secondary" | "info" }> = {
  published: { label: "Published", variant: "success" },
  draft: { label: "Draft", variant: "warning" },
  archived: { label: "Archived", variant: "secondary" },
  active: { label: "Active", variant: "info" },
};

export const SEND_STATUS: Record<string, { label: string; variant: "success" | "warning" | "secondary" | "info" | "destructive" }> = {
  queued: { label: "Queued", variant: "secondary" },
  sending: { label: "Sending", variant: "info" },
  sent: { label: "Sent", variant: "success" },
  delivered: { label: "Delivered", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
  bounced: { label: "Bounced", variant: "destructive" },
};

/** The editor theme for a brand: its colours become the page, headings, buttons and links of the design. */
export function brandTheme(brand: Brand | null) {
  if (!brand) return "basic" as const;
  return {
    extends: "basic" as const,
    styles: {
      body: { backgroundColor: brand.background_color, color: brand.text_color },
      container: { backgroundColor: "#ffffff", color: brand.text_color },
      h1: { color: brand.primary_color },
      h2: { color: brand.primary_color },
      h3: { color: brand.secondary_color },
      link: { color: brand.primary_color },
      button: { backgroundColor: brand.primary_color, color: "#ffffff", borderRadius: "6px" },
    },
  };
}

export interface LibraryFilters {
  q: string;
  category: string;
  status: string;
  method: string;
  sort: "name" | "updated" | "category";
}

export function filterLibrary(items: LibraryItem[], f: LibraryFilters): LibraryItem[] {
  const q = f.q.trim().toLowerCase();
  const out = items.filter(
    (i) =>
      (!q || `${i.name} ${i.description} ${i.category} ${i.module ?? ""}`.toLowerCase().includes(q)) &&
      (!f.category || i.category === f.category) &&
      (!f.status || i.status === f.status) &&
      (!f.method || i.source_type === f.method),
  );
  return [...out].sort((a, b) => {
    if (f.sort === "updated") return (b.updated_at ?? "").localeCompare(a.updated_at ?? "");
    if (f.sort === "category") return a.category.localeCompare(b.category) || a.name.localeCompare(b.name);
    return a.name.localeCompare(b.name);
  });
}

export function groupByCategory(items: LibraryItem[]): [string, LibraryItem[]][] {
  const map = new Map<string, LibraryItem[]>();
  for (const i of items) map.set(i.category, [...(map.get(i.category) ?? []), i]);
  return [...map.entries()];
}

export function groupPlaceholders(list: Placeholder[], query: string): [string, Placeholder[]][] {
  const q = query.trim().toLowerCase();
  const map = new Map<string, Placeholder[]>();
  for (const p of list) {
    if (q && !`${p.name} ${p.description} ${p.group}`.toLowerCase().includes(q)) continue;
    map.set(p.group, [...(map.get(p.group) ?? []), p]);
  }
  return [...map.entries()];
}

export const token = (name: string) => `{{${name}}}`;

/** Quick problems with HTML an administrator typed or pasted, before the server checks it. */
export function htmlIssues(source: string): string[] {
  const issues: string[] = [];
  if (!source.trim()) return ["The HTML is empty."];
  if (source.length > 600_000) issues.push("The HTML is over 600 KB, which is too large for an email.");
  if (/<script\b/i.test(source)) issues.push("Scripts are removed from emails for safety.");
  if (/<(iframe|form|object|embed)\b/i.test(source)) issues.push("Frames, forms and embedded objects are removed from emails.");
  if (/<style\b/i.test(source)) issues.push("<style> blocks are removed; use inline style attributes instead.");
  if (/\son[a-z]+\s*=/i.test(source)) issues.push("Event handlers such as onclick are removed.");
  const voids = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);
  const optionalClose = new Set(["p", "li", "td", "tr", "th", "tbody", "thead", "tfoot", "dd", "dt"]);
  const stack: string[] = [];
  const tag = /<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(\/?)>/g;
  let m: RegExpExecArray | null;
  const body = source.replace(/<!--[\s\S]*?-->/g, "").replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, "");
  while ((m = tag.exec(body))) {
    const name = m[1].toLowerCase();
    if (voids.has(name) || m[2] === "/") continue;
    if (m[0].startsWith("</")) {
      const at = stack.lastIndexOf(name);
      if (at === -1) issues.push(`A closing </${name}> has no opening tag.`);
      else {
        const skipped = stack.slice(at + 1).filter((n) => !optionalClose.has(n));
        if (skipped.length) issues.push(`<${skipped[skipped.length - 1]}> is never closed before </${name}>.`);
        stack.splice(at);
      }
    } else stack.push(name);
  }
  const open = [...new Set(stack.filter((n) => !["html", "body", "head", "p", "li", "td", "tr", "th"].includes(n)))];
  if (open.length) issues.push(`These tags are never closed: ${open.map((n) => `<${n}>`).join(", ")}.`);
  return issues;
}

/** The payload that saves, previews or tests a template from what is on screen. */
export function draftPayload(t: TemplateOut, edits: Partial<DraftPayload>): DraftPayload {
  const c = t.current;
  return {
    subject: c.subject,
    preheader: c.preheader,
    editor_json: c.editor_json,
    html: t.source_type === "html" ? (c.html_source ?? c.body_html) : c.body_html,
    code_template_key: c.code_template_key,
    code_props: c.code_props,
    brand_profile_id: c.brand_profile_id,
    signature_id: c.signature_id,
    config: c.config ?? {},
    ...edits,
  };
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
