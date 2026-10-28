# Approved React Email templates

React Email components that developers (or coding agents) write, review and merge like any other code. They appear in
**Email Studio → Create Email → Approved React Email templates**. Administrators change a template's *settings* (the
properties it declares), never its code, and nothing is ever uploaded or executed on the server.

## How it works

1. A template is one file in `src/templates/` that exports `meta` (its name, category, the ERPX email it is written for,
   and its settings) and a default React Email component.
2. `npm run build` renders every template to plain HTML in `../../modules/email_studio/code_templates/` (plus
   `manifest.json`). **Commit the generated files**: the API only reads them, so it needs no Node.
3. In the HTML, every setting is a `{{prop:name}}` token and every ERPX value is an ordinary `{{placeholder}}`. The API
   fills the settings from what the administrator chose (escaped for where they land), then the placeholders from the
   email being sent.

## Adding a template

1. Copy a file in `src/templates/` and change `meta` and the component.
   - Use `p("setting")` for a setting and `v("student_name")` for an ERPX placeholder (`src/layout.tsx`).
   - Keep every `required` setting in the markup, and keep the link the ERPX email needs (for example
     `v("verification_url")` for `verification`).
   - `{{signature}}`, `{{brand_header}}` and `{{brand_footer}}` place the chosen signature and brand blocks; use each once.
   - Include `COMMON_PROPS` so the template follows the chosen brand's colours.
2. Register it in `scripts/build.tsx`.
3. `npm run build`, commit the generated files with your source.
4. `cd ../.. && python -m pytest tests/unit/test_email_studio.py` checks that every template is complete, uses only
   what the ERPX email it targets supplies, and contains no script.

## Commands

```bash
npm install
npm run build       # regenerate modules/email_studio/code_templates/
npm run check       # fail if the generated files are out of date
npm run typecheck
```

## Rules

- Email-safe markup only (tables and inline styles, which React Email produces). No scripts, no remote CSS or fonts.
- Do not put personal data or real links in defaults. Use placeholders.
- Do not add a placeholder the target ERPX email does not supply: the unit test fails, and the email could not be assigned.
