// Hücre düzenleme standardı (K-172, docs/12 "Hücre düzenleme"): düzenlenebilir hücre düz metin görünür; kolon başlığında ✎, hücrenin üzerine
// gelince ince çerçeve. Tıklamak seçer; çift tıklama, Enter, F2 ya da yazmaya başlamak düzenleyiciyi açar (hücreyi kaplar). Enter ya da Tab
// taslağa alır ve sonraki hücreye geçer, Esc vazgeçer; ok tuşlarıyla gezilir. Değişen hücre lila zeminlidir. Taslak useTableEdits'te tutulur,
// Kaydet toplu yazar (K-132).
import type { ReactNode } from "react";

import type { ListColumn, Row } from "./types";

export interface EditorSpec {
  kind: "text" | "select";
  /** Düzenleyici açıldığındaki metin (taslak ya da kayıtlı değer). */
  text: string;
  options?: readonly string[];
  placeholder?: string;
}

/** Yapıştırılan blokta bir hücre: hedef satır ve kolon (tablonun dışına taşıyorsa undefined) ve metin. */
export interface PasteCell {
  row: Row | undefined;
  col: ListColumn | undefined;
  text: string;
}

export interface CellEditing {
  /** Kolon başlığında ✎ (yalnız düzenleme yetkisi varsa; hiçbir kolon düzenlenemiyorsa hücre imleci de yok, K-172). */
  editableColumn(col: ListColumn): boolean;
  canEdit(col: ListColumn, row: Row): boolean;
  editor(col: ListColumn, row: Row): EditorSpec;
  /** Düzenleyicinin metni taslağa (Enter, Tab, odak kaybı). */
  commit(col: ListColumn, row: Row, text: string): void;
  /** Ekran okuyucu için düzenleyicinin adı. */
  label(col: ListColumn, row: Row): string;
  /** Seçili hücrede Delete (ör. manuel değeri kaldırma taslağı); işlendiyse true. */
  clear?(col: ListColumn, row: Row): boolean;
  /** Hücre menüsü (sağ tık, hücrenin tamamında; K-172): açıldıysa true (tarayıcının menüsü çıkmaz, hücre seçilir). */
  menu?(col: ListColumn, row: Row, anchor: HTMLElement): boolean;
  /** Seçili hücreden başlayarak yapıştırılan blok (sekme ve satır ayraçlı; Excel). */
  paste?(cells: PasteCell[]): void;
}

/** Panodaki metin satır ve hücrelere: sekme ayraçlı, son boş satır atılır. */
export function parseClipboard(text: string): string[][] {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
  return lines.map((line) => line.split("\t"));
}

interface Drafts {
  get<T>(key: string, field: string, saved: T): T;
  changed(key: string, field: string): boolean;
  set(key: string, field: string, value: unknown, saved: unknown): void;
}

/** Basit ekranlar (ör. Veri yükleme'deki Yöntem): seçenekli ya da metin kolonları. Taslak gösterimi ve lila zemin de buradan. */
export function draftEditing(edits: Drafts, keyOf: (row: Row) => string, fields: Record<string, {
  label(row: Row): string;
  editable(row: Row): boolean;
  options?: readonly string[];
  placeholder?: string;
}>): { editing: CellEditing; cellRender: Record<string, (value: unknown, row: Row) => ReactNode>; changed(field: string, row: Row): boolean } {
  const saved = (row: Row, field: string) => (row[field] === null || row[field] === undefined ? "" : String(row[field]));
  return {
    editing: {
      editableColumn: (col) => col.field in fields,  // yetkisiz kullanıcıda ekran alanı vermez (✎ yok)
      canEdit: (col, row) => Boolean(fields[col.field]?.editable(row)),
      editor: (col, row) => {
        const f = fields[col.field];
        return { kind: f.options ? "select" : "text", text: edits.get(keyOf(row), col.field, saved(row, col.field)), options: f.options, placeholder: f.placeholder };
      },
      commit: (col, row, text) => edits.set(keyOf(row), col.field, text, saved(row, col.field)),
      label: (col, row) => fields[col.field].label(row),
    },
    cellRender: Object.fromEntries(Object.keys(fields).map((field) => [field, (_value: unknown, row: Row) => edits.get(keyOf(row), field, saved(row, field))])),
    changed: (field, row) => edits.changed(keyOf(row), field),
  };
}
