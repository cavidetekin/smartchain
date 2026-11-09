// Pencere tablosu (K-132, docs/12): ortak tablonun görünümü (renkli başlık, tek satır, sıralama), satırlar pencerenin verisinden gelir.
// Önizleme, Veri çek, Çekim sonucu, Bağlantı testi. Sunucu listesi olan yerde DataTable kullanılır.
import { ArrowDown, ArrowUp } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";

export interface LocalColumn<R> {
  key: string;
  label: string;
  numeric?: boolean;
  /** Uzun metin (Not, Neden, Sorun): gerektiğinde alt satıra kayar; tek satır kuralının istisnası (docs/12). */
  wrap?: boolean;
  /** Sıralama değeri; verilmezse value ya da hücre sıralanmaz. */
  value?(row: R): string | number | null;
  render?(row: R): ReactNode;
  /** Başlıkta etiketle birlikte gösterilen öğe (ör. toplu seçim kutusu, K-145). */
  header?: ReactNode;
}

export function LocalTable<R>({ label, columns, rows, rowKey }: {
  label: string;
  columns: LocalColumn<R>[];
  rows: R[];
  rowKey(row: R): string;
}) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);

  const shown = useMemo(() => {
    const col = sort && columns.find((c) => c.key === sort.key);
    if (!col?.value) return rows;
    const read = col.value;
    return [...rows].sort((a, b) => {
      const [x, y] = [read(a), read(b)];
      if (x === y) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "tr");
      return order * sort!.dir;
    });
  }, [rows, columns, sort]);

  const toggle = (key: string) => setSort((s) => (s?.key !== key ? { key, dir: 1 } : s.dir === 1 ? { key, dir: -1 } : null));

  return (
    <div className="sc-local-table-wrap">
      <table className="sc-table-grid sc-local-table" aria-label={label}>
        <thead>
          <tr>
            {columns.map((c) => {
              const dir = sort?.key === c.key ? sort.dir : 0;
              return (
                <th key={c.key} scope="col" className={c.numeric ? "is-num" : undefined} aria-sort={dir === 1 ? "ascending" : dir === -1 ? "descending" : undefined}>
                  <div className="sc-table-head">
                    {c.value ? (
                      <button type="button" className="sc-table-sort" onClick={() => toggle(c.key)}>
                        <span className="sc-table-label">{c.label}</span>
                        {dir === 1 && <ArrowUp aria-hidden="true" />}
                        {dir === -1 && <ArrowDown aria-hidden="true" />}
                      </button>
                    ) : <span className="sc-table-sort sc-table-label">{c.header}{c.label}</span>}
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {shown.map((row) => (
            <tr key={rowKey(row)} className="sc-table-row">
              {columns.map((c) => {
                const value = c.value?.(row);
                const name = c.numeric ? "is-num sc-num" : c.wrap ? "is-wrap" : undefined;
                return <td key={c.key} className={name}>{c.render ? c.render(row) : value ?? ""}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
