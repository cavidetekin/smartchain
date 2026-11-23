// Kapasite yönetimi › Geçerlilik görünümü (7.9c, K-188; docs/12 "Kapasite yönetimi"; mockup plans/7.9-mockups/gecerlilik.html ve
// zaman-cubugu-renk.html, seçenek B). Çalışma düzeni, Verimlilik ve Ek mesai limitleri'nde tablo seçimi "Kayıtlar · Geçerlilik": Geçerlilik her
// kaynak için hangi aralıkta hangi değerin uygulandığını ve hangi kayıttan geldiğini gösterir. Üstte zaman çubuğu (senaryonun planlama ufku), altta
// ortak tablo; aradaki tutamaç sürüklenir. Zaman çubuğu tabloda yüklenen satırları çizer (süzme ve sıralamayla aynı); ayrı bir hesap yoktur. Hücre
// düzenleme yoktur (satırlar hesaplanmış aralıktır); sağ tıkta Düzenle (aralığın geldiği kayıt), Yeni kayıt (o kaynak seçili) ve Kayda git.
import { type MouseEvent as ReactMouseEvent, type ReactNode, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { getJson } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { DataTable, type FieldHints } from "../table/DataTable";
import { ABOVE_MAX_ZOOM, listApi, type ListFilter, type Row, setListScenario } from "../table/types";
import { type MenuAction, MenuActions, RowPopMenu } from "../ui/PopMenu";
import { CapacityEntryDialog } from "./CapacityEntryDialog";
import { ENTRIES, type EntryKind, type EntrySpec, ORIGIN_DIFF, type Owner } from "./capacityModel";

const T = tr.capacity;
const LOCATION_HINT: FieldHints = { LocationCode: { width: 6.5 } };   // Lokasyon kodu dar kolon (K-189)
const DAY = 86_400_000;
const MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
const ZOOMS = [1, 1.5, 2, 3, 4, 6, 8, ABOVE_MAX_ZOOM];   // − ve + düğmelerinin basamakları
const WHEEL_STEP = 1.2;                                   // Ctrl + tekerleğin bir adımı
const LEVEL_RESOURCE = "Kaynak";
const LABEL_REM = 9;                                      // soldaki kaynak kolonunun genişliği (components.css ile aynı)

export type TableView = "kayitlar" | "gecerlilik";
/** Geçerlilik görünümü olan girişler: liste, zaman çubuğunda yazılan değer ve ipucundaki adı. percent: "%110" biçiminde yazılır (verimlilik). */
export const VALIDITY: Partial<Record<EntryKind, { list: string; value: string; decimals: number; label: string; percent?: boolean }>> = {
  "work-patterns": { list: "capacity-work-patterns-validity", value: "DailyCapacity", decimals: 2, label: T.dailyCapacity },
  efficiency: { list: "capacity-efficiency-validity", value: "EfficiencyPct", decimals: 2, label: T.view.efficiency, percent: true },
  "overtime-limits": { list: "capacity-overtime-limits-validity", value: "DailyLimit", decimals: 2, label: T.dailyLimit },
};

/** Sekmelerin yanındaki tablo seçimi (Kayıtlar · Geçerlilik). */
export function TableChoice({ value, onChange }: { value: TableView; onChange(v: TableView): void }) {
  return (
    <select className="sc-input sc-select sc-table-choice" aria-label={T.view.label} value={value} onChange={(e) => onChange(e.target.value as TableView)}>
      <option value="kayitlar">{T.view.records}</option>
      <option value="gecerlilik">{T.view.validity}</option>
    </select>
  );
}

interface Horizon { start: string; end: string }
/** "yyyy-aa-gg" → gün numarası (saat diliminden bağımsız) ve "gg.aa.yyyy". */
const dayOf = (iso: string) => { const [y, m, d] = iso.slice(0, 10).split("-").map(Number); return Math.round(Date.UTC(y, m - 1, d) / DAY); };
const trDate = (iso: string) => { const [y, m, d] = iso.slice(0, 10).split("-"); return `${d}.${m}.${y}`; };
const pct = (n: number) => `${(n * 100).toFixed(3)}%`;
/** Yüzde yazımı: "%110", "%87,5" (gereksiz ondalık yazılmaz). */
const percentText = (value: number) => `%${formatNumber(value, Number.isInteger(value) ? 0 : Number.isInteger(value * 10) ? 1 : 2)}`;
const clampZoom = (zoom: number) => Math.min(ABOVE_MAX_ZOOM, Math.max(1, Math.round(zoom * 100) / 100));

interface Segment { row: Row; left: number; width: number; text: string; lines: string[]; tone: SpanTone; outline: boolean; top: boolean }
/** Dilimin tonu (zaman çubuğunun kendi renkleri): nane, amber, mercan (K-193: iki tedarik biçimi birden). */
export type SpanTone = "group" | "own" | "both";
interface Line { key: string; code: string; title: string; segments: Segment[] }
/** Bir satırın zaman çubuğundaki yeri ve yazımı (sahipten bağımsız kullanım, K-191). key: satırın anahtarı; code: solda yazan ad; text: dilimde
 *  yazan; own: amber dilim (değilse nane); tone: verilirse ton (own'un yerine); outline: dolgusuz, çerçeveli dilim (K-193: blokajlı ama açık kalan
 *  dönem); top: üstte çizilir (ör. kapanış, üst limitin üstünde); lines: ipucunun satırları. */
export interface SpanInfo { key: string; code: string; title: string; text: string; own: boolean; tone?: SpanTone; outline?: boolean; top?: boolean; lines: string[] }
/** Geçerlilik görünümünün sahipten bağımsız tanımı (K-191: tedarikçi limiti). */
export interface ValidityCustom {
  list: string; entry: EntrySpec;
  /** Soldaki kolonun başlığı ("Kaynak", "Tedarikçi · Malzeme") ve genişliği (rem; verilmezse kaynak kodunun genişliği). */
  corner: string; labelRem?: number;
  /** Geçerlilik tablosunun kolon genişlikleri (rem). */
  hints?: FieldHints;
  describe(row: Row): SpanInfo;
  /** Zaman çubuğu için satırları birleştirir (K-193: dönemin iki tedarik biçimi tek dilim); dönen satırlar `ValidFrom` ve `ValidTo` taşır. */
  merge?(rows: Row[]): Row[];
  /** Aralığın geldiği kaydı Kayıtlar listesinde bulmak için sahip süzmesi (`OwnerKeys` değeri). */
  ownerKey(row: Row): string;
  /** "Yeni kayıt"ta dolu gelen sahip. */
  newOwner(row: Row): Owner;
  /** Satır menüsünün erişilebilir adı. */
  label(row: Row): string;
}

/** Zaman çubuğu: her kaynak bir satır, her aralık bir dilim; ufkun dışı kesilir, kayıt olmayan aralık boş kalır. Renk (zaman çubuğunun kendi
 *  renkleri): nane grubun kaydı, amber kaynağın kendi kaydı. Başlık satırı (Kaynak, aylar) ve kaynak listesi kaydırırken sabittir; − ve + ya da
 *  Ctrl + fare tekerleği çubuğu yatayda yakınlaştırır (tekerlekte imlecin altındaki tarih yerinde kalır). */
export function ValidityTimeline({ rows, horizon, value, decimals, label, percent, zoom, onZoom, picked, onPick, onMenu, describe, corner, labelRem = LABEL_REM }: {
  rows: Row[]; horizon: Horizon; value: string; decimals: number; label: string; percent?: boolean;
  /** Sahipten bağımsız kullanım (K-191): satırın çubuktaki yeri ve yazımı; verilmezse kapasite girişinin (kaynak, değer) yazımı. */
  describe?(row: Row): SpanInfo; corner?: string; labelRem?: number;
  zoom: number; onZoom(zoom: number): void;
  picked?: number | null; onPick?(row: Row): void; onMenu?(row: Row, anchor: HTMLElement): void;
}) {
  const model = useMemo(() => {
    const start = dayOf(horizon.start), end = dayOf(horizon.end);
    const total = end - start + 1;
    if (!(total > 0)) return null;
    const lines = new Map<string, Line>();
    // Veride birden çok lokasyon varsa soldaki kaynak kodu lokasyonla yazılır ("ORM-01 · T-01"; K-189)
    const manyLocations = new Set(rows.map((r) => r.LocationCode).filter(Boolean)).size > 1;
    for (const row of rows) {
      const from = Math.max(dayOf(String(row.ValidFrom)), start);
      const to = Math.min(row.ValidTo ? dayOf(String(row.ValidTo)) : end, end);
      const custom = describe?.(row);
      const key = custom?.key ?? `${row.ResourceGroupId}|${row.ResourceId}`;
      const code = custom?.code ?? (manyLocations && row.LocationCode ? `${String(row.LocationCode)} · ${String(row.Code ?? "")}` : String(row.Code ?? ""));
      const title = custom?.title ?? `${code} · ${String(row.GroupCode ?? "")}`;
      let line = lines.get(key);
      if (!line) {
        line = { key, code, title, segments: [] };
        lines.set(key, line);
      }
      if (to < from) continue;
      if (custom) {
        line.segments.push({ row, left: (from - start) / total, width: (to - from + 1) / total, text: custom.text, tone: custom.tone ?? (custom.own ? "own" : "group"),
                             outline: Boolean(custom.outline), top: Boolean(custom.top), lines: custom.lines });
        continue;
      }
      const own = row.SourceLevel === LEVEL_RESOURCE;
      const number = Number(row[value]);
      const text = percent ? percentText(number) : formatNumber(number, decimals);
      const unit = percent || !row.CapacityUnit ? "" : ` ${String(row.CapacityUnit)}`;
      const range = row.ValidTo ? `${trDate(String(row.ValidFrom))} – ${trDate(String(row.ValidTo))}` : T.view.since(trDate(String(row.ValidFrom)));
      line.segments.push({ row, left: (from - start) / total, width: (to - from + 1) / total, text, tone: own ? "own" : "group", outline: false, top: false,
                           lines: [title, `${label}: ${text}${unit}`, range, own ? T.view.ownRecord : T.view.groupRecord,
                                   ...(row.SourceOrigin === ORIGIN_DIFF ? [T.view.scenarioDiff] : [])] });
    }
    // ay ekseni: ufkun kestiği aylar, ufuktaki payıyla
    const months: { key: string; label: string; left: number; width: number }[] = [];
    const first = new Date(start * DAY), last = new Date(end * DAY);
    for (let y = first.getUTCFullYear(), m = first.getUTCMonth(); y < last.getUTCFullYear() || (y === last.getUTCFullYear() && m <= last.getUTCMonth()); m === 11 ? (y++, m = 0) : m++) {
      const a = Math.max(Math.round(Date.UTC(y, m, 1) / DAY), start), b = Math.min(Math.round(Date.UTC(y, m + 1, 0) / DAY), end);
      if (b >= a) months.push({ key: `${y}-${m}`, label: `${MONTHS[m]} ${y}`, left: (a - start) / total, width: (b - a + 1) / total });
    }
    for (const line of lines.values()) line.segments.sort((a, b) => Number(a.top) - Number(b.top));   // üstte çizilecek dilim sonda
    return { lines: [...lines.values()], months };
  }, [rows, horizon, value, decimals, label, percent, describe]);

  // Dilime ya da ay hücresine sığmayan yazı yazılmaz (ipucunda görünür). Yakınlaştırılmış uzun dilimde değer dilimin görünen kısmının ortasında
  // durur (dilimin ortası ekran dışındaysa kaydırılır). Her çizimde, kaydırınca ve boyut değişince ölçülür.
  const box = useRef<HTMLDivElement>(null);
  const fit = useCallback(() => {
    const el = box.current;
    if (!el) return;
    const frame = el.getBoundingClientRect();
    const viewLeft = frame.left + (el.querySelector<HTMLElement>(".sc-validity-corner")?.offsetWidth ?? 0), viewRight = frame.left + el.clientWidth;
    const monthRight = viewRight - (el.querySelector<HTMLElement>(".sc-validity-zooms")?.offsetWidth ?? 0);   // başlık satırının sağ ucunda düğmeler var
    el.querySelectorAll<HTMLElement>(".sc-validity-chip, .sc-validity-month").forEach((cell) => {
      const text = cell.firstElementChild as HTMLElement | null;
      if (!text) return;
      const r = cell.getBoundingClientRect();
      const a = Math.max(r.left, viewLeft), b = Math.min(r.right, cell.classList.contains("sc-validity-month") ? monthRight : viewRight);
      const partly = r.width > 0 && b > a && (a > r.left || b < r.right);   // bir kısmı görünen alanın dışında
      const room = partly ? b - a : cell.clientWidth;
      if (text.offsetWidth > room - 4) cell.dataset.tight = "1";
      else delete cell.dataset.tight;
      text.style.transform = partly ? `translateX(${((a + b) / 2 - (r.left + r.right) / 2).toFixed(1)}px)` : "";
    });
  }, []);
  useLayoutEffect(fit);
  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    el.addEventListener("scroll", fit, { passive: true });
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(fit);
    observer?.observe(el);
    return () => { el.removeEventListener("scroll", fit); observer?.disconnect(); };
  }, [fit]);

  // Ctrl + fare tekerleği: yakınlaştırır; imlecin altındaki tarih yerinde kalır (yeni genişlikte aynı oran imlecin altına kaydırılır). Düz tekerlek
  // kutuyu dikey kaydırır (tarayıcının kendi davranışı). Dinleyici pasif olmamalı: Ctrl + tekerlek sayfayı büyütmesin.
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;
  const anchor = useRef<{ ratio: number; offset: number } | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const label = el.querySelector<HTMLElement>(".sc-validity-corner")?.offsetWidth ?? 0;
      const track = el.querySelector<HTMLElement>(".sc-validity-axis")?.offsetWidth ?? 0;
      const next = clampZoom(zoomRef.current * (e.deltaY < 0 ? WHEEL_STEP : 1 / WHEEL_STEP));
      if (next === zoomRef.current) return;
      const offset = e.clientX - el.getBoundingClientRect().left - label;   // imlecin, çubuğun görünen kısmının başına uzaklığı
      if (track > 0) anchor.current = { ratio: (el.scrollLeft + offset) / track, offset };
      onZoom(next);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [onZoom]);
  useLayoutEffect(() => {
    const el = box.current, kept = anchor.current;
    if (!el || !kept) return;
    anchor.current = null;
    const track = el.querySelector<HTMLElement>(".sc-validity-axis")?.offsetWidth ?? 0;
    el.scrollLeft = Math.max(0, kept.ratio * track - kept.offset);
  }, [zoom]);

  if (!model) return null;
  const smaller = [...ZOOMS].reverse().find((z) => z < zoom - 0.001), larger = ZOOMS.find((z) => z > zoom + 0.001);
  return (
    <div className="sc-validity" role="group" aria-label={T.view.timeline} ref={box}>
      {/* Izgaranın genişliği içeriği kadardır (kaynak kolonu + yakınlaştırılmış çubuk): sabit kolon, kapsayıcısı ızgara olduğu için, yatay
          kaydırmanın sonuna kadar yerinde kalır. Genişlik kutunun genişliğinde kalsaydı kolon o genişlik bitince kayardı. */}
      <div className="sc-validity-grid" data-zoom={zoom}
           style={{ width: `calc(${labelRem}rem + (100% - ${labelRem}rem) * ${zoom})`, ["--validity-label" as string]: `${labelRem}rem` }}>
        <div className="sc-validity-corner"><b>{corner ?? T.resource}</b></div>
        <div className="sc-validity-axis">
          {model.months.map((m) => <span key={m.key} className="sc-validity-month" aria-hidden="true" title={m.label} style={{ left: pct(m.left), width: pct(m.width) }}><b>{m.label}</b></span>)}
          <span className="sc-validity-zooms">
            <button type="button" className="sc-validity-zoom" aria-label={T.view.zoomOut} title={T.view.zoomOut} disabled={smaller === undefined} onClick={() => onZoom(smaller!)}>−</button>
            <button type="button" className="sc-validity-zoom" aria-label={T.view.zoomIn} title={T.view.zoomIn} disabled={larger === undefined} onClick={() => onZoom(larger!)}>+</button>
          </span>
        </div>
        {model.lines.map((line) => (
          <div className="sc-validity-line" key={line.key}>
            <span className="sc-validity-label" title={line.title}>{line.code}</span>
            <div className="sc-validity-bar" role="group" aria-label={line.title}>
              {model.months.slice(1).map((m) => <i key={m.key} className="sc-validity-tick" style={{ left: pct(m.left) }} aria-hidden="true" />)}
              {line.segments.map((s) => (
                <button type="button" key={String(s.row.Id)} title={s.lines.join("\n")} aria-label={s.lines.join(", ")} aria-pressed={picked === s.row.Id}
                        className={`sc-validity-span is-${s.tone}${s.outline ? " is-outline" : ""}${picked === s.row.Id ? " is-picked" : ""}`}
                        style={{ left: pct(s.left), width: pct(s.width) }} onClick={() => onPick?.(s.row)}
                        onContextMenu={(e: ReactMouseEvent<HTMLElement>) => { if (!onMenu) return; e.preventDefault(); onMenu(s.row, e.currentTarget); }}>
                  <span className="sc-validity-chip"><b>{s.text}</b></span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Geçerlilik tablosu ve üstünde zaman çubuğu. Hücre düzenleme, satır menüsü düğmesi ve kart yok; sağ tıkta Düzenle ve Yeni kayıt (yazma yetkisi
 *  olanda) ve Kayda git. */
export function ValidityView({ kind, custom, filters, lead, end, compact, reloadKey = 0, onChanged, onGoToRecord }: {
  /** Kapasite girişi; sahipten bağımsız kullanımda `custom` verilir (K-191). */
  kind?: EntryKind; custom?: ValidityCustom;
  filters?: ListFilter[]; lead?: ReactNode; end?: ReactNode; compact?: boolean; reloadKey?: number;
  /** Kayıt düzenlendi ya da eklendi (öteki tablolar yenilensin). */
  onChanged?(): void;
  /** "Kayda git": Kayıtlar'a geçilir, kayıt seçili gösterilir. */
  onGoToRecord?(recordId: number): void;
}) {
  const { scenario } = useShell();
  const { me } = useAuth();
  const entry = custom?.entry ?? ENTRIES[kind!];
  const write = Boolean(me && can(me, entry.adapter?.writeFunction ?? 24, "write"));
  const spec = custom ? { list: custom.list, value: "", decimals: 0, label: "", percent: false } : VALIDITY[kind!]!;
  const DialogView = entry.adapter?.Dialog ?? CapacityEntryDialog;
  const sid = scenario?.id ?? 0;
  const [horizon, setHorizon] = useState<Horizon | null>(null);
  const [picked, setPicked] = useState<{ id: number; n: number } | null>(null);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement } | null>(null);
  const [dialog, setDialog] = useState<{ row: Row | null; owner: Owner | null } | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const ctrl = new AbortController();
    setHorizon(null);
    getJson<{ start: string | null; end: string | null }>(`/api/capacity/horizon?scenario_id=${sid}`, ctrl.signal)
      .then((h) => { if (h.start && h.end) setHorizon({ start: h.start, end: h.end }); })
      .catch(() => undefined);   // ufuk okunamazsa tablo yine çalışır; zaman çubuğu çizilmez
    return () => ctrl.abort();
  }, [sid]);

  /** Aralığın geldiği kayıt (Kayıtlar listesindeki satırı): Düzenle penceresi bu satırla açılır. */
  const openEdit = async (row: Row) => {
    setListScenario(entry.list, sid);
    const owner = custom ? custom.ownerKey(row) : row.SourceLevel === LEVEL_RESOURCE ? `,r${row.ResourceId},` : `,g${row.ResourceGroupId},`;
    try {
      // İstenen alanlar listenin kendi kolonlarıdır: girişlerin alanları aynı değildir (Verimlilik'te "Birim" yok; olmayan alan isteği reddettirir)
      const fields = (await listApi(entry.list).columns()).columns.map((c) => c.field);
      for (let offset = 0; ; offset += 100) {
        const page = await listApi(entry.list).query({ offset, limit: 100, sort: [{ field: entry.start, dir: "asc" }], fields,
                                                       filters: [{ field: "OwnerKeys", op: "contains", value: owner }] });
        const found = page.rows.find((r) => r.Id === row.SourceRowId);
        if (found) { setDialog({ row: found, owner: null }); return; }
        if (page.rows.length < 100) return;
      }
    } catch (err) {
      console.error("Geçerlilik › Düzenle: kayıt okunamadı", err);   // sessiz kalmasın: pencere açılmıyorsa nedeni konsolda
    }
  };
  // Yeni kayıt: pencere aralığın kaynağı seçili açılır; seviye ve kod pencerede değiştirilebilir
  const openNew = (row: Row) => setDialog({ row: null, owner: custom ? custom.newOwner(row) : { level: "resource", id: Number(row.ResourceId), code: String(row.Code ?? "") } });
  const items = (row: Row): MenuAction[] => [
    ...(write ? [{ label: T.menu.edit, onClick: () => void openEdit(row) }, { label: T.menu.add, onClick: () => openNew(row) }] : []),
    ...(onGoToRecord ? [{ label: T.view.goToRecord, onClick: () => onGoToRecord(Number(row.SourceRowId)) }] : []),
  ];
  const onZoomOf = useRef<(zoom: number) => void>(() => undefined);
  const onZoom = useCallback((zoom: number) => onZoomOf.current(zoom), []);   // kimliği sabit: tekerlek dinleyicisi her çizimde yeniden bağlanmaz

  return (
    <>
      <DataTable list={spec.list} baseFilters={filters} toolbarLead={lead} toolbarEnd={end} compact={compact} fieldHints={custom?.hints ?? LOCATION_HINT} reloadKey={reloadKey + tick}
                 cellMenu={(_col, row) => items(row)} selectedRowId={picked?.id ?? null} reveal={picked}
                 above={horizon ? (rows, pane) => {
                   onZoomOf.current = pane.setZoom;
                   return (
                     <ValidityTimeline rows={custom?.merge ? custom.merge(rows) : rows} horizon={horizon} value={spec.value} decimals={spec.decimals} label={spec.label} percent={spec.percent}
                                       zoom={pane.zoom} onZoom={onZoom} picked={picked?.id ?? null} describe={custom?.describe} corner={custom?.corner} labelRem={custom?.labelRem}
                                       onPick={(row) => setPicked((cur) => ({ id: row.Id, n: (cur?.n ?? 0) + 1 }))}
                                       onMenu={(row, anchor) => { if (items(row).length) setMenu({ row, anchor }); }} />
                   );
                 } : undefined} />
      {menu && (
        <RowPopMenu label={T.rowActions(custom ? custom.label(menu.row) : String(menu.row.Code ?? ""))} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuActions items={items(menu.row)} onDone={() => setMenu(null)} end={false} />
        </RowPopMenu>
      )}
      {dialog && (
        <DialogView spec={entry} scenario={sid} row={dialog.row} owner={dialog.owner} onClose={() => setDialog(null)}
                    onSaved={() => { setDialog(null); setTick((n) => n + 1); onChanged?.(); }} />
      )}
    </>
  );
}
