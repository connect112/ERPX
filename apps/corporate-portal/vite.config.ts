import path from "node:path";
import react from "@vitejs/plugin-react";
// vitest/config re-exports vite's defineConfig with its types extended to
// recognize the `test` key below — plain "vite"'s defineConfig doesn't know
// about it and fails typecheck (`tsc -b`) even though it works at runtime.
// Same fix already applied to apps/web, apps/student-portal, and
// apps/trainer-portal's vite.config.ts.
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5176,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split all third-party code into a single, deterministic `vendor`
        // chunk. It changes far less often than app code, so browsers can
        // cache it across deploys; keeping it as ONE chunk (rather than
        // per-package) avoids request waterfalls / high fragmentation.
        // Per-route app code is already split via React.lazy in the router.
        manualChunks(id) {
          if (id.includes("node_modules")) {
            return "vendor";
          }
        },
      },
    },
  },
  test: {
    // Scoped to where real unit tests actually live — see
    // apps/web/vite.config.ts for the identical rationale.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    passWithNoTests: true,
  },
});
