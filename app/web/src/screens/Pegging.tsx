// Parametreler › Pegging (K-201; fonksiyon 22): pegging'in sıralama ayarları. Üstte "Full pegging yöntemi"; altında iki ölçüt listesi yan yana:
// "İhtiyaç sırası" (ihtiyaçlar hangi sırayla ele alınır) ve "Arz sırası" (her ihtiyaç arzı hangi sırayla tüketir). Ölçütler yukarıdan aşağı
// uygulanır; kullanıcı yalnız sırayı ve yönlü ölçütün yönünü değiştirir (ölçüt eklenmez, silinmez). Ölçütlerin adları, yön seçenekleri ve
// ipuçları sunucudan gelir (tek tanım: app/params/pegging.py). Vazgeç ve Kaydet altta (K-166): tek Kaydet yöntemi ve iki listeyi birlikte yazar.
// Bu ayarları bugün hiçbir hesap kullanmaz (pegging Aşama 10'da).
import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { Alert, Segment, SettingsFoot, Tooltip } from "../ui";
import { type SortableItem, SortableList } from "../ui/SortableList";
import type { PeggingCriterion, PeggingData, PeggingSide } from "./parametersApi";

const T = tr.pegging;
const SIDES: PeggingSide[] = ["need", "supply"];

interface Draft { method: string; need: PeggingCriterion[]; supply: PeggingCriterion[] }
const draftOf = (d: PeggingData): Draft => ({ method: d.method.value, need: d.need, supply: d.supply });
const same = (a: PeggingCriterion[], b: PeggingCriterion[]) => a.length === b.length && a.every((x, i) => x.criterion === b[i].criterion && x.direction === b[i].direction);

export function Pegging({ api, canWrite, onDirty }: {
  api: { pegging(signal?: AbortSignal): Promise<PeggingData>; savePegging(body: { method: string; need: PeggingCriterion[]; supply: PeggingCriterion[] }): Promise<PeggingData> };
  canWrite: boolean;
  onDirty(dirty: boolean): void;
}) {
  const [data, setData] = useState<PeggingData | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.pegging(ctrl.signal).then((d) => { setData(d); setDraft(draftOf(d)); })
      .catch((e: unknown) => { if (!ctrl.signal.aborted) setError(e instanceof ApiError ? e.message : T.failed); });
    return () => ctrl.abort();
  }, [api]);

  const dirty = Boolean(data && draft && (draft.method !== data.method.value || !same(draft.need, data.need) || !same(draft.supply, data.supply)));
  useEffect(() => { onDirty(dirty); }, [dirty]);  // eslint-disable-line react-hooks/exhaustive-deps

  const items = useMemo(() => {
    const build = (side: PeggingSide): SortableItem[] => (draft?.[side] ?? []).map((c) => ({
      id: c.criterion,
      label: c.criterion,
      end: c.directions.length > 0 && c.direction !== null ? (
        // yön: parçalı seçim; seçeneğin ipucu ölçüte göre (ör. "erken önce"); ekranda açıklama yazısı yok
        <Segment<string> label={T.direction(c.criterion)} hideLabel value={c.direction}
                         onChange={(v) => setDraft((d) => (d ? { ...d, [side]: d[side].map((x) => (x.criterion === c.criterion ? { ...x, direction: v } : x)) } : d))}
                         options={c.directions.map((o) => ({ value: o.value, disabled: !canWrite, label: <Tooltip content={o.hint}><span className="sc-pegging-dir">{o.value}</span></Tooltip> }))} />
      ) : undefined,
    }));
    return { need: build("need"), supply: build("supply") };
  }, [draft, canWrite]);

  if (!data || !draft) return error ? <Alert tone="error">{error}</Alert> : <p className="sc-muted">{T.loading}</p>;

  const order = (side: PeggingSide, ids: string[]) => setDraft((d) => (d ? { ...d, [side]: ids.map((id) => d[side].find((x) => x.criterion === id)!) } : d));
  const save = () => {
    setBusy(true);
    setError(null);
    api.savePegging({ method: draft.method, need: draft.need.map(({ criterion, direction }) => ({ criterion, direction, directions: [] })),
                      supply: draft.supply.map(({ criterion, direction }) => ({ criterion, direction, directions: [] })) })
      .then((d) => { setData(d); setDraft(draftOf(d)); })
      .catch((e: unknown) => setError(e instanceof ApiError ? [e.message, ...e.details.map((x) => x.problem)].join(" ") : T.failed))
      .finally(() => setBusy(false));
  };

  return (
    <div className="sc-pegging">
      <section className="sc-settings-card sc-settings-card--wide" aria-label={T.title}>
        {/* yöntem ve iki liste tek blok: etiket ve seçenekler yan yana, listelerin sol kenarından başlar (K-201 demo) */}
        <div className="sc-pegging-method">
          <span className="sc-field-label">{data.method.label}</span>
          <Segment<string> label={data.method.label} hideLabel value={draft.method} onChange={(v) => setDraft((d) => (d ? { ...d, method: v } : d))}
                           options={data.method.options.map((o) => ({ value: o, label: o, disabled: !canWrite && o !== draft.method }))} />
        </div>
        <div className="sc-pegging-lists">
          {SIDES.map((side) => (
            <section key={side} className="sc-pegging-list" aria-label={T.lists[side]}>
              <h2 className="sc-pegging-head">{T.lists[side]}</h2>
              <SortableList label={T.lists[side]} items={items[side]} onOrder={(ids) => order(side, ids)} readOnly={!canWrite} />
            </section>
          ))}
        </div>
        <SettingsFoot dirty={dirty} busy={busy} onDiscard={() => { setDraft(draftOf(data)); setError(null); }} onSave={save} />
      </section>
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
}
