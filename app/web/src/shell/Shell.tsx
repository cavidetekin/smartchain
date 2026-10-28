// Kabuk (docs/12, K-82): kenar menü + bağlam çubuğu + çalışma alanı.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet } from "react-router";

import type { Job } from "../api/client";
import { applyFontSize, type FontSize, userPrefs } from "../prefs";
import { ContextBar } from "./ContextBar";
import { type ExportItem, ExportToasts } from "./ExportToasts";
import { ShellContext, type TrackedExport } from "./ShellContext";
import { Sidebar } from "./Sidebar";

export function Shell({ userId }: { userId: number }) {
  const prefs = useMemo(() => userPrefs(userId), [userId]);
  const [collapsed, setCollapsed] = useState(prefs.collapsed());
  const [fontSize, setFontSize] = useState<FontSize>(prefs.fontSize());
  const [searchTick, setSearchTick] = useState(0);
  const [exports, setExports] = useState<ExportItem[]>([]);
  // Çalışma açma 8.2'de gelir; o zamana kadar çalışmanın ekranları kapalıdır (K-43).
  const workspaceOpen = false;

  useEffect(() => applyFontSize(fontSize), [fontSize]);

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
    prefs.setFontSize(size);
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
        <ContextBar userId={userId} fontSize={fontSize} onFontSize={changeFontSize} onJob={onJob} />
        <main className="sc-content">
          <Outlet />
        </main>
      </div>
      <ExportToasts userId={userId} items={exports} onDismiss={dismissExport} />
    </div>
    </ShellContext.Provider>
  );
}
