// Excel'e aktar · kapsam penceresi (U-14, fonksiyon 86, K-91; mockup m24f-0724, 1.5 demosunda sadeleşti): yalnız
// satırlar (filtrelenmiş ya da tümü), sütunlar (görünen ya da tümü) ve dosya adı. Gruplama, ara toplamlar ve Bilgi
// sayfası her zaman gelir. Satır sayısı anlık sınırı aşarsa dosya arka planda hazırlanır, üst sınırı aşarsa aktarım
// kapalıdır ("filtreyi daraltın"); yalnız bu durumlarda ve sunucu hatasında mesaj çıkar.
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { Alert, Dialog, RadioGroup } from "../ui";
import type { ExportInfo, ExportScope } from "./types";

const T = tr.table;

const pad = (n: number) => String(n).padStart(2, "0");

/** Sunucunun vereceği adın önizlemesi: smartchain_<liste>_veri-v<n>_<yyyy-aa-gg_ssdd>.xlsx (K-91). */
export function exportFileName(slug: string, version: number | null, now: Date): string {
  const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`;
  return `smartchain_${slug}_${version ? `veri-v${version}` : "veri"}_${stamp}.xlsx`;
}

export function ExportDialog({ info, filtered, total, visibleColumns, allColumns, hasFilters, onClose, onExport }: {
  info: ExportInfo;
  filtered: number;
  total: number;
  visibleColumns: number;
  allColumns: number;
  hasFilters: boolean;
  onClose(): void;
  /** Hata fırlatırsa pencere açık kalır, mesaj içinde görünür. */
  onExport(scope: ExportScope): Promise<void>;
}) {
  const [scope, setScope] = useState<ExportScope>({ rows: "filtered", columns: "visible" });
  const [version, setVersion] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.currentDataVersion().then((dv) => alive && setVersion(dv.id)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  const rows = scope.rows === "filtered" ? filtered : total;
  const tooLarge = rows > info.max_rows;
  const background = !tooLarge && rows > info.sync_max_rows;
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await onExport(scope);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  return (
    <Dialog wide title={T.exportTitle(info.title)} subtitle={T.exportSubtitle(version, formatNumber(rows))}
            onClose={onClose} onSubmit={submit} busy={busy} submitDisabled={tooLarge}
            submitLabel={background ? T.exportSubmitBackground : T.exportSubmit}>
      <div className="sc-export-grid">
        <RadioGroup label={T.exportRows} value={scope.rows} onChange={(v) => setScope({ ...scope, rows: v as ExportScope["rows"] })}
                    options={[
                      ...(hasFilters ? [{ value: "filtered", label: T.exportRowsFiltered(formatNumber(filtered)) }] : []),
                      { value: hasFilters ? "all" : "filtered", label: T.exportRowsAll(formatNumber(total)) },
                    ]} />
        <RadioGroup label={T.exportColumns} value={scope.columns}
                    onChange={(v) => setScope({ ...scope, columns: v as ExportScope["columns"] })}
                    options={[{ value: "visible", label: T.exportColumnsVisible(visibleColumns) },
                              { value: "all", label: T.exportColumnsAll(allColumns) }]} />
      </div>
      <div className="sc-field">
        <span className="sc-field-label">{T.exportFileName}</span>
        <output className="sc-export-file sc-num" data-testid="export-file-name">
          {exportFileName(info.file_slug, version, new Date())}
        </output>
      </div>
      {background && (
        <Alert tone="info">{T.exportBackground(formatNumber(rows), formatNumber(info.sync_max_rows), info.file_hours)}</Alert>
      )}
      {tooLarge && <Alert tone="risk">{T.exportTooLarge(formatNumber(rows), formatNumber(info.max_rows))}</Alert>}
      {error && <Alert tone="error" title={T.exportError}>{error}</Alert>}
    </Dialog>
  );
}
