import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "."), "server-only": path.resolve(__dirname, "tests/helpers/empty.ts") } },
  test: {
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    // Node by default; component tests (.tsx) opt in with a `// @vitest-environment jsdom` docblock
    // (vitest 4+ removed environmentMatchGlobs).
    environment: "node",
    setupFiles: ["./vitest.setup.ts"],
    testTimeout: 20_000,
  },
});
