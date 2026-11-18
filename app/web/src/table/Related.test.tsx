// İlişkili alanlar (K-182): Alanlar panelinde "İlişkili alanlar" bölümü (başlıklar, açınca yükleme, arama), seçilen alanın isteğe ve başlığa
// girmesi, salt okunurluk, ilişkili miktar alanının kendi biriminin ondalığı, görünümden gelen ilişkili alan, sınır, "Varsayılana dön".
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp } from "../test/helpers";
import { joinPaths, MAX_RELATED_FIELDS, mergeColumns, relatedLimit, relatedPath } from "./related";
import { col, useTableTestSetup } from "./testBackend";
import type { ListColumn } from "./types";

useTableTestSetup();

const LIST = "/api/master-resource-group-member";
const COLUMNS = [col("ResourceGroupCode", "Kaynak grubu", "text", "list"), col("ResourceCode", "Kaynak", "text", "list", { manual: true })];
const rel = (field: string, label: string, type: ListColumn["type"] = "text", extra: Partial<ListColumn> = {}): ListColumn =>
  col(field, label, type, type === "bool" ? "list" : type === "number" ? "number" : "text", { default_visible: false, related: true, ...extra });
const CRITICAL = rel("ResourceGroupId/IsCritical", "Kaynak grubu · Kritik", "bool");
const GROUP_FIELDS = [rel("ResourceGroupId/Name", "Kaynak grubu · Grup adı"), CRITICAL, rel("ResourceGroupId/CapacityUnit", "Kaynak grubu · Kapasite birimi")];
const SUB = rel("ResourceGroupId/SubcontractorId/Name", "Kaynak grubu · Fasoncu · Tedarikçi adı");
const STOCK = rel("ResourceId/Stock", "Kaynak · Miktar", "number", { decimals_from_unit: true });
const CATALOG: Record<string, object> = {
  ResourceGroupId: { path: "ResourceGroupId", label: "Kaynak grubu", fields: GROUP_FIELDS,
                     relations: [{ path: "ResourceGroupId/SubcontractorId", label: "Kaynak grubu · Fasoncu" }] },
  "ResourceGroupId/SubcontractorId": { path: "ResourceGroupId/SubcontractorId", label: "Kaynak grubu · Fasoncu", fields: [SUB], relations: [] },
  ResourceId: { path: "ResourceId", label: "Kaynak", fields: [rel("ResourceId/ResourceType", "Kaynak · Kaynak tipi"), STOCK], relations: [] },
};
const ROWS = [
  { Id: 1, ResourceGroupCode: "ISL5", ResourceCode: "M5-01", "ResourceGroupId/IsCritical": true, "ResourceId/Stock": 12, _field_decimals: { "ResourceId/Stock": 0 }, _sources: {} },
  { Id: 2, ResourceGroupCode: "F-ISIL", ResourceCode: "F-ISIL", "ResourceGroupId/IsCritical": false, "ResourceId/Stock": 1.5, _field_decimals: { "ResourceId/Stock": 3 }, _sources: {} },
];

