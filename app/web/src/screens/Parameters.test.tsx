// Parametreler (ekran 06; K-175): ana başlıklar ve alt başlıklar; form kartı (değişiklik yokken düğmeler pasif, yalnız değişen gönderilir, LP'de lot
// anahtarları pasif); kaydedilmemiş değişiklik uyarısı; Hedefler (hücre düzenleme, toplam, kapatma, sürükleme, kayıt); Ufuk ve dönemler (salt okunur
// tarihler, satır ekleme ve silme, önizleme, şerit, kayıt); raporlama ekseni; End user'da ekran yok.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp } from "../test/helpers";

const P = (key: string, label: string, kind: string, extra: object = {}) => ({ key, label, kind, ...extra });
const SECTIONS = [
  { key: "model", title: "Model", table: null, subs: [
    { key: "model-tipi", title: "Model tipi", table: null, params: [
      P("ModelType", "Model tipi", "choice", { options: ["LP", "MILP"] }),
      P("ProductionMinLot", "Üretimde minimum lot", "bool", { enabled_when: { key: "ModelType", value: "MILP" }, hint: "Yalnız MILP modelde uygulanır." }),
      P("RoundPurchaseToLot", "Satın alma önerisini sipariş lotuna yuvarla", "bool")] },
    { key: "cozum", title: "Çözüm", table: null, params: [P("OptimalityGapPct", "Optimality gap (%)", "number", { min: 0, max: 100 })] }] },
  { key: "hedefler", title: "Hedefler", table: "objectives", subs: [] },
  { key: "malzeme", title: "Malzeme", table: null, subs: [
    { key: "kisit-ve-stok", title: "Kısıt ve stok", table: null, params: [P("MaterialConstraint", "Malzeme kısıtı", "bool")] },
    { key: "guvenlik-stogu", title: "Güvenlik stoğu", table: null, params: [
      P("SafetyStockMode", "Güvenlik stoğu", "choice", { options: ["Dikkate alma", "Yumuşak hedef", "Kesin kısıt"] })] }] },
  { key: "kapasite", title: "Kapasite", table: null, subs: [{ key: "kapasite", title: "Kapasite", table: null, params: [P("UseOvertime", "Fazla mesai kullanılsın", "bool")] }] },
  { key: "plan-kararliligi", title: "Plan kararlılığı", table: null, subs: [{ key: "plan-kararliligi", title: "Plan kararlılığı", table: null, params: [
    P("FixPeriod", "Sabit dönem", "int", { min: 0, unit_key: "FixPeriodUnit" }), P("FixPeriodUnit", "Sabit dönem birimi", "choice", { options: ["Gün", "Hafta", "Ay"] })] }] },
  { key: "planlama-ufku", title: "Planlama ufku", table: null, subs: [
    { key: "ufuk-ve-donemler", title: "Ufuk ve dönemler", table: "buckets", params: [] },
    { key: "raporlama-ekseni", title: "Raporlama ekseni", table: "report", params: [P("ReportAxisSameAsPlan", "Raporlama ekseni planla aynı", "bool")] },
    { key: "takvim-ayarlari", title: "Takvim ayarları", table: null, params: [
      P("WeekStart", "Hafta başlangıcı", "choice", { options: ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"] })] }] },
];
const VALUES = { ModelType: "LP", ProductionMinLot: "0", RoundPurchaseToLot: "1", OptimalityGapPct: "1", MaterialConstraint: "1", SafetyStockMode: "Yumuşak hedef",
                 UseOvertime: "0", ReportAxisSameAsPlan: "1", WeekStart: "Pazartesi", FixPeriod: "2", FixPeriodUnit: "Hafta" };
const O = (id: number, code: string, label: string, seq: number | null, seconds: number | null, tolerance: number | null) =>
  ({ id, code, label, priority_group: null, seq, seconds, tolerance, active: seq !== null });
const OBJECTIVES = [O(1, "UNMET_DEMAND", "Karşılanmayan talep", 1, 300, 0), O(2, "LATENESS", "Gecikme", 2, 300, 0), O(3, "OVERTIME", "Fazla mesai", 3, 60, 5),
                    O(4, "PLAN_DEVIATION", "Önceki plandan sapma", null, null, null)];
const PART = (bucket_type: string, count: number, span_unit: string, start: string, end: string, days: number) => ({ bucket_type, count, span_unit, start, end, buckets: count, days });
const PLAN = [PART("Hafta", 3, "Ay", "2026-11-16", "2027-01-31", 77), PART("Ay", 6, "Ay", "2027-02-01", "2027-07-31", 181)];
const PERIODS = [{ no: 1, start: "2026-11-16", end: "2026-11-22", bucket_type: "Hafta", days: 7 }, { no: 2, start: "2027-02-08", end: "2027-02-28", bucket_type: "Ay", days: 21 }];
type Sent = { bucket_type: string; count: number; span_unit: string };
const preview = (rows: Sent[]) => ({
  rows: rows.map((r, i) => PART(r.bucket_type, r.count, r.span_unit, `2027-0${i + 1}-01`, `2027-0${i + 1}-28`, 28)), start: null, end: null, buckets: rows.length,
  periods: rows.map((r, i) => ({ no: i + 1, start: `2027-0${i + 1}-01`, end: `2027-0${i + 1}-28`, bucket_type: r.bucket_type, days: 28 })) });

function backend(values: Record<string, string | null> = VALUES) {
  const sent: { method: string; url: string; body: { changes?: object; rows?: object[] } }[] = [];
  let current = { ...values };
  const record = (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    sent.push({ method: init?.method ?? "GET", url, body });
    return body;
  };
  mockApi({
    "/api/scenarios/current": { body: { id: 1, name: "Baz" } },
    "/api/parameters/objectives": (url: string, init?: RequestInit) => {
      if (init?.method !== "PUT") return { body: { rows: OBJECTIVES, total_seconds: 660 } };
      const rows = record(url, init).rows as { id: number; active: boolean; seconds: number | null; tolerance: number | null }[];
      let seq = 0;
      return { body: { rows: rows.map((r) => ({ ...OBJECTIVES.find((o) => o.id === r.id)!, ...r, seq: r.active ? ++seq : null })), total_seconds: 0 } };
    },
    "/api/parameters/time-buckets/plan/preview": (url: string, init?: RequestInit) => {
      const rows = record(url, init).rows as { bucket_type: string; count: number; span_unit: string }[];
      return { body: preview(rows) };
    },
    "/api/parameters/time-buckets/rapor/preview": (url: string, init?: RequestInit) => ({ body: preview(record(url, init).rows as Sent[]) }),
    "/api/parameters/time-buckets/plan": (url: string, init?: RequestInit) => {
      const base = { rows: PLAN, periods: PERIODS, start: "2026-11-16", end: "2027-07-31", buckets: 17, bucket_types: ["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"], span_units: ["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"] };
      if (init?.method !== "PUT") return { body: base };
      const rows = record(url, init).rows as { bucket_type: string; count: number; span_unit: string }[];
      return { body: { ...base, ...preview(rows) } };
    },
    "/api/parameters/time-buckets/rapor": { body: { rows: [], periods: [], start: null, end: null, buckets: 0, bucket_types: ["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"], span_units: ["Gün", "Hafta", "Ay"] } },
    "/api/parameters": (url: string, init?: RequestInit) => {
      if (init?.method === "PUT") current = { ...current, ...Object.fromEntries(Object.entries(record(url, init).changes as Record<string, unknown>).map(([k, v]) => [k, v === true ? "1" : v === false ? "0" : (v as string | null)])) };
      return { body: { scenario: { id: 1, name: "Baz" }, sections: SECTIONS, values: current, computed: { fix_period_end: "2026-11-29" } } };
    },
  });
  return sent;
}

async function open(path = "/parametre/parametreler", role = "Key user", values = VALUES) {
  const user = userEvent.setup();
  const sent = backend(values);
  const { router } = renderApp(path, meAs(role));
  await screen.findByRole("heading", { name: "Parametreler" }, { timeout: 5000 });
  return { user, sent, router };
}
const tabs = () => screen.getByRole("radiogroup", { name: "Parametre başlıkları" });
const save = () => screen.getByRole("button", { name: "Kaydet" });
const cancel = () => screen.getByRole("button", { name: "Vazgeç" });
const cell = (table: HTMLElement, row: number, col: number) => within(table).getAllByRole("row")[row].querySelectorAll("td")[col] as HTMLElement;

describe("ekran 06 · Parametreler", () => {
  it("ana başlıklar şeritte, alt başlıklar solda; tek alt başlıkta menü yok; bağlam çubuğunda Senaryo: Baz", async () => {
    const { user } = await open();
    await waitFor(() => expect(within(tabs()).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Model", "Hedefler", "Malzeme", "Kapasite", "Plan kararlılığı", "Planlama ufku"]));
    expect(within(screen.getByRole("navigation", { name: "Model bölümleri" })).getAllByRole("button").map((b) => b.textContent)).toEqual(["Model tipi", "Çözüm"]);
    await waitFor(() => expect(screen.getByTestId("scenario")).toHaveTextContent("Senaryo: Baz"));
    await user.click(within(tabs()).getByRole("radio", { name: "Kapasite" }));
    expect(await screen.findByRole("switch", { name: "Fazla mesai kullanılsın" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Kapasite bölümleri" })).toBeNull();
    await user.click(within(tabs()).getByRole("radio", { name: "Malzeme" }));
    await user.click(within(screen.getByRole("navigation", { name: "Malzeme bölümleri" })).getByRole("button", { name: "Güvenlik stoğu" }));
    expect(within(screen.getByRole("radiogroup", { name: "Güvenlik stoğu" })).getByRole("radio", { name: "Yumuşak hedef" })).toHaveAttribute("aria-checked", "true");
  });

  it("form kartı: değişiklik yokken düğmeler pasif; LP'de lot anahtarı pasif, MILP'te açılır; yalnız değişen gönderilir; bildirim yok", async () => {
    const { user, sent } = await open();
    await screen.findByRole("radiogroup", { name: "Model tipi" });
    expect(save()).toBeDisabled();
    expect(cancel()).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Üretimde minimum lot" })).toBeDisabled();
    await user.click(within(screen.getByRole("radiogroup", { name: "Model tipi" })).getByRole("radio", { name: "MILP" }));
    expect(save()).toBeEnabled();
    const lot = screen.getByRole("switch", { name: "Üretimde minimum lot" });
    expect(lot).toBeEnabled();
    expect(lot.closest("label")?.className).toContain("sc-toggle--md");                      // 44×24 anahtar
    await user.click(lot);
    await user.click(save());
    await waitFor(() => expect(sent.find((s) => s.method === "PUT")?.body).toEqual({ changes: { ModelType: "MILP", ProductionMinLot: "1" } }));
    await waitFor(() => expect(save()).toBeDisabled());
    expect(screen.queryByText(/kaydedildi/i)).toBeNull();
    await user.click(screen.getByRole("switch", { name: "Satın alma önerisini sipariş lotuna yuvarla" }));
    await user.click(cancel());                                                             // Vazgeç taslağı atar
    expect(screen.getByRole("switch", { name: "Satın alma önerisini sipariş lotuna yuvarla" })).toBeChecked();
  });

  it("kaydedilmemiş değişiklikle başlık değişirken uyarı; vazgeçince taslak atılır", async () => {
    const { user, router } = await open();
    await user.click(await screen.findByRole("switch", { name: "Satın alma önerisini sipariş lotuna yuvarla" }));
    await user.click(within(tabs()).getByRole("radio", { name: "Malzeme" }));
    const dialog = screen.getByRole("dialog", { name: "Kaydedilmemiş değişiklikler var" });
    expect(router.state.location.search).not.toContain("malzeme");
    await user.click(within(dialog).getByRole("button", { name: /Kaydetmeden/ }));
    await waitFor(() => expect(router.state.location.search).toContain("sekme=malzeme"));
    await user.click(within(tabs()).getByRole("radio", { name: "Model" }));
    expect(await screen.findByRole("switch", { name: "Satın alma önerisini sipariş lotuna yuvarla" })).toBeChecked();
  });

  it("Hedefler: hücre düzenleme, toplam, kapatma, sürükleme; Kaydet tablonun altında ve sırayla gönderir", async () => {
    const { user, sent } = await open("/parametre/parametreler?sekme=hedefler");
    const table = await screen.findByRole("table", { name: "Hedefler" });
    const rows = () => within(table).getAllByRole("row").slice(1, -1).map((r) => r.querySelectorAll("td")[1].textContent);
    expect(rows()).toEqual(["Karşılanmayan talep", "Gecikme", "Fazla mesai", "Önceki plandan sapma"]);
    expect(within(table).getByRole("columnheader", { name: /Süre bütçesi/ })).toHaveTextContent("✎");
    expect(within(table).getAllByRole("row").at(-1)).toHaveTextContent("Toplam660");
    expect(table.closest(".sc-settings-card")?.querySelector(".sc-settings-foot")).not.toBeNull();   // düğmeler tablonun altında
    expect(save()).toBeDisabled();
    await user.dblClick(cell(table, 2, 2));                                                          // Gecikme · süre
    const editor = within(table).getByRole("textbox");
    await user.clear(editor);
    await user.type(editor, "120{Enter}");
    expect(cell(table, 2, 2)).toHaveTextContent("120");
    expect(cell(table, 2, 2)).toHaveClass("is-draft");
    expect(within(table).getAllByRole("row").at(-1)).toHaveTextContent("Toplam480");
    await user.click(within(table).getByRole("switch", { name: "Fazla mesai aktif" }));               // kapanan hedef: değerleri boş, soluk
    expect(within(table).getAllByRole("row")[3]).toHaveClass("is-off");
    expect(cell(table, 3, 2)).toHaveTextContent("");
    const [first, second] = within(table).getAllByRole("row").slice(1, 3);                            // Karşılanmayan talep, Gecikme'nin arkasına sürüklenir
    const data = { effectAllowed: "", setData: () => undefined };
    fireEvent.dragStart(first, { dataTransfer: data });
    fireEvent.dragOver(second, { dataTransfer: data });
    fireEvent.drop(second, { dataTransfer: data });
    expect(rows().slice(0, 2)).toEqual(["Gecikme", "Karşılanmayan talep"]);
    await user.click(save());
    await waitFor(() => expect(sent.find((s) => s.method === "PUT")?.body.rows).toEqual([
      { id: 2, active: true, seconds: 120, tolerance: 0 }, { id: 1, active: true, seconds: 300, tolerance: 0 },
      { id: 3, active: false, seconds: null, tolerance: null }, { id: 4, active: false, seconds: null, tolerance: null }]));
  });

  it("Hedefler: geçersiz süre hücrede işaretlenir, Kaydet pasif", async () => {
    const { user } = await open("/parametre/parametreler?sekme=hedefler");
    const table = await screen.findByRole("table", { name: "Hedefler" });
    await user.dblClick(cell(table, 1, 2));
    await user.clear(within(table).getByRole("textbox"));
    await user.type(within(table).getByRole("textbox"), "0{Enter}");
    expect(cell(table, 1, 2)).toHaveClass("is-invalid");
    expect(cell(table, 1, 2)).toHaveAttribute("title", "1 ya da daha büyük tam sayı girilmeli.");
    expect(save()).toBeDisabled();
  });

  it("Ufuk ve dönemler: tarihler salt okunur; satır ekle, önizleme, şerit, sil, kayıt", async () => {
    const { user, sent } = await open("/parametre/parametreler?sekme=planlama-ufku");
    const table = await screen.findByRole("table", { name: "Ufuk ve dönemler" });
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Sıra", "Dönem tipi✎", "Kapsam✎", "Kapsam birimi✎", "Başlangıç", "Bitiş", ""]);
    expect(cell(table, 1, 4)).toHaveTextContent("16.11.2026");
    expect(cell(table, 1, 5)).toHaveTextContent("31.01.2027");
    await user.dblClick(cell(table, 1, 4));                                                          // Başlangıç düzenlenmez
    expect(within(table).queryByRole("textbox")).toBeNull();
    expect(screen.getByRole("img", { name: "Ufuk" })).toHaveTextContent("3 ay · haftalık6 ay · aylık");
    const list = screen.getByRole("table", { name: "Dönem listesi" });                              // hesaplanan dönemler, salt okunur
    expect(within(list).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Dönem", "Başlangıç", "Bitiş", "Dönem tipi", "Gün sayısı"]);
    expect(within(list).getAllByRole("row")[2]).toHaveTextContent("208.02.202728.02.2027Ay21");     // yarım ay görünür
    await user.dblClick(cell(list, 1, 4));
    expect(within(list).queryByRole("textbox")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Satır ekle" }));
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    await waitFor(() => expect(sent.at(-1)?.url).toContain("/preview"));
    expect(sent.at(-1)?.body.rows).toEqual([{ bucket_type: "Hafta", count: 3, span_unit: "Ay" }, { bucket_type: "Ay", count: 6, span_unit: "Ay" },
                                            { bucket_type: "Ay", count: 1, span_unit: "Ay" }]);
    await waitFor(() => expect(cell(table, 3, 4)).toHaveTextContent("01.03.2027"));                  // tarihler taslaktan
    expect(within(list).getAllByRole("row")).toHaveLength(4);                                        // dönem listesi kaydetmeden güncellenir
    await user.dblClick(cell(table, 3, 3));                                                          // kapsam birimi açılır liste
    expect(within(within(table).getByRole("combobox")).getAllByRole("option").map((o) => o.textContent)).toEqual(["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"]);
    await user.selectOptions(within(table).getByRole("combobox"), "Hafta");
    expect(cell(table, 3, 3)).toHaveTextContent("Hafta");
    await user.click(within(table).getByRole("button", { name: "1. satır işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Sil" }));
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    await user.click(save());
    await waitFor(() => expect(sent.find((s) => s.method === "PUT")?.body.rows).toEqual([
      { bucket_type: "Ay", count: 6, span_unit: "Ay" }, { bucket_type: "Ay", count: 1, span_unit: "Hafta" }]));
  });

  it("Raporlama ekseni: anahtar kapatılınca ikinci tablo kaydetmeden açılır, açılınca kapanır; kayıt Kaydet ile", async () => {
    const { user, sent } = await open("/parametre/parametreler?sekme=planlama-ufku&bolum=raporlama-ekseni");
    const toggle = await screen.findByRole("switch", { name: "Raporlama ekseni planla aynı" });
    expect(toggle).toBeChecked();
    expect(screen.queryByRole("table")).toBeNull();
    await user.click(toggle);
    expect(await screen.findByRole("table", { name: "Raporlama ekseni dönemleri" })).toBeInTheDocument();
    expect(sent.some((x) => x.method === "PUT")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Satır ekle" }));                           // tablonun taslağı
    await user.click(toggle);                                                                       // yeniden "planla aynı": tablo ve taslağı kalkar
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getAllByRole("button", { name: "Kaydet" })).toHaveLength(1);
    expect(save()).toBeDisabled();
  });

  it("sabit dönem: değer ve birim tek satırda; kayıtlı değerin son günü altında; ikisi birlikte gönderilir", async () => {
    const { user, sent } = await open("/parametre/parametreler?sekme=plan-kararliligi");
    const value = await screen.findByRole("textbox", { name: "Sabit dönem" });
    const row = value.closest(".sc-field") as HTMLElement;
    expect(value).toHaveValue("2");
    expect(within(row).getByRole("radiogroup", { name: "Sabit dönem birimi" })).toBeInTheDocument();
    expect(within(row).getByRole("radio", { name: "Hafta" })).toHaveAttribute("aria-checked", "true");
    expect(row).toHaveTextContent("Sabit dönem son günü: 29.11.2026");
    expect(screen.queryByText("Sabit dönem birimi")).toBeNull();                                    // birim ayrı satır değil
    await user.click(within(row).getByRole("radio", { name: "Ay" }));
    expect(row).not.toHaveTextContent("Sabit dönem son günü");                                    // taslakta eski tarih gösterilmez
    await user.clear(value);
    await user.type(value, "1{Enter}");
    await user.click(save());
    await waitFor(() => expect(sent.find((x) => x.method === "PUT")?.body).toEqual({ changes: { FixPeriod: "1", FixPeriodUnit: "Ay" } }));
  });

  it("Raporlama ekseni ayrıysa dönem tablosu açılır", async () => {
    await open("/parametre/parametreler?sekme=planlama-ufku&bolum=raporlama-ekseni", "Key user", { ...VALUES, ReportAxisSameAsPlan: "0" });
    expect(await screen.findByRole("table", { name: "Raporlama ekseni dönemleri" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Satır ekle" })).toBeInTheDocument();
  });

  it("End user ekranı görmez", async () => {
    backend();
    renderApp("/parametre/parametreler", meAs("End user"));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Parametreler" })).toBeNull());
    expect(screen.queryByRole("link", { name: "Parametreler" })).toBeNull();
  });
});
