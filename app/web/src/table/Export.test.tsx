// Excel'e aktarım (1.5, U-14, K-91): kapsam penceresi, sözleşmeye giden istek, anlık indirme, arka plan işi
// (iş göstergesinde ilerleme, bitince bildirim ve İndir), sınır ve hata.
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FakeWebSocket } from "../test/helpers";
import { exportFileName } from "./ExportDialog";
import { calls, EXPORT_FILE, openTable, savedView, STANDARD_FIELDS, useTableTestSetup } from "./testBackend";

useTableTestSetup();

let saved: string[] = [];
beforeEach(() => {
  saved = [];
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    saved.push(this.download);
  });
});

const openDialog = async () => {
  await userEvent.click(await screen.findByRole("button", { name: "Excel'e aktar" }));
  return screen.findByRole("dialog", { name: "Excel'e aktar · Malzeme listesi" });
};

const job = (status: string, extra: Record<string, unknown> = {}) => ({
  id: 81, job_type: "Dışa aktarım", channel: "Dışa aktarım", status, progress: null, queue_position: null,
  updated_at: "2026-10-28T10:00:00+00:00", ...extra,
});

const socket = () => FakeWebSocket.instances.find((s) => s.url.includes("/api/ws"))!;

describe("kapsam penceresi ve anlık indirme", () => {
  it("ekrandaki görünüm durumunu gönderir; dosya sunucunun verdiği adla iner", async () => {
    await openTable({ filtered: 800, total: 800 });
    const dialog = await openDialog();
    expect(dialog).toHaveTextContent("Veri v35 · 800 satır");
    expect(within(dialog).getByRole("radio", { name: "Tümü (800 satır)" })).toBeChecked();  // filtre yokken tek seçenek
    expect(within(dialog).getByRole("radio", { name: "Görünen (7)" })).toBeChecked();
    expect(within(dialog).getByTestId("export-file-name").textContent).toMatch(/^smartchain_malzeme_veri-v35_\d{4}-\d\d-\d\d_\d{4}\.xlsx$/);
    // Sade pencere (1.5 demosu): yalnız Satırlar, Sütunlar, Dosya adı, Vazgeç / İndir; onay kutusu, bilgi kutusu, not yok
    expect(within(dialog).getAllByRole("group").map((g) => g.querySelector("legend")?.textContent)).toEqual(["Satırlar", "Sütunlar"]);
    expect(within(dialog).queryAllByRole("checkbox")).toEqual([]);
    expect(dialog.querySelectorAll(".sc-alert")).toHaveLength(0);
    expect(within(dialog).getAllByRole("button").map((b) => b.textContent)).toEqual(["Vazgeç", "İndir"]);
    expect(dialog).not.toHaveTextContent("ize yazılır");
    expect(dialog).not.toHaveTextContent("geri yüklenemez");

    await userEvent.click(within(dialog).getByRole("button", { name: "İndir" }));
    await waitFor(() => expect(saved).toEqual([EXPORT_FILE]));
    expect(calls.exports[0].url).toBe("/api/materials/export?user_id=3");
    expect(calls.exports[0].body).toEqual({
      fields: STANDARD_FIELDS, widths: {}, sort: [], filters: [], group_by: [], aggregates: { SafetyStock: { fn: "sum" } },
      rules: [], scope: { rows: "filtered", columns: "visible" },
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("filtre ve gruplamayla: tüm satırlar, tüm sütunlar; gruplama istekte ekrandaki gibi", async () => {
    const filters = [{ field: "Name", op: "contains" as const, value: "mil" }];
    const view = savedView(7, "Mil", { columns: [{ field: "Code", width: 8 }, { field: "Name" }], filters,
                                       group_by: ["MaterialLevel"], sort: [{ field: "Code", dir: "desc" }] });
    await openTable({ total: 50_000, views: { views: [view], default_view_id: 7 },
                      groups: [{ key: ["Hammadde"], count: 120, aggregates: {}, mixed_units: [], unit_decimals: {} }] });
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("radio", { name: "Tümü (50.000 satır)" }));
    expect(within(dialog).getByRole("radio", { name: "Filtrelenmiş (120)" })).not.toBeChecked();
    await userEvent.click(within(dialog).getByRole("radio", { name: "Tümü (10)" }));
    expect(within(dialog).queryAllByRole("checkbox")).toEqual([]);
    // 50.000 satır anlık sınırı (10.000) aşar: arka planda hazırlanır
    expect(dialog).toHaveTextContent("dosya arka planda hazırlanır");
    await userEvent.click(within(dialog).getByRole("button", { name: "Hazırla" }));
    await waitFor(() => expect(calls.exports).toHaveLength(1));
    expect(calls.exports[0].body).toMatchObject({
      fields: ["Code", "Name"], widths: { Code: 8 }, sort: [{ field: "Code", dir: "desc" }], filters, group_by: ["MaterialLevel"],
      scope: { rows: "all", columns: "all" },
    });
  });

  it("üst sınırı aşan aktarım kapalı", async () => {
    await openTable({ filtered: 600_000, total: 600_000 });
    const dialog = await openDialog();
    expect(dialog).toHaveTextContent("600.000 satır, bir aktarımın sınırı olan 500.000 satırı aşıyor; filtreyi daraltın.");
    expect(within(dialog).getByRole("button", { name: "İndir" })).toBeDisabled();
    await userEvent.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(calls.exports).toEqual([]);
  });

  it("sunucu hatası pencerede görünür; dosya inmez", async () => {
    await openTable({
      filtered: 800, total: 800,
      exportReply: { status: 503, body: { error: { code: "export_trace_failed", message: "Dışa aktarım ize yazılamadı; dosya verilmedi.", trace_id: "x" } } },
    });
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: "İndir" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Dışa aktarım ize yazılamadı; dosya verilmedi.");
    expect(saved).toEqual([]);
  });

  it("dosya adı önizlemesi sunucuyla aynı kalıpta", () => {
    expect(exportFileName("malzeme", 142, new Date(2026, 9, 28, 9, 5))).toBe("smartchain_malzeme_veri-v142_2026-10-28_0905.xlsx");
  });
});

describe("arka plan: ilerleme ve bildirim", () => {
  const start = async () => {
    await openTable({ filtered: 20_000, total: 20_000,
                      exportReply: { status: 202, body: { job_id: 81, file_name: EXPORT_FILE, rows: 20_000 } } });
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: "Hazırla" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await act(async () => socket().open());  // bağlanınca liste yenilenir (/api/jobs); bitmesini bekle
  };

  it("iş göstergesi ilerlemeyi yazar; bitince 'İndir' bildirimi dosyayı indirir", async () => {
    await start();
    act(() => socket().send({ type: "job", job: job("Çalışıyor", { progress: "5.000 / 20.000 satır" }) }));
    const indicator = screen.getByTestId("job-indicator");
    expect(indicator).toHaveTextContent("Excel hazırlanıyor · 5.000 / 20.000 satır");
    expect(within(indicator).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");
    expect(screen.queryByRole("region", { name: "Bildirimler" })).toBeNull();

    act(() => socket().send({ type: "job", job: job("Bitti", { progress: "Hazır · 4,8 MB" }) }));
    const toast = await screen.findByRole("region", { name: "Bildirimler" });
    expect(toast).toHaveTextContent("Malzeme listesi hazır · 4,8 MB");
    expect(toast).toHaveTextContent(EXPORT_FILE);
    await userEvent.click(within(toast).getByRole("button", { name: `${EXPORT_FILE} dosyasını indir` }));
    await waitFor(() => expect(saved).toEqual([EXPORT_FILE]));
    expect(calls.downloads).toEqual(["/api/exports/81/file?user_id=3"]);
    expect(screen.queryByRole("region", { name: "Bildirimler" })).toBeNull();
  });

  it("iş hata ile biterse bildirim nedeni yazar ve kapatılır", async () => {
    await start();
    act(() => socket().send({ type: "job", job: job("Hata", { error_text: "Excel dosyası hazırlanamadı. Destek için iş numarası: 81" }) }));
    const toast = await screen.findByRole("region", { name: "Bildirimler" });
    expect(toast).toHaveTextContent("Malzeme listesi hazırlanamadı");
    expect(toast).toHaveTextContent("Destek için iş numarası: 81");
    await userEvent.click(within(toast).getByRole("button", { name: "Kapat" }));
    expect(screen.queryByRole("region", { name: "Bildirimler" })).toBeNull();
  });

  it("biten aktarım iş listesinden de indirilir (sayfa yenilense bile)", async () => {
    await openTable();
    await act(async () => socket().open());  // bağlanınca liste yenilenir (/api/jobs); bitmesini bekle
    act(() => socket().send({ type: "job", job: job("Bitti", { progress: "Hazır · 4,8 MB" }) }));
    await userEvent.click(screen.getByTestId("job-indicator"));
    const list = screen.getByRole("dialog", { name: "Arka plandaki işler" });
    await userEvent.click(within(list).getByRole("button", { name: "İndir" }));
    await waitFor(() => expect(saved).toEqual([EXPORT_FILE]));
    expect(screen.queryByRole("region", { name: "Bildirimler" })).toBeNull();  // bu oturumda başlatılmadı: bildirim yok
  });
});
