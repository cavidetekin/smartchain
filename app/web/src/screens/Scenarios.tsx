// Senaryolar (ekran 07; fonksiyon 27, 28; K-177, docs/12): senaryoların listesi ve yönetimi. Şeridin solunda "Yeni senaryo" (Admin ve üstü);
// tablo içi düzenleme: "Gece çalışsın" anahtarı ve gece sırası (satır sürüklenir; yalnız gece çalışanlar arasında), Vazgeç ve Kaydet şeritte.
// Satır menüsü: Parametreler · Kopyala · Yeniden adlandır · Baz'dan ayır · Pasif yap / Aktif yap · Sil; yönetim öğeleri yalnız Admin ve üstünde
// görünür. Baz silinemez, pasif yapılamaz, yeniden adlandırılamaz. Başarılı işlemde bildirim yok; liste yenilenir.
import { type DragEvent, type HTMLAttributes, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { formatDateTime, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { scenarioApi, type DeleteInfo } from "../shell/scenarioApi";
import { useShell } from "../shell/ShellContext";
import { SwitchCell } from "../table/CellEditors";
import { DataTable, type FieldHints, type RowMenuSpec } from "../table/DataTable";
import { listApi, type Row } from "../table/types";
import { EditBar, UnsavedGuard } from "../table/useTableEdits";
import { Alert, Button, ConfirmDialog, Dialog, GridSeq, SelectField, TextField } from "../ui";
import { type MenuAction, MenuActions, MenuItem, RowPopMenu } from "../ui/PopMenu";
import { dropId } from "./DataRules";
import { PARAMETERS_PATH } from "./catalog";

const T = tr.scenarios;
const ADMIN_ROLES = ["System owner", "Admin"];
const NAME_MAX = 100;
const HINTS: FieldHints = { NightlyPriority: { width: 7, left: true }, Name: { width: 18 }, ModelType: { width: 6 }, FollowsBase: { width: 8 },
                            RunsNightly: { width: 9 }, BudgetSeconds: { width: 10 }, LastRunAt: { width: 15 }, ActiveLabel: { width: 6 } };
const ALLOWED = { allowed: true };

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const fieldError = (e: unknown, field: string) => (e instanceof ApiError ? e.details.find((d) => d.field === field)?.problem : undefined);

interface Scenario { id: string; name: string; isBase: boolean; isActive: boolean; runsNightly: boolean; followsBase: boolean; priority: number | null }
const asScenario = (r: Row): Scenario => ({
  id: String(r.Id), name: String(r.Name), isBase: Boolean(r.IsBase), isActive: r.IsActive !== false, runsNightly: Boolean(r.RunsNightly),
  followsBase: r.FollowsBase === "Evet", priority: r.NightlyPriority === null || r.NightlyPriority === undefined ? null : Number(r.NightlyPriority),
});

/** Yeni senaryo (ve Kopyala): her zaman var olan bir senaryodan kopyalanır. */
function ScenarioDialog({ all, sourceId, onClose, onDone }: { all: Scenario[]; sourceId: string; onClose(): void; onDone(): void }) {
  const [name, setName] = useState("");
  const [source, setSource] = useState(sourceId);
  const follows = (id: string) => { const s = all.find((x) => x.id === id); return !s || s.isBase || s.followsBase; };
  const [followsBase, setFollowsBase] = useState(follows(sourceId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | undefined>();
  const save = async () => {
    setBusy(true);
    setError(null);
    setNameError(undefined);
    try {
      await scenarioApi.create(name.trim(), Number(source), followsBase);
      onDone();
    } catch (e) {
      const problem = fieldError(e, "name");
      setNameError(problem);
      setError(problem ? null : errorText(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={T.newScenario} onClose={onClose} onSubmit={() => void save()} submitLabel={tr.ui.save} busy={busy} submitDisabled={!name.trim()}>
      {error && <Alert tone="error">{error}</Alert>}
      <TextField label={T.name} required value={name} maxLength={NAME_MAX} error={nameError} autoFocus onChange={(v) => { setName(v); setNameError(undefined); }} />
      <SelectField label={T.source} value={source} options={all.map((s) => ({ value: s.id, label: s.isBase ? T.baseName(s.name) : s.name }))}
                   onChange={(v) => { setSource(v); setFollowsBase(follows(v)); }} />
      <div className="sc-field sc-field--inline">
        <span className="sc-field-label">{T.followsBase}</span>
        <SwitchCell label={T.followsBase} checked={followsBase} editable size="md" onToggle={setFollowsBase} />
      </div>
    </Dialog>
  );
}

function RenameDialog({ scenario, onClose, onDone }: { scenario: Scenario; onClose(): void; onDone(): void }) {
  const [name, setName] = useState(scenario.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const save = async () => {
    setBusy(true);
    try {
      await scenarioApi.rename(Number(scenario.id), name.trim());
      onDone();
    } catch (e) {
      setError(fieldError(e, "name") ?? errorText(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={T.renameTitle(scenario.name)} onClose={onClose} onSubmit={() => void save()} submitLabel={tr.ui.save} busy={busy}
            submitDisabled={!name.trim() || name.trim() === scenario.name}>
      <TextField label={T.name} required value={name} maxLength={NAME_MAX} error={error} autoFocus onChange={(v) => { setName(v); setError(undefined); }} />
    </Dialog>
  );
}

/** Silme onayı: silinecek plan versiyonu sayısını söyler; yayınlanmış planı olan senaryo silinemez. */
function DeleteDialog({ scenario, onClose, onDone }: { scenario: Scenario; onClose(): void; onDone(): void }) {
  const [info, setInfo] = useState<DeleteInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    scenarioApi.deleteInfo(Number(scenario.id), ctrl.signal).then(setInfo).catch((e: unknown) => { if (!ctrl.signal.aborted) setError(errorText(e)); });
    return () => ctrl.abort();
  }, [scenario.id]);
  const remove = async () => {
    setBusy(true);
    try {
      await scenarioApi.remove(Number(scenario.id));
      onDone();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };
  return (
    <Dialog title={T.deleteTitle(scenario.name)} onClose={onClose} onSubmit={() => void remove()} submitLabel={T.remove} danger busy={busy}
            submitDisabled={!info?.deletable} submitReason={info?.reason}>
      {error && <Alert tone="error">{error}</Alert>}
      {info && <p className="sc-dialog-message">{info.deletable ? T.deleteText(info.plan_versions) : info.reason}</p>}
    </Dialog>
  );
}

type Ask = { kind: "new"; source: string } | { kind: "rename" | "delete" | "detach" | "passive"; scenario: Scenario };

export function Scenarios() {
  const me = useAuth().me!;
  const shell = useShell();
  const navigate = useNavigate();
  const isAdmin = ADMIN_ROLES.includes(me.role);
  const nightlyReason = can(me, 28, "write") ? null : forbiddenReason(28, "write");
  const [reloadKey, setReloadKey] = useState(0);
  const [all, setAll] = useState<Scenario[]>([]);
  const [night, setNight] = useState<string[] | null>(null);  // taslak: gece çalışan senaryolar, sırasıyla
  const [drag, setDrag] = useState<{ id: string; over?: string; side?: "before" | "after" } | null>(null);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement; extra?: MenuAction[] } | null>(null);
  const [ask, setAsk] = useState<Ask | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {  // bütün senaryolar (küçük liste): taslak sıra ve "Kopyalanacak senaryo" seçenekleri
    const ctrl = new AbortController();
    listApi("scenarios").query({ fields: ["Name"], sort: [{ field: "NightOrder", dir: "asc" }, { field: "Name", dir: "asc" }], filters: [], offset: 0, limit: 100 }, ctrl.signal)
      .then((r) => { setAll(r.rows.map(asScenario)); setNight(null); }).catch(() => undefined);
    return () => ctrl.abort();
  }, [reloadKey]);

  const savedNight = useMemo(() => all.filter((s) => s.runsNightly).sort((a, b) => (a.priority ?? 1e9) - (b.priority ?? 1e9)).map((s) => s.id), [all]);
  const current = night ?? savedNight;
  const dirty = night !== null && night.join(",") !== savedNight.join(",");
  const refresh = () => {
    setAsk(null);
    setReloadKey((k) => k + 1);
    shell.refreshScenario();  // ad, pasif ya da silme seçili senaryoyu ve bağlam çubuğunun listesini etkiler
  };
  const fail = (e: unknown) => {
    setAsk(null);
    setError(errorText(e));
  };
  const act = async (work: () => Promise<unknown>) => {
    try {
      await work();
      refresh();
    } catch (e) {
      fail(e);
    }
  };
  const saveNight = async () => {
    setSaving(true);
    setError(null);
    try {
      const on = new Set(current);
      await scenarioApi.saveNightly([...current.map((id) => ({ id: Number(id), runs_nightly: true })),
                                     ...all.filter((s) => !on.has(s.id)).map((s) => ({ id: Number(s.id), runs_nightly: false }))]);
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  };
  const openParameters = async (row: Row) => {
    setMenu(null);
    if (await shell.selectScenario(Number(row.Id))) navigate(PARAMETERS_PATH);
  };

  const cellRender = useMemo(() => ({
    NightlyPriority: (_v: unknown, row: Row) => {
      const at = current.indexOf(String(row.Id));
      return <GridSeq seq={at >= 0 ? at + 1 : null} movable={!nightlyReason && at >= 0} />;
    },
    Name: (value: unknown, row: Row) => (row.IsBase ? T.baseName(String(value)) : String(value)),
    RunsNightly: (_v: unknown, row: Row) => {
      const id = String(row.Id);
      const on = current.includes(id);
      return <SwitchCell label={T.runsNightlyOf(String(row.Name))} checked={on} editable={!nightlyReason && row.IsActive !== false}
                         changed={on !== savedNight.includes(id)} onToggle={(next) => setNight(next ? [...current, id] : current.filter((x) => x !== id))} />;
    },
    LastRunAt: (value: unknown, row: Row) => (value ? <span className="sc-num">{T.lastRun(formatDateTime(serverDate(String(value))), String(row.LastRunStatus ?? ""))}</span> : null),
  }), [current, savedNight, nightlyReason]);

  /** Sürükle-bırak: yalnız gece çalışan satırlar arasında; üst yarı önüne, alt yarı arkasına. */
  const rowProps = useCallback((row: Row): HTMLAttributes<HTMLTableRowElement> => {
    const id = String(row.Id);
    const passive = row.IsActive === false ? "is-off" : "";
    if (nightlyReason || !current.includes(id)) return { className: passive || undefined };
    return {
      draggable: true,
      className: `${passive}${drag?.over === id ? ` is-drop-${drag.side}` : drag?.id === id ? " is-dragging" : ""}`.trim() || undefined,
      onDragStart: (e: DragEvent<HTMLTableRowElement>) => {
        e.dataTransfer?.setData("text/plain", id);
        if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
        setDrag({ id });
      },
      onDragOver: (e: DragEvent<HTMLTableRowElement>) => {
        if (!drag || drag.id === id) return;
        e.preventDefault();
        const r = e.currentTarget.getBoundingClientRect();
        const side = e.clientY < r.top + r.height / 2 ? "before" : "after";
        if (drag.over !== id || drag.side !== side) setDrag({ ...drag, over: id, side });
      },
      onDrop: (e: DragEvent<HTMLTableRowElement>) => {
        e.preventDefault();
        const from = drag?.id ?? e.dataTransfer?.getData("text/plain");
        if (from && from !== id && current.includes(from)) setNight(dropId(current, from, id, drag?.side ?? "before"));
        setDrag(null);
      },
      onDragEnd: () => setDrag(null),
    };
  }, [nightlyReason, drag, current]);

  // Taslak varken satırlar taslak sırayla: gece çalışanlar önce, sonra ötekiler ada göre
  const rowOrder = useMemo(() => (dirty ? [...current, ...all.filter((s) => !current.includes(s.id)).map((s) => s.id)] : null), [dirty, current, all]);
  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.Name)),
    onOpen: (row: Row, anchor: HTMLElement, extra?: MenuAction[]) => setMenu({ row, anchor, extra }),
  }), []);

  const picked = menu ? asScenario(menu.row) : null;
  const baseLocked = { allowed: false, reason: T.baseLocked };
  const choose = (next: Ask) => {
    setMenu(null);
    setAsk(next);
  };
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {error && <Alert tone="error" onClose={() => setError(null)}>{error}</Alert>}
      <DataTable list="scenarios" fieldHints={HINTS} cellRender={cellRender} rowMenu={rowMenu} rowProps={rowProps} rowOrder={rowOrder} reloadKey={reloadKey}
                 toolbarActions={<EditBar dirty={dirty} busy={saving} onSave={() => void saveNight()} onDiscard={() => setNight(null)} disabledReason={nightlyReason} />}
                 toolbarLead={isAdmin ? (
                   <Button variant="primary" onClick={() => setAsk({ kind: "new", source: String(shell.scenario?.id ?? all.find((s) => s.isBase)?.id ?? "") })}>{T.newScenario}</Button>
                 ) : undefined} />
      <UnsavedGuard dirty={dirty} />
      {menu && picked && (
        <RowPopMenu label={T.rowMenu(picked.name)} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuActions items={menu.extra} onDone={() => setMenu(null)} />
          <MenuItem label={T.parameters} state={ALLOWED} onClick={() => void openParameters(menu.row)} />
          {isAdmin && (
            <>
              <MenuItem label={T.copy} state={ALLOWED} onClick={() => choose({ kind: "new", source: picked.id })} />
              <MenuItem label={T.rename} state={picked.isBase ? baseLocked : ALLOWED} onClick={() => choose({ kind: "rename", scenario: picked })} />
              <MenuItem label={T.detach} state={picked.isBase || !picked.followsBase ? { allowed: false, reason: T.notFollowing } : ALLOWED}
                        onClick={() => choose({ kind: "detach", scenario: picked })} />
              {picked.isActive
                ? <MenuItem label={T.makePassive} state={picked.isBase ? baseLocked : ALLOWED} onClick={() => choose({ kind: "passive", scenario: picked })} />
                : <MenuItem label={T.makeActive} state={ALLOWED} onClick={() => { setMenu(null); void act(() => scenarioApi.setActive(Number(picked.id), true)); }} />}
              <MenuItem label={T.remove} state={picked.isBase ? baseLocked : ALLOWED} onClick={() => choose({ kind: "delete", scenario: picked })} />
            </>
          )}
        </RowPopMenu>
      )}
      {ask?.kind === "new" && <ScenarioDialog all={all} sourceId={ask.source} onClose={() => setAsk(null)} onDone={refresh} />}
      {ask?.kind === "rename" && <RenameDialog scenario={ask.scenario} onClose={() => setAsk(null)} onDone={refresh} />}
      {ask?.kind === "delete" && <DeleteDialog scenario={ask.scenario} onClose={() => setAsk(null)} onDone={refresh} />}
      {ask?.kind === "detach" && (
        <ConfirmDialog title={T.detachTitle(ask.scenario.name)} message={T.detachText} confirmLabel={T.detachConfirm} danger onCancel={() => setAsk(null)}
                       onConfirm={() => void act(() => scenarioApi.detach(Number(ask.scenario.id)))} />
      )}
      {ask?.kind === "passive" && (
        <ConfirmDialog title={T.passiveTitle(ask.scenario.name)} message={T.passiveText} confirmLabel={T.makePassive} onCancel={() => setAsk(null)}
                       onConfirm={() => void act(() => scenarioApi.setActive(Number(ask.scenario.id), false))} />
      )}
    </section>
  );
}