function backend(views: object = { views: [], default_view_id: null }, relations = [{ path: "ResourceGroupId", label: "Kaynak grubu" }, { path: "ResourceId", label: "Kaynak" }]) {
  const queries: { fields: string[] }[] = [];
  const related: string[] = [];
  mockApi({
    "/api/master-data/counts": { body: { data_version: 35, tabs: [] } },
    [`${LIST}/columns`]: { body: { chunk_size: 100, columns: COLUMNS, relations,
                                   export: { title: "Kaynak grup eşleşmesi", file_slug: "kaynak-grup-eslesmesi", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    [`${LIST}/related`]: (url) => {
      const path = decodeURIComponent(url.split("path=")[1]);
      related.push(path);
      return { body: CATALOG[path] };
    },
    [`${LIST}/views`]: { body: views },
    [`${LIST}/query`]: (_url, init) => {
      queries.push(JSON.parse(String(init?.body)));
      return { body: { rows: ROWS, filtered: ROWS.length, total: ROWS.length } };
    },
  });
  return { queries, related };
}

async function open(views?: object, relations?: { path: string; label: string }[]) {
  const user = userEvent.setup();
  const calls = backend(views, relations);
  renderApp("/veri/ana-veri?sekme=kaynak&tablo=kaynak-grup-eslesmesi", meAs("Key user"));
  await screen.findByText("M5-01", {}, { timeout: 5000 });
  return { user, ...calls, last: () => calls.queries[calls.queries.length - 1] };
}

describe("ilişkili alanların hesabı", () => {
  it("yol, birleştirmeler ve sınır", () => {
    expect(relatedPath("WorkOrderId/MaterialId/Name")).toBe("WorkOrderId/MaterialId");
    expect([...joinPaths(["Code", "WorkOrderId/MaterialId/Name", "WorkOrderId/Status"])]).toEqual(["WorkOrderId", "WorkOrderId/MaterialId"]);
    const twenty = Array.from({ length: MAX_RELATED_FIELDS }, (_, i) => `A/F${i}`);
    expect(relatedLimit(twenty, "A/X")).toBe("fields");
    const eight = ["A/x", "B/x", "C/x", "D/x", "E/x", "F/x", "G/x", "H/x"];
    expect([relatedLimit(eight, "I/x"), relatedLimit(eight, "A/y"), relatedLimit(eight.slice(0, 7), "A/B/x")]).toEqual(["joins", null, null]);
    expect(mergeColumns(COLUMNS, [CRITICAL], [CRITICAL, COLUMNS[0]]).map((c) => c.field)).toEqual(["ResourceGroupCode", "ResourceCode", CRITICAL.field]);
  });
});

describe("Alanlar paneli: İlişkili alanlar (K-182)", () => {
  it("başlıklar kapalı gelir; açılınca alanlar yüklenir; seçilen alan isteğe ve başlığa girer; salt okunurdur", async () => {
    const { user, related, last } = await open();
    await user.click(screen.getByRole("button", { name: "Alanlar (2/2)" }));
    const panel = screen.getByRole("dialog", { name: "Alanlar (2/2)" });
    const section = within(panel).getByRole("group", { name: "İlişkili alanlar" });
    expect(within(section).getAllByRole("button").map((b) => b.textContent)).toEqual(["Kaynak grubu", "Kaynak"]);
    expect(related).toEqual([]);                                                   // açılmadan yüklenmez
    await user.click(within(section).getByRole("button", { name: "Kaynak grubu" }));
    await user.click(await within(section).findByRole("checkbox", { name: "Kritik" }));
    expect(related).toEqual(["ResourceGroupId"]);
    await waitFor(() => expect(last().fields).toEqual(["ResourceGroupCode", "ResourceCode", "ResourceGroupId/IsCritical"]));
    const header = screen.getByRole("columnheader", { name: /Kaynak grubu · Kritik/ });
    expect(header).toBeInTheDocument();
    expect(header.textContent).not.toContain("✎");                                // düzenlenebilir işareti yok
    expect(screen.getByRole("button", { name: "Alanlar (3/2)" })).toBeInTheDocument();  // açık kolonlar / tablonun kendi alanları
    expect(within(section).getAllByRole("button", { name: /Kaynak grubu/ })[0].textContent).toContain("1");
    // ikinci seviye: alt başlık, kendi açılışında yüklenir
    await user.click(within(section).getByRole("button", { name: "Kaynak grubu › Fasoncu" }));
    expect(await within(section).findByRole("checkbox", { name: "Tedarikçi adı" })).toBeInTheDocument();
    expect(related).toEqual(["ResourceGroupId", "ResourceGroupId/SubcontractorId"]);
    await user.click(within(section).getByRole("checkbox", { name: "Kritik" }));
    await waitFor(() => expect(last().fields).toEqual(["ResourceGroupCode", "ResourceCode"]));
    expect(screen.queryByRole("columnheader", { name: /Kaynak grubu · Kritik/ })).toBeNull();
  });

  it("arama birinci seviyenin alanlarını yükler ve arar; ikinci seviye açılmadıkça aranmaz", async () => {
    const { user, related } = await open();
    await user.click(screen.getByRole("button", { name: /Alanlar/ }));
    const panel = screen.getByRole("dialog");
    await user.type(within(panel).getByRole("searchbox"), "kapasite");
    expect(await within(panel).findByRole("checkbox", { name: "Kapasite birimi" })).toBeInTheDocument();
    expect(related.sort()).toEqual(["ResourceGroupId", "ResourceId"]);
    expect(within(panel).getAllByRole("checkbox")).toHaveLength(1);                // tablonun kendi alanlarında eşleşme yok
    await user.clear(within(panel).getByRole("searchbox"));
    await user.type(within(panel).getByRole("searchbox"), "tedarikçi");
    await waitFor(() => expect(within(panel).queryAllByRole("checkbox")).toHaveLength(0));
  });

  it("ilişkili miktar alanı kendi kaydının biriminin ondalığıyla; \"Varsayılana dön\" ilişkili alanları da kapatır", async () => {
    const { user, last } = await open();
    await user.click(screen.getByRole("button", { name: /Alanlar/ }));
    const panel = screen.getByRole("dialog");
    await user.click(within(panel).getByRole("button", { name: "Kaynak" }));
    await user.click(await within(panel).findByRole("checkbox", { name: "Miktar" }));
    await waitFor(() => expect(last().fields).toContain("ResourceId/Stock"));
    expect(await screen.findByText("1,500")).toBeInTheDocument();                 // 3 ondalık (satırın _field_decimals'ı)
    expect(screen.getByText("12")).toBeInTheDocument();                           // ondalıksız
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Varsayılana dön" }));
    await waitFor(() => expect(last().fields).toEqual(["ResourceGroupCode", "ResourceCode"]));
  });

  it("görünümden gelen ilişkili alan açılışta kolondur (ek istek yok)", async () => {
    const definition = { v: 1, columns: [{ field: "ResourceCode" }, { field: CRITICAL.field }], pinned: 0, sort: [{ field: CRITICAL.field, dir: "desc" }],
                         filters: [], group_by: [] };
    const views = { views: [{ id: 5, name: "Kritikler", owner_user_id: 1, owner_name: "x", is_shared: false, is_owner: true,
                              updated_at: "2026-11-19T10:00:00+00:00", definition, warnings: [] }], default_view_id: 5, related_columns: [CRITICAL] };
    const { queries, related } = await open(views);
    expect(queries[0].fields).toEqual(["ResourceCode", CRITICAL.field]);
    expect(queries[0]).toMatchObject({ sort: [{ field: CRITICAL.field, dir: "desc" }] });
    expect(screen.getByRole("columnheader", { name: /Kaynak grubu · Kritik/ })).toBeInTheDocument();
    expect(screen.getByText("Evet")).toBeInTheDocument();
    expect(related).toEqual([]);
  });

  it("ilişkisi olmayan tabloda bölüm görünmez", async () => {
    const { user } = await open(undefined, []);
    await user.click(screen.getByRole("button", { name: /Alanlar/ }));
    expect(within(screen.getByRole("dialog")).queryByRole("group", { name: "İlişkili alanlar" })).toBeNull();
    expect(within(screen.getByRole("dialog")).getAllByRole("checkbox")).toHaveLength(2);
  });

  it("sınırda kalan kutular kapalıdır, nedeni ipucunda", async () => {
    const many = Array.from({ length: MAX_RELATED_FIELDS }, (_, i) => rel(`ResourceGroupId/F${i}`, `Kaynak grubu · Alan ${i}`));
    const definition = { v: 1, columns: [{ field: "ResourceCode" }, ...many.map((c) => ({ field: c.field }))], pinned: 0, sort: [], filters: [], group_by: [] };
    const views = { views: [{ id: 6, name: "Dolu", owner_user_id: 1, owner_name: "x", is_shared: false, is_owner: true,
                              updated_at: "2026-11-19T10:00:00+00:00", definition, warnings: [] }], default_view_id: 6, related_columns: many };
    const { user } = await open(views);
    await user.click(screen.getByRole("button", { name: /Alanlar/ }));
    const panel = screen.getByRole("dialog");
    await user.click(within(panel).getByRole("button", { name: /Kaynak grubu/ }));
    const box = await within(panel).findByRole("checkbox", { name: "Kritik" });
    expect(box).toBeDisabled();
    expect(box.closest("[title]")).toHaveAttribute("title", "Kaynak grubu · Kritik · En çok 20 ilişkili alan seçilebilir");
  });
});
