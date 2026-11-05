// Yetki matrisi (fonksiyon 90, K-100; ekran 22'den açılır): 14 grup × 4 rol. İstisnalar Excel'de, fonksiyon düzeyinde görünür.
import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { Alert, Button, Dialog } from "../ui";
import { type PermissionMatrix, systemOwnerApi } from "./systemOwnerApi";

const T = tr.matrix;

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : tr.users.failed);

export function PermissionMatrixDialog({ onClose }: { onClose(): void }) {
  const [matrix, setMatrix] = useState<PermissionMatrix | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    systemOwnerApi.matrix(ctrl.signal).then(setMatrix).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, []);

  const exportFile = async () => {
    setExporting(true);
    setError(null);
    try {
      await systemOwnerApi.exportMatrix();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setExporting(false);
    }
  };

  return (
    <Dialog title={T.title} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel xwide>
      {matrix && (
        <>
          <table className="sc-matrix" aria-label={T.title}>
            <thead>
              <tr>
                <th scope="col">{T.group}</th>
                {matrix.roles.map((r) => <th key={r} scope="col">{r}</th>)}
              </tr>
            </thead>
            <tbody>
              {matrix.groups.map((g) => (
                <tr key={g.key}>
                  <th scope="row">{g.name}</th>
                  {matrix.roles.map((r) => <td key={r}>{T.levels[g.levels[r]]}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          <div><Button busy={exporting} onClick={() => void exportFile()}>{T.exportButton}</Button></div>
        </>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}
