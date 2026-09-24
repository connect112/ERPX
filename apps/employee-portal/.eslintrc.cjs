/** ESLint config for the ERPX web app (Vite + React + TypeScript). */
module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
    // Accessibility (WCAG 2.1 AA) baseline — Production Hardening Audit
    // finding, Phase 1: establish tooling only, no component fixes yet.
    // CI's frontend job (.github/workflows/ci.yml) runs `npm run build`
    // and `npm run test --if-present`, never `npm run lint` — so turning
    // this on for real (not silenced) surfaces the true current violation
    // count without risking any CI regression. See
    // docs/project-hardening-audit.md for the baseline and remediation
    // plan; fixing the violations this reports is explicitly out of
    // scope for this change (Phase 2+).
    "plugin:jsx-a11y/recommended",
  ],
  ignorePatterns: ["dist", "node_modules", "**/*.d.ts", ".eslintrc.cjs"],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  plugins: ["@typescript-eslint", "react-refresh", "jsx-a11y"],
  settings: {
    "jsx-a11y": {
      // Radix UI / shadcn-style primitives (components/ui/*) forward
      // arbitrary props onto real DOM elements via Radix's Slot pattern —
      // this tells jsx-a11y's rules to still check attributes/roles on
      // components named like our own wrappers, not just raw <div>/<button>.
      components: {
        Button: "button",
        Input: "input",
        Textarea: "textarea",
        Select: "select",
        Label: "label",
        Table: "table",
      },
    },
  },
  rules: {
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    "no-unused-vars": "off",
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "warn",
    "no-empty": ["error", { allowEmptyCatch: true }],
  },
};
