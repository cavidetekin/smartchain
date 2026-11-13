// Kaydın kartı (K-171, K-173): kod ve ad, güncel veride mi, İlişkili kayıtlar (yalnız Ana veri).
import { getJson, postJson } from "../api/client";
import type { ListFilter } from "../table/types";

export interface Relation { key: string; label: string; list: string; count: number; filters: ListFilter[] }

export interface RecordCard {
  list: string;
  table: string;
  id: string;
  code: string;
  name: string | null;
  label: string;
  current: boolean;
  closed_version: number | null;
  relations: Relation[];
}

/** Çoklu seçimde kart (K-171): seçili kayıtların İlişkili kayıtlarının birleşimi. */
export interface RecordsCard { list: string; table: string; ids: string[]; relations: Relation[] }

export const recordsApi = {
  many: (list: string, ids: string[], signal?: AbortSignal) => postJson<RecordsCard>(`/api/records/${encodeURIComponent(list)}/many`, { ids }, signal),
  read: (list: string, id: string, signal?: AbortSignal) => getJson<RecordCard>(`/api/records/${encodeURIComponent(list)}/${encodeURIComponent(id)}`, signal),
};
