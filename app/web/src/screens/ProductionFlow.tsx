// Üretim akışı penceresi (K-200; ekran 03, fonksiyon 10): bir malzemenin solunda onu kullananlar, sağında onun kullandıkları; açtıkça yüklenir.
// Yalnız ürün ağacı verisi (plan, senaryo, stok yok); salt okunur. Kapalı açılır. Çizim ortak bileşendir (ui/flow, docs/12 "Akış çizimi standardı").
// Aynı malzeme iki yoldan açılırsa iki ayrı kutudur: düğümün kimliği yoludur. Yüklenen veri malzeme başına saklanır; kapatılıp açılan dal
// yeniden istenmez. Bir basışta 20'den çok kutu gelecekse ilk 20 ve "+N malzeme" kutusu; basınca kalanı açılır (200'den çoksa 200'er).
// Kutu malzeme seviyesine göre renklidir (hayalet gri); alternatif grubu üyesi "veya G1" etiketi taşır. Başlıkta yakınlaştırma, PNG indirme
// (açık çizimin tamamı; izi yazılır, K-108) ve "Tümünü kapat"; alt satırda renk açıklaması ve "Kapat".
import { Download, Scan, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, emitNotice, saveBlob } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { Alert, Button, Dialog } from "../ui";
import { type FlowApi, FlowDiagram, ZOOM_STEPS } from "../ui/flow/FlowDiagram";
import type { BranchState, FlowBranch, FlowModel, FlowNode, FlowSide } from "../ui/flow/flowLayout";
import { type FlowAlternative, type FlowComponents, type FlowItem, type FlowMaterial, type FlowParent, type FlowRoot, productionFlowApi } from "./productionFlowApi";

const T = tr.productionFlow;
export const FIRST = 20;     // bir basışta açılan en çok kutu
export const STEP = 200;     // "+N malzeme" basışında açılan en çok kutu

/** Malzeme seviyesi → kutunun tonu (docs/12; tokens.css --flow-<ton>-*). */
const LEVEL_TONE: Record<string, string> = { "Nihai ürün": "final", "Yarı mamul": "semi", Hammadde: "raw" };
/** Kutunun tonu: hayalet seviyesinin renginde değil gri; seviyesi bilinmeyen nötr. */
export const toneOf = (m: FlowMaterial): string | undefined => (m.phantom ? "phantom" : m.level ? LEVEL_TONE[m.level] : undefined);
/** Renk açıklaması (ekranda ve PNG'de aynı sıra). */
export const LEGEND: { label: string; tone: string }[] = [
  { label: T.keyCurrent, tone: "current" }, { label: "Nihai ürün", tone: "final" }, { label: "Yarı mamul", tone: "semi" }, { label: "Hammadde", tone: "raw" },
  { label: T.keyPhantom, tone: "phantom" }, { label: T.keyOption, tone: "option" },
];

interface Open { state: BranchState; shown: number; error?: string }
interface Parents { total: number; items: FlowParent[] }
/** Düğümün arkasındaki kayıt: çizim bileşeni bilmez, pencere olayda buradan bulur. */
interface Meta { material?: FlowMaterial; alternative?: FlowAlternative; owner?: number; side: FlowSide }
interface EdgeText { edge?: string; edgeNote?: string }

/** Miktar: en çok altı ondalık, gereksiz sıfırsız, Türkçe biçimde. */
export function quantityText(value: number, uom: string | null): string {
  const digits = Math.min(6, (String(Number(value.toFixed(6))).split(".")[1] ?? "").length);
  return `×${formatNumber(value, digits)}${uom ? ` ${uom}` : ""}`;
}

/** Kullananın okundaki yazı: üstte miktar; altta üst malzemenin birden çok alternatifi varsa hangilerinde kullanıldığı.
 *  Miktar alternatife göre değişiyorsa ayrı ayrı yazılır (ilki üstte, kalanı altta). */
