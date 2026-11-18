// Validasyon bildirimi (K-181): ekranda en çok bir validasyon bildirimi. Tek tabloda tablo bildirimi, birden fazla tabloda tek özet
// ("Validasyon bitti · 25 tablo: 4 geçti, 3 uyarılı, 16 hatalı, 2 tamamlanamadı"). Toplu çekimde özet, grubun tablolar arası işinden okunur.
import { JOB_DONE, JOB_FAILED, JOB_VALIDATION, type Job, VALIDATION_NOTIFY } from "../api/client";

const CROSS_SCOPE = "Tablolar arası";
const BULK_TRIGGER = "Toplu çekim";
/** İşi süren durumlar: bunlardan biri varken bildirim bekler. */
export const VALIDATION_ACTIVE = ["Sırada", "Çalışıyor"];
/** Özetteki sıra; son değer işin düştüğü (Valide edilemedi) tablodur. */
export const NOT_COMPLETED = "Tamamlanamadı";
export const SUMMARY_ORDER = ["Geçti", "Uyarılı", "Hatalı", NOT_COMPLETED];

/** Toplu çekimin sonundaki tablolar arası iş: grubun özeti buradan çıkar. */
export const isBulkCross = (job: Job) =>
  job.job_type === JOB_VALIDATION && job.validation?.scope === CROSS_SCOPE && job.validation?.trigger === BULK_TRIGGER;

/** Bu iş bu kullanıcıya validasyon bildirimi verir mi? Zamanlanmış toplu işin (sahibi yok) özeti kimseye çıkmaz. */
export function validationNotifies(job: Job, userId: number): boolean {
  if (job.job_type !== JOB_VALIDATION) return false;
  if (isBulkCross(job)) return job.requested_by === userId;
  return VALIDATION_NOTIFY.includes(job.validation?.trigger ?? "") && Boolean(job.validation?.entity) && (job.requested_by ?? userId) === userId;
}

export interface ValidationSummary {
  /** Tek tablonun işi: bugünkü tablo bildirimi gösterilir. */
  single: Job | null;
  tables: number;
  parts: { outcome: string; count: number }[];
  /** İçinde tamamlanamayan var: bildirim kırmızı. */
  failed: boolean;
  jobIds: number[];
}

/** Biten validasyon işlerinin özeti; aynı tablonun birden fazla işi varsa sonuncusu sayılır. */
export function summarize(jobs: Job[]): ValidationSummary | null {
  const ended = jobs.filter((j) => j.job_type === JOB_VALIDATION && (j.status === JOB_DONE || j.status === JOB_FAILED)).sort((a, b) => a.id - b.id);
  if (!ended.length) return null;
  const byTable = new Map<string, string>();
  for (const j of ended) {
    if (isBulkCross(j)) {
      if (j.status === JOB_DONE && j.validation?.tables?.length) for (const t of j.validation.tables) byTable.set(t.entity, t.outcome);
      else byTable.set(`${CROSS_SCOPE}:${j.id}`, NOT_COMPLETED);
    } else {
      byTable.set(j.validation?.entity ?? String(j.id), j.status === JOB_FAILED ? NOT_COMPLETED : j.validation?.outcome ?? NOT_COMPLETED);
    }
  }
  const outcomes = [...byTable.values()];
  const parts = SUMMARY_ORDER.map((outcome) => ({ outcome, count: outcomes.filter((o) => o === outcome).length })).filter((p) => p.count > 0);
  return {
    single: ended.length === 1 && !isBulkCross(ended[0]) ? ended[0] : null,
    tables: byTable.size,
    parts,
    failed: outcomes.includes(NOT_COMPLETED),
    jobIds: ended.map((j) => j.id),
  };
}
