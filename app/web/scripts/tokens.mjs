// Renk değişkenleri tek kaynak (K-85, K-92): tokens.css → app/shared/design-tokens.json.
// Excel yazıcısı (sunucu) renkleri bu dosyadan okur. `npm run build` öncesi otomatik çalışır (prebuild); eşitlik testte.
import { readFileSync, writeFileSync } from "node:fs";

const SRC = new URL("../src/styles/tokens.css", import.meta.url);
const OUT = new URL("../../shared/design-tokens.json", import.meta.url);

/** :root içindeki renk değişkenleri; var(--x) çözülür, yalnız #rrggbb değerler kalır (adına göre sıralı). */
export function parseTokens(css) {
  const root = css.match(/:root\s*\{([\s\S]*?)\n\}/);
  if (!root) throw new Error("tokens.css: :root bloğu yok");
  const raw = {};
  for (const m of root[1].replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/--([\w-]+):\s*([^;]+);/g)) raw[m[1]] = m[2].trim();
  const resolve = (v, seen = new Set()) => {
    const ref = v.match(/^var\(--([\w-]+)\)$/);
    if (!ref || seen.has(ref[1]) || !(ref[1] in raw)) return v;
    seen.add(ref[1]);
    return resolve(raw[ref[1]], seen);
  };
  const out = {};
  for (const name of Object.keys(raw).sort()) {
    const v = resolve(raw[name]).toLowerCase();
    if (/^#[0-9a-f]{6}$/.test(v)) out[name] = v;
  }
  return out;
}

export function renderTokens(css) {
  return JSON.stringify({ source: "app/web/src/styles/tokens.css", colors: parseTokens(css) }, null, 2) + "\n";
}

if (process.argv[1]?.endsWith("tokens.mjs")) {  // doğrudan çalıştırılınca yazar; testte yalnız içe aktarılır
  writeFileSync(OUT, renderTokens(readFileSync(SRC, "utf-8")));
  console.log("design-tokens.json yazıldı");
}
