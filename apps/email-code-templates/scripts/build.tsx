/**
 * Renders every approved template to static HTML for the API.
 *
 *   npm run build   writes ../../modules/email_studio/code_templates/<key>.html and manifest.json
 *   npm run check   fails if the files on disk differ from what the source would produce (used by CI and the API tests)
 *
 * Each property is rendered as a {{prop:name}} token and each ERPX value as an ordinary {{placeholder}}; the API fills them in.
 */
import { render } from "@react-email/render";
import { createElement } from "react";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import * as accountVerification from "../src/templates/account-verification";
import * as certificateDistribution from "../src/templates/certificate-distribution";
import * as internshipOffer from "../src/templates/internship-offer";
import * as internshipWelcome from "../src/templates/internship-welcome";
import * as passwordReset from "../src/templates/password-reset";
import type { TemplateMeta } from "../src/types";

const TEMPLATES: { meta: TemplateMeta; default: (props: Record<string, string>) => JSX.Element }[] = [
  accountVerification,
  passwordReset,
  internshipOffer,
  internshipWelcome,
  certificateDistribution,
];

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "..", "..", "..", "modules", "email_studio", "code_templates");
const check = process.argv.includes("--check");

let failed = false;
const manifest: TemplateMeta[] = [];
mkdirSync(out, { recursive: true });

for (const t of TEMPLATES) {
  const props = Object.fromEntries(t.meta.props.map((p) => [p.name, `{{prop:${p.name}}}`]));
  const html = await render(createElement(t.default, props));
  manifest.push(t.meta);
  const file = join(out, `${t.meta.key}.html`);
  if (check) {
    if (!existsSync(file) || readFileSync(file, "utf-8") !== html) {
      console.error(`out of date: ${t.meta.key}.html (run npm run build)`);
      failed = true;
    }
  } else {
    writeFileSync(file, html, "utf-8");
  }
}

const manifestText = JSON.stringify(manifest, null, 2) + "\n";
const manifestFile = join(out, "manifest.json");
if (check) {
  if (!existsSync(manifestFile) || readFileSync(manifestFile, "utf-8") !== manifestText) {
    console.error("out of date: manifest.json (run npm run build)");
    failed = true;
  }
  if (failed) process.exit(1);
  console.log("approved templates are up to date");
} else {
  writeFileSync(manifestFile, manifestText, "utf-8");
  console.log(`built ${TEMPLATES.length} templates into ${out}`);
}
