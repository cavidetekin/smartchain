// Form içi tablo (docs/12 "Form içi tablolar", K-175): alt başlıklı form sayfalarının içindeki küçük, tamamı yüklü listeler (ör. Parametreler'de
// Hedefler, Ufuk ve dönemler). Ortak tablonun görünümü ve hücre düzenleme standardı (K-172): düzenlenebilir hücre düz metin, başlıkta ✎; tıklamak
// seçer; çift tıklama, Enter, F2 ya da yazmaya başlamak düzenleyiciyi açar; Enter taslağa alıp alt hücreye, Tab sağdaki hücreye geçer, Esc vazgeçer;
// değişen hücre lila. Sıra veridir: satır sürüklenir; sıralama, filtre ve görünüm araçları yoktur. Kaydetmez: taslağı ekran tutar, Kaydet ve Vazgeç
// tablonun altındadır.
import { GripVertical } from "lucide-react";
import { type DragEvent, type KeyboardEvent, type ReactNode, useRef, useState } from "react";

import { tr } from "../i18n/tr";

export interface GridColumn<R> {
  key: string;
  label: string;
  /** Sayı kolonu: sağa yaslı, Inter. */
  num?: boolean;
  /** Hücrenin sınıfı (ör. satır menüsü kolonu "sc-table-rowmenu"). */
  cls?: string;
  /** rem cinsinden genişlik; verilmezse kalan alanı paylaşır. */
  width?: number;
  render(row: R, index: number): ReactNode;
  /** Düzenlenebilir kolon: düzenleyicinin metni ve taslağa yazma; options verilirse açılır liste. */
  edit?: {
    text(row: R): string;
    commit(row: R, text: string): void;
    options?: readonly string[];
    can?(row: R): boolean;
  };
  /** Metin düzenleyicisi olmadan düzenlenen kolon (ör. anahtar): başlıkta düzenleme işareti. */
  marked?: boolean;
  /** Hücrenin kapladığı kolon sayısı (bu kolondan başlayarak); kaplanan kolonların hücresi o satırda çizilmez. */
  span?(row: R): number;
  changed?(row: R): boolean;
  /** Hücredeki sorun (kırmızı çerçeve, ipucunda metin). */
  problem?(row: R, index: number): string | undefined;
}

/** Sıra hücresi: tutamak ve numara (veri kurallarındaki Sıra kolonu gibi, K-145). */
export function GridSeq({ seq, movable }: { seq: number | null; movable: boolean }) {
  return (
    <span className={`sc-seq-cell${movable ? "" : " is-locked"}`}>
      <GripVertical className="sc-seq-grip" aria-hidden="true" />
      <span className="sc-num">{seq ?? ""}</span>
    </span>
  );
}

