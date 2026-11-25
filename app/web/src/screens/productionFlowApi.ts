// Üretim akışı (K-200; docs/08): malzemenin kutusu, kullandıkları ve kullananları; pencere açtıkça ister.
import { getJson, postJson } from "../api/client";

export interface FlowMaterial {
  id: number; code: string; name: string | null;
  /** Malzeme seviyesi: Nihai ürün · Yarı mamul · Hammadde. */
  level: string | null;
  phantom: boolean; has_parents: boolean; has_components: boolean;
}
export interface FlowItem { material: FlowMaterial; quantity: number; uom: string | null; group: string | null; group_priority: number | null }
export interface FlowAlternative { no: number; versions: string[]; bom_code: string; items: FlowItem[] }
export interface FlowComponents { reference: { code: string } | null; alternatives: FlowAlternative[] }
export interface FlowUse { alternative: number; quantity: number; uom: string | null; group: string | null }
export interface FlowParent { material: FlowMaterial; alternatives: number; uses: FlowUse[] }
/** reference: malzeme benzetilen ürünse ağacını kullandığı ürün (başlığın altındaki not). */
export interface FlowRoot { material: FlowMaterial; location: string; reference: { code: string } | null }
export interface FlowParents { total: number; items: FlowParent[] }

const base = (id: number) => `/api/production-flow/${id}`;

export const productionFlowApi = {
  read: (id: number, signal?: AbortSignal) => getJson<FlowRoot>(base(id), signal),
  /** PNG indirmenin izi ve dosya adı (K-108): iz yazılamazsa ad dönmez, dosya inmez. */
  exportLog: (id: number) => postJson<{ file_name: string }>(`${base(id)}/export-log`, {}),
  components: (id: number) => getJson<FlowComponents>(`${base(id)}/components`),
  parents: (id: number, offset: number, limit: number) => getJson<FlowParents>(`${base(id)}/parents?offset=${offset}&limit=${limit}`),
};
