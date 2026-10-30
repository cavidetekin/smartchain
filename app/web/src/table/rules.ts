// Koşullu biçim kuralları (U-24, K-95): saf işlevler. Kurallar sunucuda değerlendirilir; satır, tutan kuralların
// istekteki sırasını (_rules) taşır. Burada: operatör kümeleri, özet metni, istekteki kurallar, hücre biçiminin
// birleşmesi (aynı özellikte üstteki kural kazanır), çakışma ve sıra.
import { formatDate } from "../format";
import { tr } from "../i18n/tr";
import { suggestText } from "../ui/contrast";
import { DEFAULT_TEXT, tokenColor } from "../ui/palette";
import { describeFilter } from "./filters";
import type { FormatRule, ListColumn, ListFilter, Row, RuleFormat, RuleIcon, RuleOp, RuleSpec } from "./types";

export type RuleKind = "number" | "date" | "text" | "bool";

export function ruleKind(col: ListColumn): RuleKind {
  if (col.type === "number" || col.type === "integer") return "number";
  if (col.type === "date" || col.type === "datetime") return "date";
  return col.type === "bool" ? "bool" : "text";
}

/** Kolon tipine göre koşullar (docs/08); liste filtreli metin alanı da metindir (U-24). Her tipte en sonda "Her zaman":
 *  koşulsuz kolon biçimi, bütün hücrelerde (boşlar dahil) tutar. */
export const RULE_OPS: Record<RuleKind, RuleOp[]> = {
  number: ["gt", "lt", "between", "eq", "empty", "always"],
  date: ["gt", "lt", "between", "eq", "relative", "empty", "always"],
  text: ["equals", "contains", "starts_with", "in", "empty", "always"],
  bool: ["in", "empty", "always"],
};
export const FIELD_REF_OPS: RuleOp[] = ["gt", "lt", "eq"];

export const canUseFieldRef = (col: ListColumn, op: RuleOp) =>
  FIELD_REF_OPS.includes(op) && (ruleKind(col) === "number" || ruleKind(col) === "date");

/** Karşılaştırılabilecek alanlar: aynı tipte, kendisi hariç; gizliler dahil. */
export function refCandidates(col: ListColumn, columns: ListColumn[]): ListColumn[] {
  return columns.filter((c) => c.field !== col.field && ruleKind(c) === ruleKind(col));
}

const SYMBOL: Partial<Record<RuleOp, string>> = { gt: ">", lt: "<", eq: "=" };

/** Koşulun özeti: filtre etiketiyle aynı dil; alan karşılaştırmasında "< Güvenlik stoğu". */
export function describeCondition(rule: RuleSpec, byField: Map<string, ListColumn>): string {
  const col = byField.get(rule.field);
  const c = rule.condition;
  if (!col) return "";
  if (c.op === "always") return tr.table.ruleColumnFormat;
  if (c.field_ref) return `${SYMBOL[c.op]} ${byField.get(c.field_ref)?.label ?? c.field_ref}`;
  if (SYMBOL[c.op] && ruleKind(col) === "date" && typeof c.value === "string") {
    const [y, m, d] = c.value.split("-").map(Number);
    return `${SYMBOL[c.op]} ${formatDate(new Date(y, m - 1, d))}`;
  }
  return describeFilter({ field: rule.field, ...c } as ListFilter, col);
}

export function describeRule(rule: RuleSpec, byField: Map<string, ListColumn>): string {
  return `${byField.get(rule.field)?.label ?? rule.field} ${describeCondition(rule, byField)}`;
}

/** Ekrana uygulanan kurallar: aktif, alanı görünen, karşılaştırılan alanı listede olan (sıra korunur). */
export function activeRules(rules: FormatRule[], visible: string[], known: Set<string>): FormatRule[] {
  return rules.filter((r) => r.enabled && visible.includes(r.field) && known.has(r.field)
    && (!r.condition.field_ref || known.has(r.condition.field_ref)));
}

