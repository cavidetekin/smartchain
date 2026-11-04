// Excel şablonu uç noktaları (docs/08 "Excel şablonu"; K-110). Liste ortak liste sözleşmesiyle (`data-entities`).
import { downloadFile, getJson } from "../api/client";

export interface TemplateInfo {
  entity: string;
  name: string;
  version: number;
  file_name: string;
  field_count: number;
  required: string[];
}

export const dataLoadApi = {
  info: (entity: string, signal?: AbortSignal) => getJson<TemplateInfo>(`/api/templates/${encodeURIComponent(entity)}/info`, signal),
  download: (entity: string, fallback: string) => downloadFile(`/api/templates/${encodeURIComponent(entity)}`, fallback),
};
