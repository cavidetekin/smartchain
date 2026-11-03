// Kabuk (docs/12, K-82): kenar menü + bağlam çubuğu + çalışma alanı.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet } from "react-router";

import { emitNotice, type Job } from "../api/client";
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
  const onJob = useCallback((job: Job) => setExports((x) => (
    x.some((e) => e.jobId === job.id) ? x.map((e) => (e.jobId === job.id ? { ...e, job } : e)) : x)), []);
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
      <ExportToasts items={exports} onDismiss={dismissExport} />
      <ForbiddenNotice />
      <IdleWatch me={me} />
    </div>
    </ShellContext.Provider>
  );
}
