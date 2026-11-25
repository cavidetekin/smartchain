// Akış çiziminin yerleşimi (docs/12 "Akış çizimi standardı", K-200): kapalı tek kutu, sütunlar, üst kutu çocuklarının ortasında, iki yanın
// hizası, dört yanda sabit boşluk, aynı kayıt iki yolda iki düğüm, işaretler, okların ortak gövdede birleşmesi ve tek ok ucu, etiket,
// köşe etiketi (kod yer bırakır), 16 seviyede genişlik.
import { describe, expect, it } from "vitest";

import { badgeOf, type Cmd, type FlowBranch, type FlowModel, type FlowNode, layoutFlow, linesOf, pathOf, SIZE } from "./flowLayout";

const box = (id: string, branch?: FlowBranch, edge?: string): FlowNode => ({ id, kind: "box", title: id, edge, branch });
const openBranch = (...children: FlowNode[]): FlowBranch => ({ state: "open", children });
const CLOSED: FlowBranch = { state: "closed" };
const NONE: FlowBranch = { state: "none" };
const model = (left: FlowBranch, right: FlowBranch): FlowModel => ({ root: box("root"), left, right });
type Layout = ReturnType<typeof layoutFlow>;
const at = (l: Layout, id: string) => l.nodes.find((n) => n.node.id === id)!;
const edge = (l: Layout, id: string) => l.edges.find((e) => e.id === id)!;
const first = (cmds: Cmd[]) => [cmds[0][1], cmds[0][2]];
const last = (cmds: Cmd[]) => { const c = cmds[cmds.length - 1]; return [c[c.length - 2] as number, c[c.length - 1] as number]; };

