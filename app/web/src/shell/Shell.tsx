// Kabuk (docs/12, K-82): kenar menü + bağlam çubuğu + çalışma alanı.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Outlet, useNavigate } from "react-router";

import { api, ApiError, emitNotice, importResultPath, JOB_DONE, JOB_FAILED, JOB_PRECHECK, JOB_PULL, JOB_VALIDATION, pullResultPath, type Job,
  validationResultPath } from "../api/client";
import { authApi } from "../auth/authApi";
import { useAuth } from "../auth/AuthContext";
import { IdleWatch } from "../auth/IdleWatch";
import { tr } from "../i18n/tr";
import { applyFontSize, DEFAULT_FONT_SIZE, type FontSize, userPrefs, validFontSize } from "../prefs";
import { ContextBar } from "./ContextBar";
import { type ExportItem, ExportToasts } from "./ExportToasts";
import { FlowStatusProvider } from "./FlowStatus";
import { ForbiddenNotice } from "./ForbiddenNotice";
import { hasUnsaved } from "../table/useTableEdits";
import { ConfirmDialog } from "../ui";
import { scenarioApi } from "./scenarioApi";
import { ShellContext, type ShellScenario, type TrackedExport } from "./ShellContext";
import { Sidebar } from "./Sidebar";
import { VALIDATION_ACTIVE, validationNotifies } from "./validationNotice";

/** Oturum kapısının (auth/AuthGate) içinde açılır; kullanıcı oturumdan gelir (K-97). */
const RECENT_CHECK_MS = 10 * 60 * 1000;  // sayfa yenilenirse: yeni biten ön kontrol yine bildirilir
const DATA_LOAD_PATH = "/veri/veri-yukleme";  // özet bildirimin "Sonucu aç" hedefi: tablo listesi (K-181)

