// Kabuk (docs/12, K-82): kenar menü + bağlam çubuğu + çalışma alanı.
import { useEffect, useMemo, useState } from "react";
import { Outlet } from "react-router";

import { applyFontSize, type FontSize, userPrefs } from "../prefs";
import { ContextBar } from "./ContextBar";
import { Sidebar } from "./Sidebar";

export function Shell({ userId }: { userId: number }) {
  const prefs = useMemo(() => userPrefs(userId), [userId]);
  const [collapsed, setCollapsed] = useState(prefs.collapsed());
  const [fontSize, setFontSize] = useState<FontSize>(prefs.fontSize());
  const [searchTick, setSearchTick] = useState(0);
  // Çalışma açma 8.2'de gelir; o zamana kadar çalışmanın ekranları kapalıdır (K-43).
  const workspaceOpen = false;

  useEffect(() => applyFontSize(fontSize), [fontSize]);

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

  return (
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
        <ContextBar
          userId={userId}
          fontSize={fontSize}
          onFontSize={(size) => {
            setFontSize(size);
            prefs.setFontSize(size);
          }}
        />
        <main className="sc-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
