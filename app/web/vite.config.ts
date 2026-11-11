// Vite yapılandırması (K-83). Geliştirmede /api ve /api/ws 127.0.0.1:8000'deki API'ye yönlenir.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } },
    // Renk değerleri app/shared/design-tokens.json'dan okunur (K-92, K-96; tokens.css'ten üretilir).
    fs: { allow: [".", "../shared"] },
  },
  build: { outDir: "dist", assetsDir: "assets", sourcemap: false },
  test: {
    environment: "jsdom",
    // Tam koşuda dosyalar paralel çalışır (pytest içinden de); yük altında jsdom testleri 5 sn'yi aşabilir (docs/08).
    testTimeout: 15_000,
    // Mantıksal çekirdeklerin yarısı (K-164): bütün çekirdeklerle yük altında ilk ekran açılışları zaman aşımına düşüyordu; yarısıyla hem
    // yük altında geçer hem tek başına daha hızlıdır (docs/08 Testler).
    maxWorkers: "50%",
    setupFiles: ["src/test/setup.ts"],
    env: { TZ: "Europe/Istanbul" },
  },
});
