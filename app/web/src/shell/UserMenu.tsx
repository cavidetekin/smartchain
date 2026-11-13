// Kullanıcı menüsü (fonksiyon 89; docs/12): ad ve rol, yazı boyutu (U-23), "Şifre değiştir", "Çıkış"; altta küçük satırda sürüm (K-172).
import { CircleUser } from "lucide-react";
import { useEffect, useState } from "react";

import { appVersion } from "../auth/authApi";
import { useAuth } from "../auth/AuthContext";
import { PasswordDialog } from "../auth/PasswordDialog";
import { tr } from "../i18n/tr";
import { FONT_SIZES, type FontSize } from "../prefs";
import { Segment } from "../ui";

interface Props {
  fontSize: FontSize;
  onFontSize(size: FontSize): void;
}

export function UserMenu({ fontSize, onFontSize }: Props) {
  const { me, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [changing, setChanging] = useState(false);
  const [changed, setChanged] = useState(false);
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    if (!changed) return;
    const t = setTimeout(() => setChanged(false), 5000);
    return () => clearTimeout(t);
  }, [changed]);

  useEffect(() => {  // menü ilk açılınca bir kez
    if (open && version === null) void appVersion().then((v) => setVersion(v ?? ""));
  }, [open, version]);

  if (!me) return null;
  const name = me.full_name || me.user_name;
  return (
    <div className="sc-user">
      {changed && <span className="sc-user-note" role="status">{tr.user.passwordChanged}</span>}
      <button type="button" className="sc-chip sc-chip-btn" aria-haspopup="dialog" aria-expanded={open}
              aria-label={`${tr.user.menu}: ${name}`} onClick={() => setOpen(!open)}>
        <CircleUser aria-hidden="true" />
        <span>{name}</span>
      </button>
      {open && (
        <div className="sc-popover sc-popover-right" role="dialog" aria-label={tr.user.menu}>
          <div className="sc-user-who">
            <strong>{name}</strong>
            <span className="sc-muted">{me.user_name} · {me.role}</span>
          </div>
          <div className="sc-popover-title">{tr.user.fontSize}</div>
          <Segment label={tr.user.fontSize} hideLabel value={fontSize} onChange={onFontSize}
                   options={FONT_SIZES.map((size) => ({
                     value: size, label: <>{tr.user.fontSizes[size]} <span className="sc-num">{size}</span></>,
                   }))} />
          <button type="button" className="sc-menu-btn" onClick={() => { setOpen(false); setChanging(true); }}>
            {tr.user.changePassword}
          </button>
          <button type="button" className="sc-menu-btn" onClick={() => void signOut("logout")}>
            {tr.user.logout}
          </button>
          {version && <div className="sc-user-version sc-num">{tr.user.version(version)}</div>}
        </div>
      )}
      {changing && (
        <PasswordDialog me={me} onCancel={() => setChanging(false)}
                        onDone={() => { setChanging(false); setChanged(true); }} />
      )}
    </div>
  );
}
