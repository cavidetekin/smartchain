// Ana veri (ekran 03) ve İşlem verisi (ekran 29) (K-168, K-169): sekmeler, tablo seçimi (kayıt sayılarıyla, tek tabloda yok), adres ve
// hatırlanan seçim, Standart görünümde süzgeç yok, salt okunur.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import type { ListColumn, QueryRequest } from "../table/types";
import { meAs, mockApi, renderApp, type Reply, type Routes } from "../test/helpers";

useTableTestSetup();

const COLUMNS: Record<string, ListColumn[]> = {
  materials: [col("Code", "Malzeme kodu", "text", "text"), col("Name", "Malzeme adı", "text", "text"),
              col("IsActive", "Aktif", "bool", "list", { values: [true, false], default_visible: false })],
  "master-material-reference": [col("MaterialCode", "Malzeme kodu", "text", "list", { values_from_server: true }),
                                col("TimeFactor", "Süre katsayısı", "number", "number", { decimals: 2 })],
  "master-bom": [col("MaterialCode", "Malzeme kodu", "text", "list", { values_from_server: true }),
                 col("Quantity", "Miktar", "number", "number", { decimals_from_unit: true })],
  "master-location": [col("Code", "Lokasyon kodu", "text", "text")],
  "transaction-sales-order": [col("OrderNo", "Sipariş no", "text", "text"), col("OpenQuantity", "Açık miktar", "number", "number", { decimals_from_unit: true })],
  "transaction-project-group": [col("Code", "Proje grubu kodu", "text", "text")],
  "transaction-purchase-order": [col("PurchaseOrderNo", "Sipariş no", "text", "text")],
};
const ROWS: Record<string, Reply["body"]> = {
  materials: [{ Id: 1, Code: "HAM-001", Name: "Çelik çubuk", IsActive: true }],
  "master-material-reference": [],
  "master-bom": [{ Id: 5, MaterialCode: "ALT-001", Quantity: 2, _unit_decimals: 0 }],
  "master-location": [{ Id: 1, Code: "ORM-01" }],
  "transaction-sales-order": [{ Id: 50, OrderNo: "SO-1001", OpenQuantity: 12, _unit_decimals: 0 }],
  "transaction-project-group": [{ Id: 1, Code: "PG-01" }],
  "transaction-purchase-order": [{ Id: 1, PurchaseOrderNo: "PO-2001" }],
};
const MASTER_COUNTS = {
  data_version: 35,
  tabs: [
    { key: "malzeme", tables: [{ list: "materials", label: "Malzeme", count: 1212 }, { list: "master-material-reference", label: "Benzetilen ürün", count: 0 }] },
    { key: "urun-agaci-ve-rota", tables: [{ list: "master-production-version", label: "Üretim versiyonu", count: 123 },
                                          { list: "master-bom", label: "Ürün ağacı", count: 274 }, { list: "master-routing", label: "Rota", count: 212 }] },
  ],
};
const TX_COUNTS = {
  data_version: 35,
  tabs: [
    { key: "talep", tables: [{ list: "transaction-sales-order", label: "Satış siparişi", count: 51 }, { list: "transaction-forecast", label: "Tahmin", count: 0 },
                             { list: "transaction-project", label: "Proje", count: 3 }, { list: "transaction-project-group", label: "Proje grubu", count: 1 }] },
    { key: "satin-alma", tables: [{ list: "transaction-purchase-order", label: "Satın alma siparişi", count: 39 }] },
  ],
};

const queries: { list: string; body: QueryRequest }[] = [];

