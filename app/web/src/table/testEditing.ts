// Hücre düzenleme standardı (K-172) için test yardımcıları: satır metni ve kolon başlığıyla hücre, çift tıklayıp değer girme ve Enter.
import { screen } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";

type User = ReturnType<typeof userEvent.setup>;

/** Satırı içindeki bir metinle, kolonu başlığıyla bulunan hücre (seçim ve satır menüsü kolonları başlıkla aynı sırada). */
export function cellOf(rowText: string, header: string): HTMLElement {
  const headers = screen.getAllByRole("columnheader");
  const index = headers.findIndex((h) => h.querySelector(".sc-table-label")?.textContent === header);
  if (index < 0) throw new Error(`kolon yok: ${header}`);
  const row = screen.getAllByText(rowText, { exact: true }).map((el) => el.closest("tr")).find((tr) => tr?.classList.contains("sc-table-row"));
  if (!row) throw new Error(`satır yok: ${rowText}`);
  return row.children[index] as HTMLElement;
}

/** Çift tıklayıp düzenleyiciyi açar. */
export async function openEditor(user: User, cell: HTMLElement): Promise<HTMLInputElement | HTMLSelectElement> {
  await user.dblClick(cell);
  const editor = cell.querySelector<HTMLInputElement | HTMLSelectElement>(".sc-cell-editor");
  if (!editor) throw new Error("düzenleyici açılmadı");
  return editor;
}

/** Hücreye değer girer ve Enter ile taslağa alır. */
export async function setCell(user: User, rowText: string, header: string, value: string): Promise<void> {
  const editor = await openEditor(user, cellOf(rowText, header));
  if (editor instanceof HTMLSelectElement) await user.selectOptions(editor, value);
  else {
    await user.clear(editor);
    if (value) await user.type(editor, value);
  }
  await user.keyboard("{Enter}");
}
