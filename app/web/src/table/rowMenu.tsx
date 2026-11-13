// Satır sonundaki ⋯ menüsü (K-171): ekranın satır işlemleri; sağ tıkta hücre seçenekleri (Kopyala, Manuel değeri kaldır) başta, ayraçla.
// Basit ekranlar için: işlemler bir listeyle verilir, menü burada çizilir.
import { useMemo, useRef, useState } from "react";

import { type MenuAction, MenuActions, MenuItem, RowPopMenu } from "../ui/PopMenu";
import type { RowMenuSpec } from "./DataTable";
import type { Row } from "./types";

export function useRowMenu(label: (row: Row) => string, actions: (row: Row) => MenuAction[]) {
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement; extra?: MenuAction[] } | null>(null);
  const labelRef = useRef(label);
  labelRef.current = label;
  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => labelRef.current(row),
    onOpen: (row: Row, anchor: HTMLElement, extra?: MenuAction[]) => setMenu({ row, anchor, extra }),
  }), []);
  const close = () => setMenu(null);
  const element = menu ? (
    <RowPopMenu label={label(menu.row)} anchor={menu.anchor} onClose={close}>
      <MenuActions items={menu.extra} onDone={close} />
      {actions(menu.row).map((a) => (
        <MenuItem key={a.label} label={a.label} state={a.state ?? { allowed: true }} onClick={() => { close(); a.onClick?.(); }} />
      ))}
    </RowPopMenu>
  ) : null;
  return { rowMenu, element };
}
