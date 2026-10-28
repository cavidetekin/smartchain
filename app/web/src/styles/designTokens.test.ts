// Biçim tanımı tek kaynak (K-92): Excel yazıcısının okuduğu design-tokens.json, tokens.css'ten üretilmiş hâliyle aynı.
// Fark varsa: npm run tokens (build öncesi kendiliğinden çalışır).
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { parseTokens, renderTokens } from "../../scripts/tokens.mjs";

// Yol çözülerek okunur: Vite, kök dışındaki new URL(…, import.meta.url) adreslerini sunucu adresine çevirir.
const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, "tokens.css"), "utf-8");
const json = readFileSync(resolve(here, "../../../shared/design-tokens.json"), "utf-8");

describe("design-tokens.json (K-92)", () => {
  it("tokens.css ile aynı", () => {
    expect(json).toBe(renderTokens(css));
  });

  it("Excel'in kullandığı renkler var ve çözülmüş", () => {
    const colors = parseTokens(css);
    for (const name of ["table-head-bg", "table-head-text", "table-group-1-bg", "table-group-2-bg", "text",
                        "occ-over-bg", "occ-over-text"]) {
      expect(colors[name]).toMatch(/^#[0-9a-f]{6}$/);
    }
    expect(colors["table-group-1-bg"]).toBe("#eceef7");
  });
});
