// Kenar menü (docs/12, K-82): gruplar, en çok iki seviye, arama (Ctrl+K), daraltma ve yandan açılan alt panel.
import { ChartLine, ChevronDown, ChevronRight, Lock, PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { NavLink, useNavigate } from "react-router";

import { fold } from "../format";
import { tr } from "../i18n/tr";
import type { userPrefs } from "../prefs";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { childrenOf, GROUPS, type GroupId, HOME, SCREENS, type Screen, screensInGroup } from "../screens/catalog";

interface Props {
  collapsed: boolean;
  onToggle(): void;
  onRequestSearch(): void;
  searchTick: number;
  workspaceOpen: boolean;
  prefs: ReturnType<typeof userPrefs>;
}

export function Sidebar({ collapsed, onToggle, onRequestSearch, searchTick, workspaceOpen, prefs }: Props) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState<string[]>(prefs.openGroups());
  const [flyout, setFlyout] = useState<GroupId | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (searchTick) inputRef.current?.focus();
  }, [searchTick]);

  const disabled = (s: Screen) => Boolean(s.requiresWorkspace && !workspaceOpen);
  // Rol bazlı görünürlük (K-100): okuma yetkisi olmayan ekran ve içi boş kalan grup menüde yok; arama da yalnız görünenlerde.
  const me = useAuth().me!;
  const visible = (s: Screen) => can(me, s.fn);
  const groups = GROUPS.filter((g) => screensInGroup(g.id).some(visible));
  const results = query.trim() ? SCREENS.filter((s) => visible(s) && fold(s.name).includes(fold(query.trim()))) : [];

  const toggleGroup = (id: GroupId) => {
    const next = open.includes(id) ? open.filter((g) => g !== id) : [...open, id];
    setOpen(next);
    prefs.setOpenGroups(next);
  };

  const go = (s: Screen | undefined) => {
    if (!s || disabled(s)) return;
    navigate(s.path);
    setQuery("");
  };

  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      go(results[active]);
    } else if (e.key === "Escape") {
      setQuery("");
      inputRef.current?.blur();
    }
  };

  const item = (s: Screen, sub = false) => {
    const Icon = s.icon;
    const cls = `sc-item${sub ? " is-sub" : ""}`;
    if (disabled(s)) {
      return (
        <span className={`${cls} is-disabled`} aria-disabled="true" title={tr.menu.needsWorkspace}>
          <Icon aria-hidden="true" />
          {!collapsed && <span>{s.name}</span>}
          {!collapsed && <Lock aria-hidden="true" className="sc-lock" data-testid="lock" />}
        </span>
      );
    }
    return (
      <NavLink to={s.path} className={({ isActive }) => `${cls}${isActive ? " is-active" : ""}`}
               title={collapsed ? s.name : undefined} aria-label={collapsed ? s.name : undefined} end>
        <Icon aria-hidden="true" />
        {!collapsed && <span>{s.name}</span>}
      </NavLink>
    );
  };

  const groupList = (id: GroupId) => (
    <ul>
      {screensInGroup(id).filter(visible).map((s) => (
        <li key={s.no}>
          {item(s)}
          {childrenOf(s.no).some(visible) && (
            <ul className="sc-sub">
              {childrenOf(s.no).filter(visible).map((c) => (
                <li key={c.no}>{item(c, true)}</li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );

  return (
    <nav className="sc-sidebar" aria-label="Ana menü">
      <div className="sc-brand">
        <span className="sc-logo"><ChartLine aria-hidden="true" /></span>
        {!collapsed && <span className="sc-brand-name">{tr.app.name}</span>}
        <button type="button" className="sc-icon-btn sc-toggle" onClick={onToggle}
                aria-label={collapsed ? tr.menu.expand : tr.menu.collapse}
                title={collapsed ? tr.menu.expand : tr.menu.collapse}>
          {collapsed ? <PanelLeftOpen aria-hidden="true" /> : <PanelLeftClose aria-hidden="true" />}
        </button>
      </div>

      {collapsed ? (
        <button type="button" className="sc-icon-btn sc-search-btn" onClick={onRequestSearch}
                aria-label={tr.menu.search} title={`${tr.menu.search} (${tr.menu.searchHint})`}>
          <Search aria-hidden="true" />
        </button>
      ) : (
        <label className="sc-search">
          <Search aria-hidden="true" />
          <input ref={inputRef} type="search" value={query} placeholder={tr.menu.search} aria-label={tr.menu.search}
                 onChange={(e) => {
                   setQuery(e.target.value);
                   setActive(0);
                 }}
                 onKeyDown={onSearchKey} />
          <kbd>{tr.menu.searchHint}</kbd>
        </label>
      )}

      <div className="sc-menu">
        {query.trim() && !collapsed ? (
          <ul role="listbox" aria-label={tr.menu.search}>
            {results.length === 0 && <li className="sc-empty">{tr.menu.noResults}</li>}
            {results.map((s, i) => (
              <li key={s.no} role="option" aria-selected={i === active} className={i === active ? "is-highlighted" : ""}
                  onMouseEnter={() => setActive(i)}>
                {item(s)}
              </li>
            ))}
          </ul>
        ) : collapsed ? (
          <ul>
            <li>{item(HOME)}</li>
            {groups.map((g) => {
              const Icon = g.icon;
              const name = tr.menu.groups[g.id];
              return (
                <li key={g.id} className="sc-group-icon" onMouseEnter={() => setFlyout(g.id)}
                    onMouseLeave={() => setFlyout(null)} onFocus={() => setFlyout(g.id)}>
                  <button type="button" className="sc-item" aria-label={name} title={name} aria-haspopup="menu"
                          aria-expanded={flyout === g.id}>
                    <Icon aria-hidden="true" />
                  </button>
                  {flyout === g.id && (
                    <div className="sc-flyout" role="menu" aria-label={name}>
                      <div className="sc-flyout-title">{name}</div>
                      <FlyoutList group={g.id} disabled={disabled} visible={visible} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <ul>
            <li>{item(HOME)}</li>
            {groups.map((g) => {
              const isOpen = open.includes(g.id);
              return (
                <li key={g.id} className="sc-group">
                  <button type="button" className="sc-group-head" aria-expanded={isOpen} onClick={() => toggleGroup(g.id)}>
                    <span>{tr.menu.groups[g.id]}</span>
                    {isOpen ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
                  </button>
                  {isOpen && groupList(g.id)}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </nav>
  );
}

function FlyoutList({ group, disabled, visible }: {
  group: GroupId; disabled: (s: Screen) => boolean; visible: (s: Screen) => boolean;
}) {
  const row = (s: Screen, sub = false) =>
    disabled(s) ? (
      <span className={`sc-flyout-item is-disabled${sub ? " is-sub" : ""}`} aria-disabled="true"
            title={tr.menu.needsWorkspace}>
        <span>{s.name}</span>
        <Lock aria-hidden="true" className="sc-lock" data-testid="lock" />
      </span>
    ) : (
      <NavLink to={s.path} role="menuitem" className={`sc-flyout-item${sub ? " is-sub" : ""}`}>{s.name}</NavLink>
    );
  return (
    <ul>
      {screensInGroup(group).filter(visible).map((s) => (
        <li key={s.no}>
          {row(s)}
          {childrenOf(s.no).filter(visible).map((c) => (
            <div key={c.no}>{row(c, true)}</div>
          ))}
        </li>
      ))}
    </ul>
  );
}