function backend() {
  queries.length = 0;
  const routes: Routes = { "/api/master-data/counts": { body: MASTER_COUNTS }, "/api/transaction-data/counts": { body: TX_COUNTS } };
  for (const list of Object.keys(COLUMNS)) {
    routes[`/api/${list}/columns`] = { body: { chunk_size: 100, columns: COLUMNS[list], export: { title: list, file_slug: list, sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } };
    routes[`/api/${list}/views`] = { body: { views: [], default_view_id: null } };
    routes[`/api/${list}/query`] = (_url, init) => {
      queries.push({ list, body: JSON.parse(String(init?.body)) as QueryRequest });
      const rows = ROWS[list] as unknown[];
      return { body: { rows, filtered: rows.length, total: rows.length } };
    };
  }
  return mockApi(routes);
}

async function open(path: string, title: string, role = "End user") {
  const user = userEvent.setup();
  backend();
  renderApp(path, meAs(role));
  await screen.findByRole("heading", { level: 1, name: title }, { timeout: 5000 });
  return user;
}

const tabs = (name: string) => screen.getByRole("radiogroup", { name });
const picker = () => screen.queryByRole("combobox", { name: "Tablo" });

describe("Ana veri", () => {
  const openMaster = (path = "/veri/ana-veri") => open(path, "Ana veri");

  it("beş sekme (Proje yok); varsayılan Malzeme; End user okur, düzenleme yok; süzgeç yok", async () => {
    await openMaster();
    expect(within(tabs("Ana veri bölümleri")).getAllByRole("radio").map((r) => r.textContent))
      .toEqual(["Malzeme", "Ürün ağacı ve rota", "Kaynak", "Tedarikçi ve müşteri", "Lokasyon ve birim"]);
    expect(within(tabs("Ana veri bölümleri")).getByRole("radio", { name: "Malzeme" })).toHaveAttribute("aria-checked", "true");
    expect(await screen.findByText("Çelik çubuk", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
    expect(queries.filter((q) => q.list === "materials").at(-1)!.body.filters ?? []).toEqual([]);
    expect(screen.queryByRole("columnheader", { name: /Aktif/ })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/K-\d+/);
  });

  it("tablo seçimi araç çubuğunun başında, kayıt sayılarıyla; seçilince tablo değişir", async () => {
    const user = await openMaster();
    await waitFor(() => expect(picker()).toBeInTheDocument());
    await waitFor(() => expect([...picker()!.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["Malzeme (1.212)", "Benzetilen ürün (0)"]));
    const lead = picker()!.closest(".sc-table-toolbar-main")!;   // şeridin solu: sekmeler, sonra tablo seçimi (K-173)
    expect(lead.firstElementChild).toHaveClass("sc-overflow-tabs");
    expect(lead.children[1]).toBe(picker());
    await user.selectOptions(picker()!, "master-material-reference");
    expect(await screen.findByRole("columnheader", { name: /Süre katsayısı/ }, { timeout: 5000 })).toBeInTheDocument();
    // başlık kesilmez (K-169): sayı kolonunun varsayılanı 9,23 rem; "Süre katsayısı" 14 harf → 14 × 0,56 + 3,6 = 11,44 rem
    expect([...document.querySelectorAll("colgroup col")].map((c) => (c as HTMLElement).style.width)).toEqual(["10.32rem", "11.44rem", "2.5rem"]);  // son kolon ⋯ menüsü (K-171)
  });

  it("adresle sekme ve tablo açılır", async () => {
    await openMaster("/veri/ana-veri?sekme=urun-agaci-ve-rota&tablo=urun-agaci");
    expect(within(tabs("Ana veri bölümleri")).getByRole("radio", { name: "Ürün ağacı ve rota" })).toHaveAttribute("aria-checked", "true");
    await waitFor(() => expect(picker()).toHaveValue("master-bom"));
    expect(await screen.findByText("ALT-001", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("son sekme ve tablo hatırlanır", async () => {
    const user = await openMaster();
    await waitFor(() => expect(picker()).toBeInTheDocument());
    await user.selectOptions(picker()!, "master-material-reference");
    await screen.findByRole("columnheader", { name: /Süre katsayısı/ }, { timeout: 5000 });
    await user.click(within(tabs("Ana veri bölümleri")).getByRole("radio", { name: "Lokasyon ve birim" }));
    await screen.findByText("ORM-01", {}, { timeout: 5000 });
    const saved = JSON.parse(window.localStorage.getItem("smartchain.u3.masterData") ?? "{}") as { tab: string; tables: Record<string, string> };
    expect(saved).toEqual({ tab: "lokasyon-ve-birim", tables: { malzeme: "master-material-reference" }, cards: {} });
  });
});

describe("İşlem verisi", () => {
  const openTx = (path = "/veri/islem-verisi") => open(path, "İşlem verisi");

  it("sekmeler aktarım grupları; varsayılan Talep, tablo seçiminde Proje ve Proje grubu", async () => {
    await openTx();
    expect(within(tabs("İşlem verisi bölümleri")).getAllByRole("radio").map((r) => r.textContent))
      .toEqual(["Talep", "Stok", "Üretim", "Satın alma", "İzin"]);
    expect(await screen.findByText("SO-1001", {}, { timeout: 5000 })).toBeInTheDocument();
    await waitFor(() => expect([...picker()!.querySelectorAll("option")].map((o) => o.textContent))
      .toEqual(["Satış siparişi (51)", "Tahmin (0)", "Proje (3)", "Proje grubu (1)"]));
  });

  it("tek tablolu sekmede tablo seçimi yok; adreste tablo yazmaz", async () => {
    const user = await openTx();
    await screen.findByText("SO-1001", {}, { timeout: 5000 });
    await user.click(within(tabs("İşlem verisi bölümleri")).getByRole("radio", { name: "Satın alma" }));
    expect(await screen.findByText("PO-2001", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(picker()).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 }).closest("section")!.querySelector(".sc-table-toolbar-main")!.firstElementChild!.tagName).not.toBe("SELECT");
  });

  it("adresle tablo; Key user ve End user açar", async () => {
    await openTx("/veri/islem-verisi?sekme=talep&tablo=proje-grubu");
    await waitFor(() => expect(picker()).toHaveValue("transaction-project-group"));
    expect(await screen.findByText("PG-01", {}, { timeout: 5000 })).toBeInTheDocument();
  });
});