describe("layoutFlow", () => {
  it("kapalı: yalnız seçili kutu; açılacak yön varsa işareti, yoksa yok; dört yanda sabit boşluk", () => {
    const l = layoutFlow(model(NONE, CLOSED));
    expect(l.nodes.map((n) => n.node.id)).toEqual(["root"]);
    expect(l.toggles.map((t) => [t.side, t.state])).toEqual([["right", "closed"]]);
    expect(l.edges).toEqual([]);
    expect(l.width).toBeCloseTo(SIZE.pad * 2 + SIZE.box.w);
    expect(l.height).toBeCloseTo(SIZE.pad * 2 + SIZE.box.h);
    expect([l.root.x, l.root.cy - l.root.h / 2]).toEqual([SIZE.pad, SIZE.pad]);
    // + işareti boşluğun içinde kalır (kesilmez)
    expect(l.toggles[0].cx + SIZE.toggle).toBeLessThan(l.width);
  });

  it("sağ dal sağ sütunda, sol dal sol sütunda; üst kutu çocuklarının dikey ortasında; iki yan seçili kutuda hizalı", () => {
    const l = layoutFlow(model(openBranch(box("u1", NONE)), openBranch(box("a", CLOSED), box("b", NONE), box("c", NONE))));
    const root = at(l, "root");
    expect(at(l, "a").x).toBeCloseTo(root.x + SIZE.column);
    expect(at(l, "u1").x).toBeCloseTo(root.x - SIZE.column);
    expect([at(l, "a").cy, at(l, "b").cy, at(l, "c").cy].map((y) => Math.round((y - at(l, "a").cy) / SIZE.row))).toEqual([0, 1, 2]);
    expect(root.cy).toBeCloseTo(at(l, "b").cy);            // üç çocuğun ortası
    expect(at(l, "u1").cy).toBeCloseTo(root.cy);            // tek kullanan seçili kutuyla aynı hizada
    expect(l.width).toBeCloseTo(SIZE.pad * 2 + 2 * SIZE.column + SIZE.box.w);
    expect(Math.min(...l.nodes.map((n) => n.x))).toBeCloseTo(SIZE.pad);
    expect(Math.min(...l.nodes.map((n) => n.cy - n.h / 2))).toBeCloseTo(SIZE.pad);
    expect(l.toggles.map((t) => t.id).sort()).toEqual(["a:right", "root:left", "root:right"]);
  });

  it("sağda aynı kutuya giren oklar ortak gövdede birleşir: kutunun önünde tek ok ucu", () => {
    const l = layoutFlow(model(NONE, openBranch(box("a", NONE, "×8 AD"), box("b", NONE), box("c", NONE))));
    const root = at(l, "root");
    const stem = edge(l, "root:stem:right");
    expect(l.edges.filter((e) => e.arrow).map((e) => e.id)).toEqual(["root:stem:right"]);        // tek ok ucu
    expect(first(stem.cmds)[0]).toBeGreaterThan(last(stem.cmds)[0]);                              // sağdan sola, kutuya doğru
    expect(last(stem.cmds)[0]).toBeGreaterThan(root.x + root.w);
    const trunk = first(stem.cmds)[0];
    for (const id of ["a", "b", "c"]) {
      const e = edge(l, id);
      expect(first(e.cmds)).toEqual([at(l, id).x, at(l, id).cy]);                                  // bileşenin sol kenarından çıkar
      expect(last(e.cmds)[1]).toBeCloseTo(root.cy);                                               // gövdeden kutunun hizasına
      expect(Math.abs(last(e.cmds)[0] - trunk)).toBeLessThanOrEqual(SIZE.corner + 0.001);
    }
    expect(edge(l, "b").cmds).toHaveLength(2);                                                    // aynı hizada: düz çizgi
    expect(edge(l, "a").cmds.filter((c) => c[0] === "Q")).toHaveLength(2);                        // gövdeye yuvarlak köşeyle girer ve çıkar
    expect(pathOf(edge(l, "b").cmds)).toMatch(/^M[\d.]+ [\d.]+ L[\d.]+ [\d.]+$/);
    expect(l.labels).toEqual([expect.objectContaining({ id: "a", label: "×8 AD", anchor: "end" })]);
  });

  it("tek ok: görünüm düz çizgi ve tek ok ucu", () => {
    const l = layoutFlow(model(NONE, openBranch(box("a", NONE))));
    expect(edge(l, "a").cmds.every((c) => c[0] !== "Q")).toBe(true);
    expect(last(edge(l, "a").cmds)).toEqual(first(edge(l, "root:stem:right").cmds));              // gövdede kesintisiz
    expect(l.edges.filter((e) => e.arrow)).toHaveLength(1);
  });

  it("solda bileşenden çıkan çizgi gövdede dallanır, her kullanana kendi ok ucuyla girer", () => {
    const l = layoutFlow(model(openBranch(box("u1", NONE, "×2 AD"), box("u2", NONE)), NONE));
    expect(l.edges.filter((e) => e.arrow).map((e) => e.id).sort()).toEqual(["u1", "u2"]);
    expect(edge(l, "root:stem:left").arrow).toBe(false);
    for (const id of ["u1", "u2"]) {
      const e = edge(l, id);
      expect(first(e.cmds)[0]).toBeGreaterThan(last(e.cmds)[0]);                                  // sağdan sola
      expect(last(e.cmds)[0]).toBeGreaterThan(at(l, id).x + SIZE.box.w);                          // kullananın sağ kenarına girer
      expect(last(e.cmds)[1]).toBeCloseTo(at(l, id).cy);
    }
    expect(l.labels[0]).toMatchObject({ id: "u1", label: "×2 AD", anchor: "start" });
  });

  it("aynı kayıt iki yoldan açılırsa iki ayrı düğüm", () => {
    const l = layoutFlow(model(NONE, openBranch(box("d/1", openBranch({ ...box("d/1/9"), title: "H" })), box("d/2", openBranch({ ...box("d/2/9"), title: "H" })))));
    expect(l.nodes.filter((n) => n.node.title === "H").map((n) => n.node.id)).toEqual(["d/1/9", "d/2/9"]);
    expect(at(l, "d/1/9").cy).not.toBeCloseTo(at(l, "d/2/9").cy);
  });

  it("ara kutu ve \"+N\" kutusu: ara kutunun işareti var, \"+N\" kutusunun yok", () => {
    const option: FlowNode = { id: "d/a1", kind: "option", title: "Alternatif 1", text: "V1", branch: CLOSED };
    const more: FlowNode = { id: "d/+", kind: "more", title: "+5 malzeme" };
    const l = layoutFlow(model(NONE, openBranch(option, more)));
    expect(at(l, "d/a1").w).toBe(SIZE.option.w);
    expect(l.toggles.map((t) => t.id)).toEqual(["root:right", "d/a1:right"]);
  });

  it("köşe etiketi: kod etikete yer bırakacak kadar kesilir, ton ve öteki satırlar değişmez", () => {
    const node: FlowNode = { id: "x", kind: "box", title: "COK-UZUN-MALZEME-KODU-001", text: "Conta", meta: "Hammadde", tone: "raw", badge: "veya G1" };
    const badge = badgeOf(node)!;
    const plain = linesOf({ ...node, badge: undefined });
    const cut = linesOf(node);
    expect(badge.text).toBe("veya G1");
    expect(cut.title.length).toBeLessThan(plain.title.length);
    expect(cut.title.endsWith("…")).toBe(true);
    expect(cut.title.length * 0.6 + badge.w).toBeLessThanOrEqual(SIZE.box.w - 1.5);              // kod ve etiket üst üste binmez
    expect([cut.text, cut.meta]).toEqual(["Conta", "Hammadde"]);
    expect(badgeOf({ ...node, badge: "veya COK-UZUN-GRUP-ADI" })!.text.endsWith("…")).toBe(true);
    expect(linesOf({ ...node, title: "HAM-008" }).title).toBe("HAM-008");                         // kısa kod kesilmez
  });

  it("hata ve yükleniyor durumu işarete taşınır", () => {
    const l = layoutFlow(model({ state: "busy" }, { state: "error", error: "Yüklenemedi." }));
    expect(l.toggles.map((t) => [t.side, t.state, t.error])).toEqual([["right", "error", "Yüklenemedi."], ["left", "busy", undefined]]);
  });

  it("16 seviye: genişlik seviye sayısıyla büyür, yükseklik tek satır", () => {
    let branch: FlowBranch = NONE;
    for (let level = 15; level >= 1; level -= 1) branch = openBranch(box(`n${level}`, branch));
    const l = layoutFlow(model(NONE, branch));
    expect(l.nodes).toHaveLength(16);
    expect(l.width).toBeCloseTo(SIZE.pad * 2 + 15 * SIZE.column + SIZE.box.w);
    expect(new Set(l.nodes.map((n) => n.cy.toFixed(3))).size).toBe(1);
  });
});