export function EditGrid<R>({ label, columns, rows, rowKey, rowClass, editable, drag, foot }: {
  label: string;
  columns: GridColumn<R>[];
  rows: R[];
  rowKey(row: R): string;
  rowClass?(row: R): string;
  /** Düzenleme yetkisi: yoksa ✎, imleç ve sürükleme yok. */
  editable: boolean;
  /** Sürükleyerek sıralama: satır hedefin önüne ya da arkasına. */
  drag?: { can(row: R): boolean; move(id: string, target: string, side: "before" | "after"): void };
  /** Tablonun altındaki özet satırları (tfoot). */
  foot?: ReactNode;
}) {
  const [cursor, setCursor] = useState<{ row: string; col: string } | null>(null);
  const [editing, setEditing] = useState<string | null>(null);  // düzenleyicinin metni
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<{ id: string; side: "before" | "after" } | null>(null);
  const tableRef = useRef<HTMLTableElement>(null);
  const editCols = columns.filter((c) => c.edit);

  const canEdit = (col: GridColumn<R>, row: R) => editable && Boolean(col.edit) && (col.edit!.can?.(row) ?? true);
  const at = () => {
    if (!cursor) return null;
    const row = rows.find((r) => rowKey(r) === cursor.row);
    const col = columns.find((c) => c.key === cursor.col);
    return row && col ? { row, col } : null;
  };
  const open = (text?: string) => {
    const here = at();
    if (here && canEdit(here.col, here.row)) setEditing(text ?? here.col.edit!.text(here.row));
  };
  const move = (dr: number, dc: number) => {
    if (!cursor) return;
    const r = rows.findIndex((x) => rowKey(x) === cursor.row);
    const c = editCols.findIndex((x) => x.key === cursor.col);
    const nr = Math.min(Math.max(r + dr, 0), rows.length - 1);
    const nc = Math.min(Math.max(c + dc, 0), editCols.length - 1);
    if (rows[nr] && editCols[nc]) setCursor({ row: rowKey(rows[nr]), col: editCols[nc].key });
  };
  const commit = (text: string, then?: [number, number]) => {
    const here = at();
    setEditing(null);
    if (here && canEdit(here.col, here.row) && text !== here.col.edit!.text(here.row)) here.col.edit!.commit(here.row, text);
    if (then) move(then[0], then[1]);
    tableRef.current?.focus();
  };
  const onKey = (e: KeyboardEvent<HTMLTableElement>) => {
    if (editing !== null || !cursor || !editable) return;
    const arrows: Record<string, [number, number]> = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    if (arrows[e.key]) {
      e.preventDefault();
      move(...arrows[e.key]);
    } else if (e.key === "Enter" || e.key === "F2") {
      e.preventDefault();
      open();
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const here = at();
      if (here && canEdit(here.col, here.row) && !here.col.edit!.options) {  // yazmaya başlamak açar (seçenekli hücrede liste açılır)
        e.preventDefault();
        open(e.key);
      }
    }
  };
  const editorKey = (e: KeyboardEvent<HTMLInputElement | HTMLSelectElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commit(e.currentTarget.value, [1, 0]);
    } else if (e.key === "Tab") {
      e.preventDefault();
      commit(e.currentTarget.value, [0, e.shiftKey ? -1 : 1]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setEditing(null);
      tableRef.current?.focus();
    }
    e.stopPropagation();
  };

  const dragProps = (row: R) => {
    const id = rowKey(row);
    if (!drag || !editable || !drag.can(row)) return {};
    return {
      draggable: editing === null,
      onDragStart: (e: DragEvent<HTMLTableRowElement>) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", id);
        setDragging(id);
      },
      onDragOver: (e: DragEvent<HTMLTableRowElement>) => {
        if (!dragging || dragging === id) return;
        e.preventDefault();
        const box = e.currentTarget.getBoundingClientRect();
        setOver({ id, side: e.clientY < box.top + box.height / 2 ? "before" : "after" });
      },
      onDrop: (e: DragEvent<HTMLTableRowElement>) => {
        e.preventDefault();
        if (dragging && over) drag.move(dragging, over.id, over.side);
        setDragging(null);
        setOver(null);
      },
      onDragEnd: () => {
        setDragging(null);
        setOver(null);
      },
    };
  };

  return (
    <div className="sc-table-scroll sc-edit-grid-scroll">
      <table ref={tableRef} className="sc-table-grid sc-edit-grid" aria-label={label} tabIndex={editable ? 0 : undefined} onKeyDown={onKey}>
        <colgroup>
          {columns.map((c) => <col key={c.key} style={c.width ? { width: `${c.width}rem` } : undefined} />)}
        </colgroup>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={[c.num ? "is-num" : "", c.cls ?? ""].filter(Boolean).join(" ") || undefined}>
                {c.label}
                {editable && (c.edit || c.marked) && <span className="sc-table-edit-mark" title={tr.table.editableColumn} aria-label={tr.table.editableColumn}>✎</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const id = rowKey(row);
            const drop = over?.id === id ? ` is-drop-${over.side}` : "";
            let covered = 0;   // önceki hücrenin kapladığı kolonlar çizilmez
            return (
              <tr key={id} className={`sc-table-row ${rowClass?.(row) ?? ""}${drop}${dragging === id ? " is-dragging" : ""}`} {...dragProps(row)}>
                {columns.map((col) => {
                  if (covered > 0) {
                    covered -= 1;
                    return null;
                  }
                  const span = col.span?.(row) ?? 1;
                  covered = span - 1;
                  const cell = canEdit(col, row);
                  const here = cursor?.row === id && cursor.col === col.key;
                  const problem = col.problem?.(row, index);
                  const cls = [col.cls ?? "", col.num ? "is-num" : "", cell ? "is-editable" : "", here && editable ? "is-cursor" : "", col.changed?.(row) ? "is-draft" : "",
                               problem ? "is-invalid" : ""].filter(Boolean).join(" ");
                  const isOpen = here && editing !== null && cell;
                  return (
                    <td key={col.key} className={cls || undefined} title={problem} colSpan={span > 1 ? span : undefined}
                        onClick={col.edit ? () => { if (!isOpen) { setCursor({ row: id, col: col.key }); setEditing(null); } } : undefined}
                        onDoubleClick={cell ? () => { setCursor({ row: id, col: col.key }); setEditing(col.edit!.text(row)); } : undefined}>
                      {isOpen ? (
                        col.edit!.options ? (
                          <select className="sc-cell-editor" autoFocus aria-label={`${col.label} · ${index + 1}`} defaultValue={editing ?? ""}
                                  onChange={(e) => commit(e.target.value)} onBlur={(e) => commit(e.target.value)} onKeyDown={editorKey}>
                            {col.edit!.options.map((o) => <option key={o} value={o}>{o}</option>)}
                          </select>
                        ) : (
                          <input className={`sc-cell-editor${col.num ? " is-num" : ""}`} autoFocus aria-label={`${col.label} · ${index + 1}`} defaultValue={editing ?? ""}
                                 onFocus={(e) => { if (e.target.value.length > 1) e.target.select(); }}
                                 onBlur={(e) => commit(e.target.value)} onKeyDown={editorKey} />
                        )
                      ) : col.render(row, index)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
        {foot && <tfoot>{foot}</tfoot>}
      </table>
    </div>
  );
}
