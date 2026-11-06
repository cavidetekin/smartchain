// Kabuk (docs/12, K-82): kenar menü + bağlam çubuğu + çalışma alanı.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Outlet, useNavigate } from "react-router";

import { api, emitNotice, importResultPath, JOB_DONE, JOB_FAILED, JOB_PRECHECK, JOB_PULL, JOB_VALIDATION, pullResultPath, type Job, VALIDATION_NOTIFY,
  validationResultPath } from "../api/client";
import { authApi } from "../auth/authApi";
import { useAuth } from "../auth/AuthContext";
import { IdleWatch } from "../auth/IdleWatch";
import { tr } from "../i18n/tr";
import { applyFontSize, DEFAULT_FONT_SIZE, type FontSize, userPrefs, validFontSize } from "../prefs";
import { ContextBar } from "./ContextBar";
import { type ExportItem, ExportToasts } from "./ExportToasts";
import { ForbiddenNotice } from "./ForbiddenNotice";
import { ShellContext, type TrackedExport } from "./ShellContext";
import { Sidebar } from "./Sidebar";

/** Oturum kapısının (auth/AuthGate) içinde açılır; kullanıcı oturumdan gelir (K-97). */
const RECENT_CHECK_MS = 10 * 60 * 1000;  // sayfa yenilenirse: yeni biten ön kontrol yine bildirilir

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
  const onCheck = useCallback((job: Job) => {
    const validation = job.job_type === JOB_VALIDATION && VALIDATION_NOTIFY.includes(job.validation?.trigger ?? "") && Boolean(job.validation?.entity);
    if ((job.job_type !== JOB_PRECHECK && job.job_type !== JOB_PULL && !validation) || (job.requested_by ?? userId) !== userId || job.dismissed) return;
    const before = seenChecks.current.get(job.id);
    seenChecks.current.set(job.id, job.status);
    const ended = job.status === JOB_DONE || job.status === JOB_FAILED;
    const wasEnded = before === JOB_DONE || before === JOB_FAILED;
    const recent = !!job.ended_at && Date.now() - Date.parse(job.ended_at) < RECENT_CHECK_MS;
    if (ended && !wasEnded && (before !== undefined || recent)) setChecks((x) => [...x.filter((j) => j.id !== job.id), job]);
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

  const changeFontSize = (size: FontSize) => {
    setFontSize(size);
    authApi.setFontSize(size).catch(() => emitNotice(tr.user.fontSizeNotSaved));
  };

  return (
    <ShellContext.Provider value={{ userId, fontSize, setFontSize: changeFontSize, trackExport }}>
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
      <ExportToasts items={exports} onDismiss={dismissExport} checks={checks} onOpenCheck={openCheck} onDismissCheck={dismissCheck} />
      <ForbiddenNotice />
      <IdleWatch me={me} />
    </div>
    </ShellContext.Provider>
  );
}