export function parentEdge(p: FlowParent): EdgeText {
  if (!p.uses.length) return {};
  const texts = p.uses.map((u) => quantityText(u.quantity, u.uom));
  if (p.alternatives <= 1) return { edge: texts[0] };
  if (new Set(texts).size === 1) return { edge: texts[0], edgeNote: T.alternatives(p.uses.map((u) => u.alternative).join(", ")) };
  const each = p.uses.map((u, i) => `${texts[i]} ${T.alternativeShort(u.alternative)}`);
  return { edge: each[0], edgeNote: each.slice(1).join(" · ") };
}

export function ProductionFlow({ materialId, onClose }: { materialId: number; onClose(): void }) {
  const [rootId, setRootId] = useState(materialId);
  const [root, setRoot] = useState<FlowRoot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, Open>>({});
  const [anchor, setAnchor] = useState<string | null>(null);
  const [center, setCenter] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [saving, setSaving] = useState(false);
  const [, setLoaded] = useState(0);                          // saklanan veri değişince yeniden çiz
  const components = useRef(new Map<number, FlowComponents>());
  const parents = useRef(new Map<number, Parents>());
  const meta = useRef(new Map<string, Meta>());
  const picked = useRef(false);                               // seçili malzeme pencerenin içinden değişti: odak yeni seçili kutuya
  const flow = useRef<FlowApi>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setRoot(null);
    setError(null);
    productionFlowApi.read(rootId, ctrl.signal).then(setRoot)
      .catch((e: unknown) => { if (!ctrl.signal.aborted) setError(e instanceof ApiError && e.status === 404 ? T.notFound : e instanceof Error ? e.message : T.failed); });
    return () => ctrl.abort();
  }, [rootId]);

  const model = useMemo<FlowModel | null>(() => {
    if (!root) return null;
    const found = new Map<string, Meta>();
    const lines = (m: FlowMaterial) => ({ title: m.code, text: m.name ?? undefined, meta: [m.level, m.phantom ? T.phantom : null].filter(Boolean).join(" · ") || undefined, tone: toneOf(m) });
    const box = (id: string, m: FlowMaterial, side: FlowSide, edge: EdgeText, badge?: string): FlowNode => {
      found.set(id, { material: m, side });
      return { id, kind: "box", ...lines(m), badge, ...edge };
    };
    const more = (id: string, left: number, side: FlowSide, owner: number): FlowNode => {
      found.set(`${id}/+`, { side, owner });
      return { id: `${id}/+`, kind: "more", title: T.more(formatNumber(left)) };
    };
    const items = (id: string, list: FlowItem[], shown: number, owner: number): FlowNode[] => {
      const nodes = list.slice(0, shown).map((i) => {
        const child = `${id}/${i.material.id}`;
        // alternatif grubu üyesi (K-200): okta değil, kutunun köşesinde "veya G1"; aynı etiketi taşıyanlar birbirinin yerine geçer
        return { ...box(child, i.material, "right", { edge: quantityText(i.quantity, i.uom) }, i.group ? T.orGroup(i.group) : undefined), branch: right(child, i.material) };
      });
      return list.length > shown ? [...nodes, more(id, list.length - shown, "right", owner)] : nodes;
    };
    const right = (id: string, m: FlowMaterial): FlowBranch => {
      if (!m.has_components) return { state: "none" };
      const o = open[id];
      const data = components.current.get(m.id);
      if (!o || o.state !== "open" || !data) return { state: o?.state === "open" ? "closed" : o?.state ?? "closed", error: o?.error };
      if (data.alternatives.length === 1) return { state: "open", children: items(id, data.alternatives[0].items, o.shown, m.id) };
      return {
        state: "open",
        children: data.alternatives.map((a) => {
          const child = `${id}/a${a.no}`;
          const ao = open[child];
          found.set(child, { alternative: a, side: "right", owner: m.id });
          return { id: child, kind: "option" as const, title: T.alternative(a.no), text: a.versions.join(", "),
                   branch: a.items.length === 0 ? { state: "none" as const } : ao?.state === "open" ? { state: "open" as const, children: items(child, a.items, ao.shown, m.id) } : { state: "closed" as const } };
        }),
      };
    };
    const left = (id: string, m: FlowMaterial): FlowBranch => {
      if (!m.has_parents) return { state: "none" };
      const o = open[id];
      const data = parents.current.get(m.id);
      if (!o || o.state !== "open" || !data) return { state: o?.state === "open" ? "closed" : o?.state ?? "closed", error: o?.error };
      const nodes = data.items.slice(0, o.shown).map((p) => {
        const child = `${id}/${p.material.id}`;
        return { ...box(child, p.material, "left", parentEdge(p)), branch: left(child, p.material) };
      });
      const rest = data.total - nodes.length;
      return { state: "open", children: rest > 0 ? [...nodes, more(id, rest, "left", m.id)] : nodes };
    };
    found.set("d", { material: root.material, side: "right" });
    found.set("u", { material: root.material, side: "left" });
    const result = { root: { id: "d", kind: "box" as const, ...lines(root.material) }, left: left("u", root.material), right: right("d", root.material) };
    meta.current = found;
    return result;
  }, [root, open]);  // eslint-disable-line react-hooks/exhaustive-deps

  const fail = (e: unknown) => (e instanceof Error && e.message ? e.message : T.failed);
  const set = (id: string, next: Open) => setOpen((o) => ({ ...o, [id]: next }));

  /** Kök kutuda iki yön ayrı kimlik taşır: sağ "d", sol "u". */
  const key = (node: FlowNode, side: FlowSide) => (node.id === "d" && side === "left" ? "u" : node.id);

  const toggle = useCallback((node: FlowNode, side: FlowSide) => {
    const id = key(node, side);
    const m = meta.current.get(id);
    if (!m) return;
    setAnchor(node.id);
    const current = open[id];
    if (current?.state === "busy") return;
    if (current?.state === "open") { set(id, { ...current, state: "closed" }); return; }
    if (m.alternative) { set(id, { state: "open", shown: current?.shown ?? FIRST }); return; }
    const material = m.material;
    if (!material) return;
    const cache = side === "right" ? components.current : parents.current;
    if (cache.has(material.id)) { set(id, { state: "open", shown: current?.shown ?? FIRST }); return; }
    set(id, { state: "busy", shown: FIRST });
    const load = side === "right" ? productionFlowApi.components(material.id).then((d) => { components.current.set(material.id, d); })
                                  : productionFlowApi.parents(material.id, 0, FIRST).then((d) => { parents.current.set(material.id, d); });
    load.then(() => { setLoaded((n) => n + 1); set(id, { state: "open", shown: FIRST }); })
      .catch((e: unknown) => set(id, { state: "error", shown: FIRST, error: fail(e) }));
  }, [open]);

  /** "+N malzeme": kalanı açar (200'den çoksa 200'er); kullananlarda eksik sayfa sunucudan istenir. */
  const showMore = useCallback((node: FlowNode) => {
    const id = node.id.slice(0, -2);        // dalın kimliği ("+N" kutusunun yolu eksi "/+")
    const m = meta.current.get(node.id);
    const current = open[id];
    if (!m || !current || m.owner === undefined) return;
    setAnchor(node.id);
    const shown = current.shown + STEP;
    const data = parents.current.get(m.owner);
    if (m.side === "right" || !data || data.items.length >= Math.min(shown, data.total)) { set(id, { ...current, shown }); return; }
    productionFlowApi.parents(m.owner, data.items.length, Math.min(STEP, data.total - data.items.length))
      .then((d) => { parents.current.set(m.owner as number, { total: d.total, items: [...data.items, ...d.items] }); setLoaded((n) => n + 1); set(id, { ...current, shown }); })
      .catch((e: unknown) => set(id, { ...current, state: "error", error: fail(e) }));
  }, [open]);

  const restart = () => { setOpen({}); setAnchor(null); setCenter((n) => n + 1); };
  const pick = useCallback((node: FlowNode) => {
    const m = meta.current.get(node.id)?.material;
    if (!m) return;
    restart();
    picked.current = true;
    setRootId(m.id);
  }, []);

  const headline = root ? [root.material.code, root.material.name, T.location(root.location)].filter(Boolean).join(" · ") : "";
  // Benzetilen notu (K-200): yalnız seçili malzeme benzetilen ürünse, başlığın altında kalın; çizimin içinde not yok
  const note = root?.reference ? T.reference(root.reference.code) : undefined;

  /** PNG: açık çizimin tamamı (ekranda görünen kısım değil). Görsel tarayıcıda üretilir; izi yazılamazsa dosya inmez (K-108). */
  const download = async () => {
    const layout = flow.current?.layout();
    if (!layout || !root || saving) return;
    setSaving(true);
    try {
      const { flowPng } = await import("../ui/flow/flowImage");
      const image = await flowPng(layout, { title: headline, note, legend: LEGEND });
      const { file_name } = await productionFlowApi.exportLog(root.material.id);
      saveBlob(image, file_name);
    } catch (e) {
      emitNotice(e instanceof ApiError ? e.message : T.downloadFailed);
    } finally {
      setSaving(false);
    }
  };

  const tools = (
    <div className="sc-flow-tools">
      <span className="sc-flow-zoom" aria-live="polite">{T.zoomLevel(Math.round(zoom * 100))}</span>
      <button type="button" className="sc-tool-btn" aria-label={T.zoomOut} title={T.zoomOut} disabled={!model || zoom <= ZOOM_STEPS[0] + 0.001}
              onClick={() => flow.current?.zoomOut()}><ZoomOut aria-hidden="true" /></button>
      <button type="button" className="sc-tool-btn" aria-label={T.zoomIn} title={T.zoomIn} disabled={!model || zoom >= ZOOM_STEPS[ZOOM_STEPS.length - 1] - 0.001}
              onClick={() => flow.current?.zoomIn()}><ZoomIn aria-hidden="true" /></button>
      <button type="button" className="sc-tool-btn" aria-label={T.zoomFit} title={T.zoomFit} disabled={!model} onClick={() => flow.current?.fit()}><Scan aria-hidden="true" /></button>
      <button type="button" className="sc-tool-btn sc-tool-btn--text" aria-label={T.zoomResetTitle} title={T.zoomResetTitle} disabled={!model || Math.abs(zoom - 1) < 0.001}
              onClick={() => flow.current?.reset()}>{T.zoomReset}</button>
      <button type="button" className="sc-tool-btn" aria-label={T.download} title={T.download} disabled={!model || saving} aria-busy={saving || undefined}
              onClick={() => void download()}><Download aria-hidden="true" /></button>
      <Button onClick={restart} disabled={!Object.values(open).some((o) => o.state !== "closed")}>{T.closeAll}</Button>
    </div>
  );
  const legend = (
    <ul className="sc-flow-key" aria-label={T.key}>
      {LEGEND.map((item) => <li key={item.tone}><i className={`sc-flow-swatch sc-flow-swatch--${item.tone}`} />{item.label}</li>)}
    </ul>
  );
  const subtitle = root ? <>{headline}{note && <span className="sc-dialog-subtitle-line"><strong>{note}</strong></span>}</> : undefined;

  return (
    <Dialog title={T.title} subtitle={subtitle} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel full titleAside={tools} extraActions={legend}>
      {error && <Alert tone="error">{error}</Alert>}
      {!error && !model && <p className="sc-muted">{T.loading}</p>}
      {model && (
        <FlowDiagram model={model} label={T.title} anchor={anchor} centerKey={`${rootId}:${center}`} focusCurrent={picked.current} api={flow} onZoom={setZoom}
                     onToggle={toggle} onPick={pick} onMore={showMore}
                     labels={{ busy: T.loading, toggle: (n, side, isOpen) => (n.kind === "option" ? T.toggleOption(n.title, isOpen) : T.toggle(n.title, side, isOpen)) }} />
      )}
    </Dialog>
  );
}
