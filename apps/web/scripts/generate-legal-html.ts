// Writes the static legal pages. Run after changing src/features/legal/lib/legal-content.ts:
//   npx vite-node scripts/generate-legal-html.ts
import { mkdirSync, writeFileSync } from "node:fs";

import { DATA_DELETION, PRIVACY_POLICY } from "../src/features/legal/lib/legal-content";
import { renderLegalHtml } from "../src/features/legal/lib/render-html";

mkdirSync("public", { recursive: true });
writeFileSync("public/privacy.html", renderLegalHtml(PRIVACY_POLICY, "privacy"), "utf-8");
writeFileSync("public/data-deletion.html", renderLegalHtml(DATA_DELETION, "data-deletion"), "utf-8");
console.log("wrote public/privacy.html and public/data-deletion.html");
