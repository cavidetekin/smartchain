// Kullanıcılar (ekran 22, fonksiyon 88; K-101, docs/12): ortak tablo, satırın "⋯" menüsü ve pencereler. Menü açılınca
// kayıt sunucudan okunur; öğelerin izni ve nedeni sunucudan gelir, koruma kuralları tek yerdedir (services/users.py).
import { type ReactNode, useEffect, useId, useMemo, useRef, useState } from "react";

import { ApiError, emitNotice } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { tr } from "../i18n/tr";
import { DataTable } from "../table/DataTable";
import type { Row } from "../table/types";
import { Alert, Badge, type BadgeTone, Button } from "../ui";
import { useFloating } from "../ui/popover";
import { PermissionMatrixDialog } from "./PermissionMatrixDialog";
import { ActionDialog, AddUserDialog, nameOf, NameDialog, RoleDialog, TemporaryPasswordDialog } from "./UserDialogs";
import { type ActionState, type TemporaryPassword, type UserAction, type UserDetail, usersApi } from "./usersApi";

const T = tr.users;

const STATUS_TONE: Record<string, BadgeTone> = { Aktif: "ok", Kilitli: "critical", "İlk giriş bekliyor": "risk", Pasif: "neutral" };

const CELLS = {
  Status: (value: unknown): ReactNode => (value ? <Badge tone={STATUS_TONE[String(value)] ?? "neutral"}>{String(value)}</Badge> : null),
};

function MenuItem({ label, state, onClick }: { label: string; state: ActionState; onClick(): void }) {
  const reasonId = useId();
  return (
    <>
      <button type="button" role="menuitem" className="sc-popmenu-item" disabled={!state.allowed}
              title={state.reason ?? undefined} aria-describedby={state.reason ? reasonId : undefined} onClick={onClick}>
        {label}
      </button>
      {state.reason && <span id={reasonId} className="sc-visually-hidden">{state.reason}</span>}
    </>
  );
}

