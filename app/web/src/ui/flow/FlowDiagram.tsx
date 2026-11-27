// Akış çizimi (docs/12 "Akış çizimi standardı", K-200): kutular, uçlu oklar ve + işaretleri; kendi SVG bileşenimiz, dış kütüphane yok.
// Bileşen veri bilmez: düğümleri, etiketleri ve olayları kullanan ekran verir (Üretim akışı; 8.5'te pegging'in akış görünümü).
// Konum: dal açılıp kapanınca `anchor` kutusu ekranda yerinde kalır, yeni açılan kutular görünmüyorsa görünecek kadar kayar; `centerKey`
// değişince seçili kutu ortalanır. Yakınlaştırma bileşenin içindedir (düğmeler `api` ile, Ctrl + tekerlek imlecin olduğu noktaya doğru).
import { type KeyboardEvent, type Ref, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from "react";

import { badgeOf, FONT, type FlowLayout, type FlowModel, type FlowNode, type FlowSide, layoutFlow, linesOf, pathOf, type Placed, SIZE, type Toggle, U } from "./flowLayout";

export const ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.8, 1, 1.25, 1.5, 2];
const ZOOM_MIN = ZOOM_STEPS[0];
const ZOOM_MAX = ZOOM_STEPS[ZOOM_STEPS.length - 1];
const FIT_MIN = 0.1;          // "Sığdır" çok büyük çizimde adımların altına inebilir

const press = (run: () => void) => (e: KeyboardEvent) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    e.stopPropagation();
    run();
  }
};

export interface FlowLabels {
  /** İşaretin erişilebilir adı (ör. "MAM-006 kullandıklarını aç"). */
  toggle(node: FlowNode, side: FlowSide, open: boolean): string;
  /** Yüklenirken işaretin adı. */
  busy: string;
}

/** Çizimin dışarıdan sürülen işlemleri (başlıktaki düğmeler). */
export interface FlowApi {
  zoomIn(): void;
  zoomOut(): void;
  /** %100. */
  reset(): void;
  /** Açık çizimin tamamı alana sığar (en çok %100) ve ortalanır. */
  fit(): void;
  /** O anki yerleşim (PNG çıktısı aynı yerleşimi çizer). */
  layout(): FlowLayout;
}

type Intent = { kind: "fit" } | { kind: "focal"; x: number; y: number } | null;

