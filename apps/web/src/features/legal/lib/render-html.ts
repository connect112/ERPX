import { COMPANY, SITE, type LegalDocument } from "@/features/legal/lib/legal-content";

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** Turns bare web addresses and email addresses in a sentence into links (after escaping the text). */
function link(text: string): string {
  return escapeHtml(text)
    .replace(/(https:\/\/[^\s<)]+[^\s<).,])/g, '<a href="$1">$1</a>')
    .replace(/([A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g, '<a href="mailto:$1">$1</a>');
}

/**
 * The same text as the React pages, as one plain HTML file with no JavaScript. Crawlers and review tools (Meta's checks, search
 * engines, people with scripts blocked) read this directly. `public/privacy.html` and `public/data-deletion.html` are generated
 * from it, and a test fails if they drift from the content in `legal-content.ts`.
 */
export function renderLegalHtml(doc: LegalDocument, path: "privacy" | "data-deletion"): string {
  const sections = doc.sections
    .map((s) => {
      const paragraphs = (s.paragraphs ?? []).map((p) => `<p>${link(p)}</p>`).join("\n");
      const items = s.items ? `<ul>\n${s.items.map((i) => `<li>${link(i)}</li>`).join("\n")}\n</ul>` : "";
      return `<section>\n<h2>${escapeHtml(s.heading)}</h2>\n${paragraphs}\n${items}\n</section>`;
    })
    .join("\n");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(doc.title)} - ${escapeHtml(COMPANY)}</title>
<meta name="description" content="${escapeHtml(doc.title)} for ${escapeHtml(COMPANY)} (${SITE}).">
<link rel="canonical" href="https://${SITE}/${path}">
<style>
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.6;color:#0f172a;margin:0;background:#fff}
main{max-width:46rem;margin:0 auto;padding:2.5rem 1rem}
h1{font-size:1.9rem;margin:.25rem 0}
h2{font-size:1.25rem;margin:2rem 0 .5rem}
.muted{color:#475569;font-size:.9rem}
a{color:#1d4ed8}
nav{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #e2e8f0;display:flex;gap:1.25rem;flex-wrap:wrap;font-size:.9rem}
</style>
</head>
<body>
<main>
<p class="muted">${escapeHtml(COMPANY)}</p>
<h1>${escapeHtml(doc.title)}</h1>
<p class="muted">Last updated ${escapeHtml(doc.updated)}</p>
<p>${link(doc.intro)}</p>
${sections}
<nav aria-label="Legal pages">
<a href="https://${SITE}/privacy">Privacy Policy</a>
<a href="https://${SITE}/data-deletion">Data Deletion</a>
<a href="https://${SITE}/login">Sign in</a>
</nav>
</main>
</body>
</html>
`;
}