function RowMenu({ row, anchor, onClose, onPick }: {
  row: Row; anchor: HTMLElement; onClose(): void; onPick(action: UserAction, detail: UserDetail): void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useFloating(ref, anchor, true);

  useEffect(() => {
    const ctrl = new AbortController();
    usersApi.detail(row.Id, ctrl.signal).then(setDetail).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(e instanceof ApiError ? e.message : T.failed);
    });
    return () => ctrl.abort();
  }, [row.Id]);

  useEffect(() => {
    if (detail) ref.current?.querySelector<HTMLButtonElement>("button:not([disabled])")?.focus();
  }, [detail]);

  useEffect(() => {
    const down = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node) && !anchor.contains(e.target as Node)) onClose();
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        anchor.focus();
      }
    };
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", down);
      document.removeEventListener("keydown", key);
    };
  }, [anchor, onClose]);

  const item = (action: UserAction, label: string) => detail && (
    <MenuItem label={label} state={detail.actions[action]} onClick={() => onPick(action, detail)} />
  );
  return (
    <div className="sc-table-pop sc-table-pop--menu sc-floating" ref={ref}>
      <div className="sc-popmenu" role="menu" aria-label={T.rowMenu(String(row.UserName))}
           onKeyDown={(e) => {
             if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
             e.preventDefault();
             const buttons = [...e.currentTarget.querySelectorAll<HTMLButtonElement>("button:not([disabled])")];
             const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
             buttons[(at + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
           }}>
        {error ? <Alert tone="error">{error}</Alert> : !detail ? <p className="sc-muted sc-popmenu-note">{tr.ui.busy}</p> : (
          <>
            {item("role", T.roleTitle)}
            {item("name", T.nameTitle)}
            {item("reset", T.resetTitle)}
            {item("unlock", T.unlockTitle)}
            {detail.user.is_active ? item("close", T.closeTitle) : item("reopen", T.reopenTitle)}
          </>
        )}
      </div>
    </div>
  );
}

type Shown =
  | { kind: "add" }
  | { kind: "matrix" }
  | { kind: "password"; result: TemporaryPassword; mode: "created" | "reset" }
  | { kind: UserAction; detail: UserDetail };

export function Users() {
  const me = useAuth().me!;
  const [reloadKey, setReloadKey] = useState(0);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement } | null>(null);
  const [shown, setShown] = useState<Shown | null>(null);

  const close = () => setShown(null);
  const changed = (message?: string) => {
    setReloadKey((n) => n + 1);
    if (message) emitNotice(message);
    close();
  };
  const rowMenu = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.UserName)),
    onOpen: (row: Row, anchor: HTMLElement) => setMenu((m) => (m?.row.Id === row.Id ? null : { row, anchor })),
  }), []);

  const dialog = () => {
    if (!shown) return null;
    if (shown.kind === "matrix") return <PermissionMatrixDialog onClose={close} />;
    if (shown.kind === "add") {
      return <AddUserDialog onClose={close} onCreated={(result) => {
        setReloadKey((n) => n + 1);
        setShown({ kind: "password", result, mode: "created" });
      }} />;
    }
    if (shown.kind === "password") return <TemporaryPasswordDialog result={shown.result} kind={shown.mode} onClose={close} />;
    const { detail } = shown;
    const { user } = detail;
    const name = nameOf(user);
    switch (shown.kind) {
      case "role":
        return <RoleDialog detail={detail} onClose={close} onDone={(role) => changed(T.roleNotice(user.user_name, role))} />;
      case "name":
        return <NameDialog detail={detail} onClose={close} onDone={() => changed(T.nameNotice(user.user_name))} />;
      case "reset":
        return (
          <ActionDialog title={T.resetTitle} submitLabel={T.resetSubmit} run={() => usersApi.resetPassword(user.id)}
                        onClose={close} onDone={(result) => {
                          setReloadKey((n) => n + 1);
                          setShown({ kind: "password", result, mode: "reset" });
                        }}>
            {T.resetText(name)}
          </ActionDialog>
        );
      case "unlock":
        return (
          <ActionDialog title={T.unlockTitle} submitLabel={T.unlockSubmit} run={() => usersApi.unlock(user.id)}
                        onClose={close} onDone={() => changed(T.unlockNotice(user.user_name))}>
            {T.unlockText(name)}
          </ActionDialog>
        );
      case "close":
        return (
          <ActionDialog title={T.closeConfirm} submitLabel={T.closeSubmit} danger
                        run={() => usersApi.close(user.id)} onClose={close} onDone={() => changed(T.closeNotice(user.user_name))}>
            {T.closeText(name, user.open_sessions > 0)}
          </ActionDialog>
        );
      case "reopen":
        return (
          <ActionDialog title={T.reopenTitle} submitLabel={T.reopenSubmit} run={() => usersApi.reopen(user.id)}
                        onClose={close} onDone={() => changed(T.reopenNotice(user.user_name))}>
            {T.reopenText(name)}
          </ActionDialog>
        );
    }
  };

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head sc-page-head--row">
        <h1>{T.title}</h1>
        <div className="sc-page-head-actions">
          {can(me, 90) && <Button onClick={() => setShown({ kind: "matrix" })}>{tr.matrix.title}</Button>}
          <Button variant="primary" disabledReason={can(me, 88, "write") ? null : forbiddenReason(88, "write")}
                  onClick={() => setShown({ kind: "add" })}>
            {T.add}
          </Button>
        </div>
      </header>
      <DataTable list="users" cellRender={CELLS} rowMenu={rowMenu} reloadKey={reloadKey} />
      {menu && (
        <RowMenu key={menu.row.Id} row={menu.row} anchor={menu.anchor} onClose={() => setMenu(null)}
                 onPick={(kind, detail) => {
                   setMenu(null);
                   setShown({ kind, detail });
                 }} />
      )}
      {dialog()}
    </section>
  );
}
