// Validasyon kuralları (ekran 27, fonksiyon 100; K-136, K-139) ve ortak koşul editörü.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { type ConditionField, ConditionEditor, type ConditionRow, groupsComplete, OPERATORS } from "../table/ConditionEditor";
import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Reply, type Routes } from "../test/helpers";

useTableTestSetup();

const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const COLUMNS = [
  col("EntityLabel", "Tablo", "text", "list"), col("RuleName", "Kural", "text", "text"), col("ConditionText", "Koşul", "text", "text"),
  col("Severity", "Sınıf", "text", "list"), col("Message", "Mesaj", "text", "text"), col("Kind", "Tür", "text", "list"), col("IsActive", "Aktif", "bool", "list"),
];
const RULES = [
  { Id: 2, EntityName: "Material", EntityLabel: "Malzeme", RuleName: "Minimum lot maksimum lottan büyük", ConditionText: "Minimum lot > Maksimum lot", Severity: "Hata",
    Message: "Minimum lot maksimum lottan büyük.", Kind: "Hazır", IsActive: true, Code: "MAT.MINLOT_MAXLOT", Editable: true, IsCustomized: false },
  { Id: 4, EntityName: "Material", EntityLabel: "Malzeme", RuleName: "Liste dışı değer", ConditionText: "Değer listeli alanda liste dışı değer", Severity: "Bilgi",
    Message: "Smartchain değerlerinde yok.", Kind: "Hazır", IsActive: true, Code: "ALL.OUT_OF_LIST", Editable: false, IsCustomized: false },
  { Id: 3, EntityName: "Material", EntityLabel: "Malzeme", RuleName: "Lot kontrolü", ConditionText: "Minimum lot boş değil", Severity: "Uyarı", Message: "Lot",
    Kind: "Kullanıcı", IsActive: true, Code: "KUL-1", Editable: true, IsCustomized: false },
];
const FIELDS: ConditionField[] = [
  { name: "MinLot", label: "Minimum lot", kind: "number", values: [] },
  { name: "MaxLot", label: "Maksimum lot", kind: "number", values: [] },
  { name: "MaterialLevel", label: "Malzeme seviyesi", kind: "text", values: ["Hammadde", "Yarı mamul", "Nihai ürün"] },
];
const DETAIL = { id: 2, entity: "Material", code: "MAT.MINLOT_MAXLOT", name: "Minimum lot maksimum lottan büyük", kind: "Hazır", check_type: "Mantıksal",
                 severity: "Hata", message: "Minimum lot maksimum lottan büyük.", active: true, locked: false, editable: true, customized: false,
                 groups: [[{ field: "MinLot", operator: ">", value: null, compare_field: "MaxLot" }]], condition: "Minimum lot > Maksimum lot" };

const saved = (changed: string[] = []) => (_url: string, init?: RequestInit) => (init?.method === "PUT" ? { body: { saved: 1, changed_entities: changed } } : { body: {} });

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/validation-rules/columns": { body: { chunk_size: 100, columns: COLUMNS, export: EXPORT } },
    "/api/validation-rules/query": { body: { rows: RULES, filtered: 3, total: 3 } },
    "/api/validation-rules/views": { body: { views: [], default_view_id: null } },
    "/api/validation-rules/fields/Material": { body: FIELDS as unknown as Reply["body"] },
    "/api/validation-rules/2": { body: DETAIL as unknown as Reply["body"] },
    "/api/data-entities/query": { body: { rows: [{ Id: 1, Entity: "Material", Name: "Malzeme" }], filtered: 1, total: 1 } },
    "/api/validation/Material": { body: { threshold: null } as unknown as Reply["body"] },
    ...routes,
  });
}

const calls = () => vi.mocked(fetch).mock.calls.map(([url, init]) => ({ url: String(url), method: (init as RequestInit | undefined)?.method ?? "GET",
                                                                       body: (init as RequestInit | undefined)?.body ? JSON.parse(String((init as RequestInit).body)) : null }));
const NAME = "Minimum lot maksimum lottan büyük";