export const toSpec = (r: FormatRule): RuleSpec => ({ field: r.field, condition: r.condition });
export const toRequestRule = (r: FormatRule) => ({ id: r.id, field: r.field, condition: r.condition });

const PROPS: (keyof RuleFormat)[] = ["fill", "color", "bold", "icon", "icon_color"];

/**
 * Hücrenin biçimi: o alanın tutan kuralları güncel sırayla; her özellikte ilk (üstteki) dolu olan kazanır (K-95).
 * Satır tutan kuralların kimliklerini taşır (_ruleIds); silinen kural hemen düşer, sıra değişikliği hemen geçerlidir.
 */
export function cellFormat(active: FormatRule[], row: Row | undefined, field: string):
  { format: RuleFormat; rules: FormatRule[] } | null {
  const hits = row?._ruleIds as string[] | undefined;
  if (!hits?.length) return null;
  const format: RuleFormat = {};
  const matched: FormatRule[] = [];
  for (const r of active) {
    if (r.field !== field || !hits.includes(r.id)) continue;
    matched.push(r);
    for (const p of PROPS) {
      if (format[p] === undefined && r.format[p] !== undefined && r.format[p] !== false) {
        (format as Record<string, unknown>)[p] = r.format[p];
      }
    }
  }
  return matched.length ? { format, rules: matched } : null;
}

/** Kuralı yukarı (-1) ya da aşağı (+1) taşır. */
export function moveRule(rules: FormatRule[], id: string, delta: number): FormatRule[] {
  const i = rules.findIndex((r) => r.id === id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= rules.length) return rules;
  const next = [...rules];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

/** Sürükle-bırak: kuralı hedefin önüne ya da arkasına koyar. */
export function dropRule(rules: FormatRule[], id: string, target: string, side: "before" | "after"): FormatRule[] {
  if (id === target) return rules;
  const moving = rules.find((r) => r.id === id);
  if (!moving) return rules;
  const rest = rules.filter((r) => r.id !== id);
  const at = rest.findIndex((r) => r.id === target) + (side === "after" ? 1 : 0);
  return [...rest.slice(0, at), moving, ...rest.slice(at)];
}

/** Görünümde tekil kural kimliği. */
export function newRuleId(rules: FormatRule[]): string {
  const n = Math.max(0, ...rules.map((r) => Number(/^k(\d+)$/.exec(r.id)?.[1] ?? 0)));
  return `k${n + 1}`;
}

/** İkonun varsayılan rengi (K-96): uyarı hardal, çarpı kiremit, onay yeşil, oklar ve nokta indigo, bayrak ve yıldız petrol. */
export const ICON_DEFAULT_TOKEN: Record<RuleIcon, string> = {
  warning: "status-risk", cross: "status-over", check: "status-ok", arrow_up: "indigo-500", arrow_down: "indigo-500",
  dot: "indigo-500", flag: "chart-2", star: "chart-2",
};

export const iconColor = (format: RuleFormat) =>
  format.icon_color ?? (format.icon ? tokenColor(ICON_DEFAULT_TOKEN[format.icon]) : undefined);

const readableCache = new Map<string, string>();

/** Yazı rengi: seçilmişse o; seçilmemiş ve zemin varsa zemine göre okunur renk (K-96; Excel'de aynı hesap). */
export function textColor(format: RuleFormat): string | undefined {
  if (format.color || !format.fill) return format.color;
  let c = readableCache.get(format.fill);
  if (!c) {
    c = suggestText(format.fill, DEFAULT_TEXT);
    readableCache.set(format.fill, c);
  }
  return c;
}

/** Biçimin satır içi stili (hücre, önizleme ve liste örneği aynı yerden). */
export function formatStyle(format: RuleFormat): { backgroundColor?: string; color?: string; fontWeight?: string } {
  const color = textColor(format);
  return {
    ...(format.fill ? { backgroundColor: format.fill } : {}),
    ...(color ? { color } : {}),
    ...(format.bold ? { fontWeight: "var(--fw-semibold)" } : {}),
  };
}
