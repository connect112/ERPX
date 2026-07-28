import path from "node:path";
import react from "@vitejs/plugin-react";
// vitest/config re-exports vite's defineConfig with its types extended to
// recognize the `test` key below — plain "vite"'s defineConfig doesn't know
// about it and fails typecheck (`tsc -b`) even though it works at runtime.
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    // Without an explicit `include`, vitest's default glob also matches
    // e2e/*.spec.ts — Playwright specs, which use Playwright's own test()
    // API and error immediately under vitest's runner. Scoped to where
    // real unit tests will actually live once written (none exist yet —
    // see docs/project-hardening-audit.md finding #8) — e2e coverage stays
    // exclusively Playwright's job via `npm run test:e2e`.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    passWithNoTests: true,
  },
});
