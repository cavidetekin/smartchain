// Kullanıcı menüsü: geçici kullanıcı (A-36), yazı boyutu (U-23), çıkış (2.1).
import { CircleUser } from "lucide-react";
import { useState } from "react";

import { tr } from "../i18n/tr";
import { FONT_SIZES, type FontSize } from "../prefs";
import { Segment } from "../ui";

interface Props {
  userId: number;
  fontSize: FontSize;
  onFontSize(size: FontSize): void;
}

export function UserMenu({ userId, fontSize, onFontSize }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sc-user">
      <button type="button" className="sc-chip sc-chip-btn" aria-haspopup="dialog" aria-expanded={open}
              onClick={() => setOpen(!open)}>
        <CircleUser aria-hidden="true" />
        <span>{tr.user.label(userId)}</span>
      </button>
      {open && (
        <div className="sc-popover sc-popover-right" role="dialog" aria-label={tr.user.label(userId)}>
          <p className="sc-muted">{tr.user.temporary}</p>
          <div className="sc-popover-title">{tr.user.fontSize}</div>
          <Segment label={tr.user.fontSize} value={fontSize} onChange={onFontSize}
                   options={FONT_SIZES.map((size) => ({
                     value: size, label: <>{tr.user.fontSizes[size]} <span className="sc-mono">{size}</span></>,
                   }))} />
          <button type="button" className="sc-menu-btn" disabled title={tr.user.logoutLater}>
            {tr.user.logout}
          </button>
        </div>
      )}
    </div>
  );
}
