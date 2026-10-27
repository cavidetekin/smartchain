// Vite yapılandırması (K-83). Geliştirmede /api ve /api/ws 127.0.0.1:8000'deki API'ye yönlenir.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } },
  },
  build: { outDir: "dist", assetsDir: "assets", sourcemap: false },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    env: { TZ: "Europe/Istanbul" },
  },
});