describe("ekran 27 · Validasyon kuralları", () => {
  it("End user açamaz", async () => {
    backend();
    renderApp("/veri/validasyon-kurallari", meAs("End user"));
    expect(await screen.findByText(/Bu ekranı açma yetkiniz yok/)).toBeInTheDocument();
  });

  it("Key user salt okunur: sınıf pastel çip, yeni kural pasif", async () => {
    backend();
    renderApp("/veri/validasyon-kurallari", meAs("Key user"));
    expect(await screen.findByText(NAME, {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: `${NAME} sınıfı` })).not.toBeInTheDocument();
    expect(screen.getByText("Bilgi").className).toContain("sc-tag--soft");
    expect(screen.getByRole("button", { name: /Yeni kural/ })).toBeDisabled();
  });

  it("şerit tek satır: eşik yardım metni yok", async () => {
    backend();
    renderApp("/veri/validasyon-kurallari", meAs("Admin"));
    await screen.findByText(NAME, {}, { timeout: 5000 });
    expect(screen.queryByText(/Boşsa eşik kontrolü yapılmaz/)).not.toBeInTheDocument();
    const strip = screen.getByLabelText("Hata eşiği (%)").closest(".sc-table-toolbar-main");  // tablonun şeridinin solunda (K-171)
    expect(strip).toContainElement(screen.getByRole("combobox", { name: "Tablo" }));
    expect(strip).toContainElement(screen.getByRole("button", { name: "Yeni kural" }));
    expect(document.querySelector(".sc-top-strip")).toBeNull();
  });

  it("Admin: sınıf pastel çipten seçilir, toplu kaydedilir, yeniden validasyon önerilir; onay bandı yok", async () => {
    const user = userEvent.setup();
    backend({ "/api/validation-rules": saved(["Material"]), "/api/validation/Material/revalidate": { status: 202, body: { job_id: 3 } } });
    renderApp("/veri/validasyon-kurallari", meAs("Admin"));
    await screen.findByText(NAME, {}, { timeout: 5000 });
    const select = screen.getByRole("combobox", { name: `${NAME} sınıfı` });
    expect(select.className).toContain("sc-tag--critical");
    await user.selectOptions(select, "Uyarı");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const confirm = await screen.findByRole("dialog", { name: "Yeniden valide edilsin mi?" });
    const put = calls().find((c) => c.method === "PUT" && c.url === "/api/validation-rules")!;
    expect(put.body).toEqual({ changes: [{ id: 2, severity: "Uyarı" }], thresholds: [] });
    expect(within(confirm).getByText(/Malzeme/)).toBeInTheDocument();
    await user.click(within(confirm).getByRole("button", { name: "Yeniden valide et" }));
    await waitFor(() => expect(calls().some((c) => c.method === "POST" && c.url === "/api/validation/Material/revalidate")).toBe(true));
    expect(screen.queryByText(/sıraya girdi/)).not.toBeInTheDocument();
  });

  it("satır menüsü: hazır kural silinmez, ilk hâline döner; ifade edilemeyen hazır kural düzenlenmez", async () => {
    const user = userEvent.setup();
    backend();
    renderApp("/veri/validasyon-kurallari", meAs("Admin"));
    await screen.findByText(NAME, {}, { timeout: 5000 });
    await user.click(screen.getByRole("button", { name: `${NAME} işlemleri` }));
    let menu = await screen.findByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: "Düzenle" })).toBeEnabled();
    expect(within(menu).getByRole("menuitem", { name: "İlk hâline döndür" })).toBeEnabled();
    expect(within(menu).queryByRole("menuitem", { name: /Sil/ })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Liste dışı değer işlemleri" }));
    menu = await screen.findByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: /Düzenle/ })).toBeDisabled();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Lot kontrolü işlemleri" }));
    expect(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Sil" })).toBeEnabled();
  });

  it("hazır kural pencerede düzenlenir: yalnız değişen parçalar gider; İlk hâline döndür", async () => {
    const user = userEvent.setup();
    backend({ "/api/validation-rules": saved() });
    renderApp("/veri/validasyon-kurallari", meAs("Admin"));
    await screen.findByText(NAME, {}, { timeout: 5000 });
    await user.click(screen.getByRole("button", { name: `${NAME} işlemleri` }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Kuralı düzenle" });
    expect(within(dialog).getByRole("switch", { name: "Aktif" }).closest(".sc-dialog-head")).not.toBeNull();  // başlığın sağında
    expect(within(dialog).getByRole("radio", { name: "Hata" })).toHaveAttribute("aria-checked", "true");
    expect(within(dialog).getByRole("radio", { name: "Hata" }).className).toContain("sc-tag--critical");
    await user.click(within(dialog).getByRole("radio", { name: "Uyarı" }));
    await user.clear(within(dialog).getByLabelText(/^Mesaj/));
    await user.type(within(dialog).getByLabelText(/^Mesaj/), "Lot sınırları ters.");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Kuralı düzenle" })).not.toBeInTheDocument());
    const put = calls().find((c) => c.method === "PUT")!;
    expect(put.body.changes).toEqual([{ id: 2, severity: "Uyarı", active: true, message: "Lot sınırları ters." }]);

    await user.click(screen.getByRole("button", { name: `${NAME} işlemleri` }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
    await user.click(within(await screen.findByRole("dialog", { name: "Kuralı düzenle" })).getByRole("button", { name: "İlk hâline döndür" }));
    const confirm = await screen.findByRole("dialog", { name: "İlk hâline dönsün mü?" });
    await user.click(within(confirm).getByRole("button", { name: "İlk hâline döndür" }));
    await waitFor(() => expect(calls().filter((c) => c.method === "PUT").at(-1)!.body.changes).toEqual([{ id: 2, reset: true }]));
  });

  it("yeni kural: koşul yazılır, kaydedilir", async () => {
    const user = userEvent.setup();
    backend({ "/api/validation-rules": saved() });
    renderApp("/veri/validasyon-kurallari", meAs("Admin"));
    await screen.findByText(NAME, {}, { timeout: 5000 });
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "Material");
    await user.click(screen.getByRole("button", { name: "Yeni kural" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni kural" });
    await user.type(within(dialog).getByLabelText(/Kural adı/), "Lot");
    await user.type(within(dialog).getByLabelText(/^Mesaj/), "Lot sınırı");
    await waitFor(() => expect(within(dialog).getByRole("combobox", { name: "Operatör" })).toHaveValue("Boş"));
    expect(within(dialog).queryByRole("textbox", { name: "Değer" })).not.toBeInTheDocument();  // Boş'ta değer kutusu yok
    expect(within(dialog).queryByText(/^Koşul:/)).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Yeni kural" })).not.toBeInTheDocument());
    const put = calls().find((c) => c.method === "PUT")!;
    expect(put.body.changes[0]).toMatchObject({ entity: "Material", name: "Lot", message: "Lot sınırı", severity: "Uyarı",
                                                 groups: [[{ field: "MinLot", operator: "Boş", value: null, compare_field: null }]] });
  });
});

function Harness({ initial }: { initial: ConditionRow[][] }) {
  const [groups, setGroups] = useState(initial);
  return (
    <>
      <ConditionEditor fields={FIELDS} groups={groups} onChange={setGroups} />
      <output data-testid="groups">{JSON.stringify(groups)}</output>
    </>
  );
}
const state = () => JSON.parse(screen.getByTestId("groups").textContent!) as ConditionRow[][];

describe("koşul editörü (ortak bileşen, K-139)", () => {
  it("operatörler: karşılaştırmalar sembolle; Boş değil", () => {
    expect([...OPERATORS]).toEqual(["=", "≠", ">", "<", "≥", "≤", "İçerir", "İle başlar", "Listede", "Boş", "Boş değil"]);
  });

  it("tamamlık", () => {
    expect(groupsComplete([[{ field: "MinLot", operator: "Boş değil", value: null, compare_field: null }]])).toBe(true);
    expect(groupsComplete([[{ field: "MinLot", operator: "=", value: null, compare_field: null }]])).toBe(false);
    expect(groupsComplete([[{ field: "MinLot", operator: ">", value: null, compare_field: "MaxLot" }]])).toBe(true);
  });

  it("Koşullar, Koşul Grubu kartları, ve, VEYA; Değer / Alan anahtarı; metin dışı alanda İçerir yok", async () => {
    const user = userEvent.setup();
    render(<Harness initial={[[{ field: "MinLot", operator: "=", value: "5", compare_field: null }]]} />);
    expect(screen.getByRole("heading", { name: "Koşullar" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Koşul Grubu 1" })).toBeInTheDocument();
    expect(within(screen.getByRole("combobox", { name: "Operatör" })).queryByRole("option", { name: "İçerir" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Koşul ekle/ }));
    await user.click(screen.getByRole("button", { name: /VEYA grubu ekle/ }));
    expect(screen.getByRole("region", { name: "Koşul Grubu 2" })).toBeInTheDocument();
    expect(screen.getByText("VEYA")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Koşul Grubu 1" })).getAllByText("ve")).toHaveLength(1);
    expect(screen.getByRole("button", { name: /VEYA grubu ekle/ }).className).toContain("secondary");
    await user.click(screen.getAllByRole("radio", { name: "Alan" })[0]);
    await user.selectOptions(screen.getAllByRole("combobox", { name: "Karşılaştırılan alan" })[0], "MaxLot");
    expect(state()[0][0]).toEqual({ field: "MinLot", operator: "=", value: null, compare_field: "MaxLot" });
  });

  it("Boş ve Boş değil seçilince değer kutusu ve anahtar gizlenir", async () => {
    const user = userEvent.setup();
    render(<Harness initial={[[{ field: "MinLot", operator: "=", value: "5", compare_field: null }]]} />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Operatör" }), "Boş değil");
    expect(screen.queryByRole("textbox", { name: "Değer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: "Değer ya da alan" })).not.toBeInTheDocument();
    expect(state()[0][0]).toEqual({ field: "MinLot", operator: "Boş değil", value: null, compare_field: null });
  });

  it("değer listeli alanda değer serbest yazılır, liste öneri olarak çıkar (ERP'nin dili, K-143)", async () => {
    const user = userEvent.setup();
    render(<Harness initial={[[{ field: "MaterialLevel", operator: "=", value: null, compare_field: null }]]} />);
    const box = screen.getByRole("combobox", { name: "Değer" });  // datalist bağlı metin kutusu
    expect(box.tagName).toBe("INPUT");
    const list = document.getElementById(box.getAttribute("list")!)!;
    expect([...list.querySelectorAll("option")].map((o) => o.getAttribute("value"))).toEqual(["Hammadde", "Yarı mamul", "Nihai ürün"]);
    await user.type(box, "RAW");
    expect(state()[0][0].value).toBe("RAW");
  });
});
