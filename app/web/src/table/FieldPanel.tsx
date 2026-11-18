// Alan paneli (U-6): listenin bütün alanları aramalı onay kutusu listesinde; kapalı alanlar buradan geri açılır.
// Altında "İlişkili alanlar" (K-182): satırın bağlı olduğu kayıtlar başlık olarak; başlık açılınca o kaydın alanları yüklenir.
import { ChevronDown, ChevronRight } from "lucide-react";
import { type Ref, useEffect, useState } from "react";

import { fold } from "../format";
import { tr } from "../i18n/tr";
import { Button, Checkbox, SearchField } from "../ui";
import { relatedLimit } from "./related";
import type { ListColumn, RelatedCatalog, RelationHeading } from "./types";

const T = tr.table;
const LABEL_SEP = " · ";

type Loaded = Record<string, RelatedCatalog | "loading" | "error">;

export function FieldPanel({ ref, columns, visibility, onToggle, onReset, relations = [], order = [], loadRelated, onToggleRelated }: {
  ref?: Ref<HTMLDivElement>;
  /** Tablonun kendi alanları. */
  columns: ListColumn[];
  visibility: Record<string, boolean>;
  onToggle(field: string, on: boolean): void;
  onReset(): void;
  /** İlişkili alanların birinci seviye başlıkları (K-182); boşsa bölüm görünmez. */
  relations?: RelationHeading[];
  /** Açık alanlar (ilişkili alan sınırı ve başlıktaki sayı için). */
  order?: string[];
  loadRelated?(path: string): Promise<RelatedCatalog>;
  onToggleRelated?(column: ListColumn, on: boolean): void;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [loaded, setLoaded] = useState<Loaded>({});
  const q = fold(search.trim());
  const visibleCount = order.length || columns.filter((c) => visibility[c.field]).length;

  const load = (path: string) => {
    if (!loadRelated || loaded[path]) return;
    setLoaded((x) => ({ ...x, [path]: "loading" }));
    loadRelated(path).then((c) => setLoaded((x) => ({ ...x, [path]: c })), () => setLoaded((x) => ({ ...x, [path]: "error" })));
  };
  // Arama yazılınca birinci seviyenin alanları yüklenir; ikinci seviye başlığı açılınca aranır
  useEffect(() => {
    if (q) relations.forEach((r) => load(r.path));
  }, [q, relations]);

  const toggleOpen = (path: string) => {
    load(path);
    setOpen((s) => {
      const next = new Set(s);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });
  };

  /** Bu başlığın (ve yüklenmiş alt başlıklarının) aramaya uyan alanı var mı? */
  const matches = (path: string): boolean => {
    const c = loaded[path];
    if (!c || typeof c === "string") return false;
    return c.fields.some((f) => fold(f.label).includes(q)) || c.relations.some((r) => matches(r.path));
  };

  const group = (h: RelationHeading, parentLabel: string | null) => {
    const c = loaded[h.path];
    if (q && !matches(h.path)) return null;
    const isOpen = q ? true : open.has(h.path);
    const selected = order.filter((f) => f.startsWith(`${h.path}/`)).length;
    const title = parentLabel ? h.label.replace(parentLabel + LABEL_SEP, `${parentLabel} › `) : h.label;
    return (
      <div key={h.path} className="sc-table-rel">
        <button type="button" className="sc-table-rel-head" aria-expanded={isOpen} onClick={() => toggleOpen(h.path)} title={title}>
          {isOpen ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
          <span>{title}</span>
          {selected > 0 && <span className="sc-num sc-muted">{selected}</span>}
        </button>
        {isOpen && (
          <div className="sc-table-rel-body">
            {c === "loading" && <p className="sc-muted">{T.loading}</p>}
            {c === "error" && <p className="sc-muted">{T.relatedError}</p>}
            {c && typeof c !== "string" && c.fields.filter((f) => !q || fold(f.label).includes(q)).map((f) => {
              const on = order.includes(f.field);
              const limit = on ? null : relatedLimit(order, f.field);
              const last = on && visibleCount === 1;
              const reason = last ? T.lastField : limit === "fields" ? T.relatedLimitFields : limit === "joins" ? T.relatedLimitJoins : null;
              const short = f.label.startsWith(c.label + LABEL_SEP) ? f.label.slice(c.label.length + LABEL_SEP.length) : f.label;
              return (
                <div key={f.field} className="sc-table-pop-option" title={reason ? `${f.label} · ${reason}` : f.label}>
                  <Checkbox label={short} checked={on} disabled={Boolean(reason)} onChange={(v) => onToggleRelated?.(f, v)} />
                </div>
              );
            })}
            {c && typeof c !== "string" && c.relations.map((r) => group(r, c.label))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div ref={ref} className="sc-table-pop sc-table-fields sc-floating" role="dialog" aria-label={T.fields(visibleCount, columns.length)}>
      <SearchField label={T.fieldSearch} value={search} onChange={setSearch} />
      <div className="sc-table-pop-list">
        {columns.filter((c) => !q || fold(c.label).includes(q)).map((c) => {
          const on = Boolean(visibility[c.field]);
          const last = on && visibleCount === 1;
          return (
            <div key={c.field} className="sc-table-pop-option" title={last ? `${c.label} · ${T.lastField}` : c.label}>
              <Checkbox label={c.label} checked={on} disabled={last} onChange={(v) => onToggle(c.field, v)} />
            </div>
          );
        })}
        {relations.length > 0 && (
          <div className="sc-table-rels" role="group" aria-label={T.relatedFields}>
            <p className="sc-table-rels-title">{T.relatedFields}</p>
            {relations.map((r) => group(r, null))}
          </div>
        )}
      </div>
      <div className="sc-table-pop-actions">
        <Button size="sm" variant="ghost" onClick={onReset}>{T.resetFields}</Button>
      </div>
    </div>
  );
}