export function FlowDiagram({ model, label, labels, anchor, centerKey, focusCurrent, api, onZoom, onToggle, onPick, onMore }: {
  model: FlowModel;
  /** Çizimin erişilebilir adı. */
  label: string;
  labels: FlowLabels;
  /** Son basılan kutunun kimliği: yerleşim değişince ekranda yerinde kalır. */
  anchor?: string | null;
  /** Değişince seçili kutu ortalanır (ilk açılış, seçili kutunun değişmesi, "Tümünü kapat"). */
  centerKey: string | number;
  /** Çizim ilk kurulduğunda odak seçili kutuya gelsin (seçili kutu az önce buradan değiştirildiyse). */
  focusCurrent?: boolean;
  api?: Ref<FlowApi>;
  /** Yakınlaştırma değişince (düğmelerin durumu için). */
  onZoom?(zoom: number): void;
  onToggle(node: FlowNode, side: FlowSide): void;
  /** Çift tıklama ya da Enter: kutu seçili olur. */
  onPick(node: FlowNode): void;
  onMore(node: FlowNode): void;
}) {
  const layout = useMemo(() => layoutFlow(model), [model]);
  const [zoom, setZoom] = useState(1);
  const [tick, setTick] = useState(0);            // aynı yakınlaştırmada yeniden yerleştir (ör. "Sığdır" iki kez)
  const wrap = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const view = useRef<{ key: string | number; zoom: number; margin: { x: number; y: number }; pos: Map<string, { x: number; y: number }> } | null>(null);
  const intent = useRef<Intent>(null);
  const live = useRef({ layout, zoom });
  live.current = { layout, zoom };

  const remPx = () => parseFloat(getComputedStyle(document.documentElement).fontSize) || 13;
  const apply = useCallback((next: number, how: Intent = null) => {
    intent.current = how;
    setZoom(next);
    setTick((n) => n + 1);
  }, []);
  useImperativeHandle(api, () => ({
    zoomIn: () => apply(ZOOM_STEPS.find((z) => z > live.current.zoom + 0.001) ?? ZOOM_MAX),
    zoomOut: () => apply([...ZOOM_STEPS].reverse().find((z) => z < live.current.zoom - 0.001) ?? Math.min(live.current.zoom, ZOOM_MIN)),
    reset: () => apply(1),
    fit: () => {
      const el = wrap.current;
      const rem = remPx();
      const z = el ? Math.min(el.clientWidth / (live.current.layout.width * rem), el.clientHeight / (live.current.layout.height * rem), 1) : 1;
      apply(Math.max(FIT_MIN, Number.isFinite(z) && z > 0 ? z : 1), { kind: "fit" });
    },
    layout: () => live.current.layout,
  }), [apply]);
  useEffect(() => { onZoom?.(zoom); }, [zoom]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Ctrl + tekerlek: imlecin olduğu noktaya doğru (tarayıcının sayfa yakınlaştırması yerine)
  useEffect(() => {
    const el = wrap.current;
    if (!el) return undefined;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const frame = el.getBoundingClientRect();
      const next = Math.min(ZOOM_MAX, Math.max(Math.min(ZOOM_MIN, live.current.zoom), live.current.zoom * Math.exp(-e.deltaY * 0.002)));
      apply(Math.round(next * 100) / 100, { kind: "focal", x: e.clientX - frame.left, y: e.clientY - frame.top });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [apply]);

  // Konum: çizimin alandaki başlangıcı (shift) = kenar payı − kaydırma. Tuval kaydırmaya yetecek kadar büyür.
  useLayoutEffect(() => {
    const el = wrap.current;
    const s = svg.current;
    const c = canvas.current;
    if (!el || !s || !c) return;
    const rem = remPx();
    const k = rem * zoom;                                               // yerleşim birimi (rem) başına piksel
    const cw = el.clientWidth;
    const ch = el.clientHeight;
    const pos = new Map(layout.nodes.map((p) => [p.node.id, { x: p.x, y: p.cy }]));
    const before = view.current?.key === centerKey ? view.current : null;
    const how = intent.current;
    intent.current = null;
    const origin = before ? { x: before.margin.x - el.scrollLeft, y: before.margin.y - el.scrollTop } : { x: 0, y: 0 };
    let shift: { x: number; y: number };
    let centered = false;
    if (!before) {                                                      // ilk açılış, seçili kutu değişti, "Tümünü kapat": seçili kutu ortada
      shift = { x: cw / 2 - (layout.root.x + layout.root.w / 2) * k, y: ch / 2 - layout.root.cy * k };
      centered = true;
    } else if (how?.kind === "fit") {                                   // çizimin tamamı ortada
      shift = { x: (cw - layout.width * k) / 2, y: (ch - layout.height * k) / 2 };
    } else if (before.zoom !== zoom) {                                  // yakınlaştırma: odak noktası (imleç ya da alanın ortası) yerinde kalır
      const f = how?.kind === "focal" ? how : { x: cw / 2, y: ch / 2 };
      const old = rem * before.zoom;
      shift = { x: f.x - ((f.x - origin.x) / old) * k, y: f.y - ((f.y - origin.y) / old) * k };
    } else {                                                            // dal açıldı ya da kapandı: basılan kutu yerinde kalır
      const id = anchor && pos.has(anchor) && before.pos.has(anchor) ? anchor : layout.root.node.id;
      const now = pos.get(id)!;
      const was = before.pos.get(id) ?? now;
      shift = { x: origin.x + (was.x - now.x) * k, y: origin.y + (was.y - now.y) * k };
      // yeni açılan kutular görünmüyorsa görünecek kadar kay (basılan kutu görünür kaldıkça)
      const fresh = layout.nodes.filter((p) => !before.pos.has(p.node.id));
      const held = layout.nodes.find((p) => p.node.id === id);
      if (fresh.length && held) {
        const pad = SIZE.pad * k * 0.5;
        const edge = (SIZE.toggle * 2) * k;
        const box = { l: Math.min(...fresh.map((p) => p.x)) * k - edge, r: Math.max(...fresh.map((p) => p.x + p.w)) * k + edge,
                      t: Math.min(...fresh.map((p) => p.cy - p.h / 2)) * k, b: Math.max(...fresh.map((p) => p.cy + p.h / 2)) * k };
        const over = shift.x + box.r + pad - cw;
        const under = -(shift.x + box.l - pad);
        if (over > 0) shift.x -= Math.max(0, Math.min(over, shift.x + held.x * k - pad));
        else if (under > 0) shift.x += Math.max(0, Math.min(under, cw - pad - (shift.x + (held.x + held.w) * k)));
        if (box.b - box.t + pad * 2 <= ch) {                              // dikeyde sığıyorsa tamamı görünsün
          const below = shift.y + box.b + pad - ch;
          const above = -(shift.y + box.t - pad);
          if (below > 0) shift.y -= Math.max(0, Math.min(below, shift.y + (held.cy - held.h / 2) * k - pad));
          else if (above > 0) shift.y += Math.max(0, Math.min(above, ch - pad - (shift.y + (held.cy + held.h / 2) * k)));
        }
      }
    }
    const margin = { x: Math.max(shift.x, 0), y: Math.max(shift.y, 0) };
    const scroll = { x: margin.x - shift.x, y: margin.y - shift.y };
    // tuval: çizim (kenar payıyla) ve kaydırma hedefi kadar; çizim alana sığıyorsa alan kadardır, kaydırma çubuğu çıkmaz
    c.style.width = `${Math.max(margin.x + layout.width * k, scroll.x + cw)}px`;
    c.style.height = `${Math.max(margin.y + layout.height * k, scroll.y + ch)}px`;
    s.style.marginLeft = `${margin.x}px`;
    s.style.marginTop = `${margin.y}px`;
    el.scrollLeft = scroll.x;
    el.scrollTop = scroll.y;
    // seçili kutu değişince (ya da "Tümünü kapat"ta) odak kaybolmasın: klavyeyle çalışan seçili kutudan devam eder
    if (centered && (view.current || focusCurrent) && (document.activeElement === document.body || s.contains(document.activeElement))) {
      s.querySelector<SVGGElement>(".sc-flow-node.is-current")?.focus({ preventScroll: true });
    }
    view.current = { key: centerKey, zoom, margin, pos };
  }, [layout, anchor, centerKey, zoom, tick]);  // eslint-disable-line react-hooks/exhaustive-deps

  const sideOf = (p: Placed): FlowSide => (p.side === "left" ? "left" : "right");
  const node = (p: Placed) => {
    const n = p.node;
    const current = p.side === "root";
    const x = p.x * U;
    const y = (p.cy - p.h / 2) * U;
    const w = p.w * U;
    const click = n.kind === "more" ? () => onMore(n) : () => onToggle(n, sideOf(p));
    const full = [n.title, n.text, n.meta, n.badge].filter(Boolean).join(" · ");
    const lines = linesOf(n);
    const badge = badgeOf(n);
    const tone = current ? "current" : n.kind === "option" ? "option" : n.tone ?? "box";
    return (
      <g key={n.id} className={`sc-flow-node sc-flow-node--${n.kind} sc-flow-tone--${tone}${current ? " is-current" : ""}`} role="button" tabIndex={0} aria-label={full}
         aria-current={current || undefined} data-node={n.id} data-tone={tone} onClick={click} onDoubleClick={n.kind === "box" && !current ? () => onPick(n) : undefined}
         onKeyDown={press(n.kind === "box" ? () => { if (!current) onPick(n); } : click)}>
        <title>{full}</title>
        <rect x={x} y={y} width={w} height={p.h * U} rx={n.kind === "box" ? 5 : (p.h * U) / 2} />
        {n.kind === "box" ? (
          <>
            <text className="sc-flow-code" x={x + 10} y={y + 14.5} fontSize={FONT.title}>{lines.title}</text>
            {lines.text && <text className="sc-flow-name" x={x + 10} y={y + 26.5} fontSize={FONT.text}>{lines.text}</text>}
            {lines.meta && <text className="sc-flow-meta" x={x + 10} y={y + 38} fontSize={FONT.meta}>{lines.meta}</text>}
            {badge && (
              <g className="sc-flow-badge">
                <rect x={x + w - badge.w * U - 5} y={y + 5} width={badge.w * U} height={SIZE.badgeH * U} rx={(SIZE.badgeH * U) / 2} />
                <text x={x + w - (badge.w * U) / 2 - 5} y={y + 5 + SIZE.badgeH * U - 3.4} fontSize={FONT.badge} textAnchor="middle">{badge.text}</text>
              </g>
            )}
          </>
        ) : n.kind === "option" ? (
          <>
            <text className="sc-flow-option" x={x + w / 2 - 3} y={y + (lines.text ? 12.5 : 18)} fontSize={FONT.option} textAnchor="middle">{lines.title}</text>
            {lines.text && <text className="sc-flow-meta" x={x + w / 2 - 3} y={y + 23} fontSize={FONT.optionText} textAnchor="middle">{lines.text}</text>}
          </>
        ) : (
          <text className="sc-flow-more" x={x + w / 2} y={y + 14.5} fontSize={FONT.more} textAnchor="middle">{lines.title}</text>
        )}
      </g>
    );
  };
  const toggle = (t: Toggle) => {
    const open = t.state === "open";
    const busy = t.state === "busy";
    const cx = t.cx * U;
    const cy = t.cy * U;
    const run = () => { if (!busy) onToggle(t.node, t.side); };
    return (
      <g key={t.id} className="sc-flow-toggle" role="button" tabIndex={0} aria-expanded={open} aria-busy={busy || undefined}
         aria-label={busy ? labels.busy : labels.toggle(t.node, t.side, open)} data-toggle={t.id}
         onClick={(e) => { e.stopPropagation(); run(); }} onDoubleClick={(e) => e.stopPropagation()} onKeyDown={press(run)}>
        <circle cx={cx} cy={cy} r={SIZE.toggle * U} />
        <text x={cx} y={cy + 3.6} fontSize={FONT.toggle} textAnchor="middle">{busy ? "…" : open ? "−" : "+"}</text>
        {t.error && (
          <text className="sc-flow-error" role="alert" x={t.side === "right" ? cx + 10 : cx - 10} y={cy + 16} fontSize={8.5} textAnchor={t.side === "right" ? "start" : "end"}>
            {t.error}
          </text>
        )}
      </g>
    );
  };

  return (
    <div ref={wrap} className="sc-flow" data-testid="flow-scroll" data-zoom={Math.round(zoom * 100)}>
      <div ref={canvas} className="sc-flow-canvas">
        <svg ref={svg} role="group" aria-label={label} viewBox={`0 0 ${layout.width * U} ${layout.height * U}`}
             style={{ width: `${layout.width * zoom}rem`, height: `${layout.height * zoom}rem` }}>
          <defs>
            <marker id="sc-flow-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path className="sc-flow-arrow" d="M1 1L9 5L1 9" />
            </marker>
          </defs>
          {layout.edges.map((e) => <path key={e.id} data-edge={e.id} className="sc-flow-edge" d={pathOf(e.cmds)} markerEnd={e.arrow ? "url(#sc-flow-arrow)" : undefined} />)}
          {/* etiketler çizgilerin üstünde ve zeminli: üstünden geçen dal yazıyı kesmez */}
          {layout.labels.map((e) => (
            <g key={e.id} data-edge-label={e.id}>
              {e.label && <text className="sc-flow-edge-label" x={e.x * U} y={e.y * U} fontSize={FONT.edge} textAnchor={e.anchor}>{e.label}</text>}
              {e.note && <text className="sc-flow-edge-label sc-flow-edge-note" x={e.x * U} y={e.y * U + 15.5} fontSize={FONT.edgeNote} textAnchor={e.anchor}>{e.note}</text>}
            </g>
          ))}
          {layout.nodes.map(node)}
          {layout.toggles.map(toggle)}
        </svg>
      </div>
    </div>
  );
}