export function Shell() {
  const me = useAuth().me!;
  const userId = me.id;
  const prefs = useMemo(() => userPrefs(userId), [userId]);
  const [collapsed, setCollapsed] = useState(prefs.collapsed());
  // U-23: kullanıcı kaydından; henüz seçilmediyse tarayıcıdaki eski değer (aşağıda bir kez sunucuya taşınır).
  const [fontSize, setFontSize] = useState<FontSize>(validFontSize(me.font_size) ?? prefs.legacyFontSize() ?? DEFAULT_FONT_SIZE);
  const [searchTick, setSearchTick] = useState(0);
  const [exports, setExports] = useState<ExportItem[]>([]);
  // Çalışma açma 8.2'de gelir; o zamana kadar çalışmanın ekranları kapalıdır (K-43).
  const workspaceOpen = false;

  useEffect(() => applyFontSize(fontSize), [fontSize]);
  useEffect(() => () => applyFontSize(DEFAULT_FONT_SIZE), []);  // çıkışta giriş sayfası önceki kullanıcının boyutuyla açılmaz
  useEffect(() => {
    const saved = validFontSize(me.font_size);
    if (saved) setFontSize(saved);  // ör. başka bilgisayarda değişti, me yenilendi
  }, [me.font_size]);
  useEffect(() => {
    const legacy = prefs.legacyFontSize();
    if (legacy === null) return;
    if (validFontSize(me.font_size)) prefs.clearLegacyFontSize();
    else authApi.setFontSize(legacy).then(() => prefs.clearLegacyFontSize()).catch(() => undefined);  // sonraki açılışta yeniden denenir
  }, [me.font_size, prefs]);

  // Arka plandaki Excel aktarımları (K-91): iş göstergesinin aldığı iş mesajlarıyla izlenir.
  const trackExport = useCallback((e: TrackedExport) => setExports((x) => [...x, e]), []);
  // Excel ön kontrol işleri (K-129): bu sayfada biten ya da yeni bitmiş iş bildirim olur; eski işler listede kalır.
  const [checks, setChecks] = useState<Job[]>([]);
  const seenChecks = useRef(new Map<number, string>());
  const navigate = useNavigate();
  // Validasyon (K-181): kullanıcının validasyon işleri sürerken biten işler bekler; hepsi bitince birlikte bildirilir (tek özet bildirim).
  const waitingValidation = useRef(new Map<number, Job>());
  const activeValidation = useRef(new Set<number>());
  const onCheck = useCallback((job: Job) => {
    const validation = job.job_type === JOB_VALIDATION;
    const wanted = validation ? validationNotifies(job, userId)
      : (job.job_type === JOB_PRECHECK || job.job_type === JOB_PULL) && (job.requested_by ?? userId) === userId;
    if (!wanted || job.dismissed) return;
    const before = seenChecks.current.get(job.id);
    seenChecks.current.set(job.id, job.status);
    const ended = job.status === JOB_DONE || job.status === JOB_FAILED;
    const wasEnded = before === JOB_DONE || before === JOB_FAILED;
    const recent = !!job.ended_at && Date.now() - Date.parse(job.ended_at) < RECENT_CHECK_MS;
    const fresh = ended && !wasEnded && (before !== undefined || recent);
    if (!validation) {
      if (fresh) setChecks((x) => [...x.filter((j) => j.id !== job.id), job]);
      return;
    }
    if (VALIDATION_ACTIVE.includes(job.status)) activeValidation.current.add(job.id);
    else activeValidation.current.delete(job.id);
    if (fresh) waitingValidation.current.set(job.id, job);
    if (waitingValidation.current.size && activeValidation.current.size === 0) {
      const done = [...waitingValidation.current.values()];
      waitingValidation.current.clear();
      setChecks((x) => [...x.filter((j) => !done.some((d) => d.id === j.id)), ...done]);
    }
  }, [userId]);
  const dismissCheck = useCallback((jobId: number) => {
    setChecks((x) => x.filter((j) => j.id !== jobId));
    void api.dismissJob(jobId).catch(() => undefined);  // kapatma işte saklanır (K-132)
  }, []);
  const openCheck = useCallback((job: Job) => {
    dismissCheck(job.id);
    if (job.job_type === JOB_PULL) navigate(pullResultPath(job.id));
    else if (job.job_type === JOB_VALIDATION && job.validation?.entity) navigate(validationResultPath(job.validation.entity));
    else if (job.import_batch_id) navigate(importResultPath(job.import_batch_id));
  }, [dismissCheck, navigate]);
  const openValidationSummary = useCallback((jobIds: number[]) => {
    jobIds.forEach(dismissCheck);
    navigate(DATA_LOAD_PATH);
  }, [dismissCheck, navigate]);
  const onJob = useCallback((job: Job) => {
    onCheck(job);
    setExports((x) => (x.some((e) => e.jobId === job.id) ? x.map((e) => (e.jobId === job.id ? { ...e, job } : e)) : x));
  }, [onCheck]);
  const dismissExport = useCallback((jobId: number) => setExports((x) => x.filter((e) => e.jobId !== jobId)), []);

  const setCollapsedRemembered = (value: boolean) => {
    setCollapsed(value);
    prefs.setCollapsed(value);
  };
  const requestSearch = () => {
    setCollapsedRemembered(false);
    setSearchTick((n) => n + 1);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        requestSearch();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Seçili senaryo (K-177): girişte kullanıcının hatırlanan senaryosu (yoksa, pasifse ya da silindiyse Baz)
  const [scenario, setScenario] = useState<ShellScenario | null>(null);
  const [scenarioTick, setScenarioTick] = useState(0);
  const [askScenario, setAskScenario] = useState<{ id: number; done(ok: boolean): void } | null>(null);
  const loadScenario = useCallback(() => {
    scenarioApi.current().then(setScenario).catch(() => undefined);
    setScenarioTick((n) => n + 1);
  }, []);
  useEffect(() => loadScenario(), [loadScenario]);
  const applyScenario = useCallback(async (id: number) => {
    try {
      setScenario(await scenarioApi.select(id));
      return true;
    } catch (e) {
      emitNotice(e instanceof ApiError ? e.message : tr.context.scenarioFailed);
      loadScenario();
      return false;
    }
  }, [loadScenario]);
  const selectScenario = useCallback((id: number) => {
    if (scenario?.id === id) return Promise.resolve(true);
    if (!hasUnsaved()) return applyScenario(id);
    return new Promise<boolean>((done) => setAskScenario({ id, done }));  // kaydedilmemiş değişiklik: önce onay
  }, [scenario, applyScenario]);
  const refreshScenario = loadScenario;

  const changeFontSize = (size: FontSize) => {
    setFontSize(size);
    authApi.setFontSize(size).catch(() => emitNotice(tr.user.fontSizeNotSaved));
  };

  return (
    <ShellContext.Provider value={{ userId, fontSize, setFontSize: changeFontSize, trackExport, scenario, selectScenario, refreshScenario, scenarioTick }}>
    <FlowStatusProvider>
    <div className={`sc-shell${collapsed ? " is-collapsed" : ""}`}>
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsedRemembered(!collapsed)}
        onRequestSearch={requestSearch}
        searchTick={searchTick}
        workspaceOpen={workspaceOpen}
        prefs={prefs}
      />
      <div className="sc-main">
        <ContextBar fontSize={fontSize} onFontSize={changeFontSize} onJob={onJob} />
        <main className="sc-content">
          <Outlet />
        </main>
      </div>
      <ExportToasts items={exports} onDismiss={dismissExport} checks={checks} onOpenCheck={openCheck} onDismissCheck={dismissCheck}
                    onOpenValidationSummary={openValidationSummary} />
      <ForbiddenNotice />
      <IdleWatch me={me} />
      {askScenario && (
        <ConfirmDialog title={tr.table.unsavedTitle} message={tr.table.unsavedText} confirmLabel={tr.table.unsavedLeave} danger
                       onCancel={() => { askScenario.done(false); setAskScenario(null); }}
                       onConfirm={() => { const ask = askScenario; setAskScenario(null); void applyScenario(ask.id).then(ask.done); }} />
      )}
    </div>
    </FlowStatusProvider>
    </ShellContext.Provider>
  );
}
