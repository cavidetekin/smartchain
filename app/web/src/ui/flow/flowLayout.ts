// Akış çiziminin yerleşimi (docs/12 "Akış çizimi standardı", K-200): saf hesap, DOM yok. Seçili kutu ortada; sol dal sola, sağ dal sağa
// sütun sütun açılır. Yaprak kutular alt alta dizilir, üst kutu çocuklarının dikey ortasında durur; iki yan ayrı yerleşir ve seçili kutuda
// hizalanır. Aynı kutuya giren oklar ortak gövdede birleşir. Ölçüler rem'dir (dört yazı boyunda ölçeklenir). Ekrandaki SVG ve PNG çıktısı
// aynı yerleşimi çizer.

export type FlowSide = "left" | "right";
/** box: kayıt kutusu (en çok üç satır) · option: ara kutu (ör. "Alternatif 1") · more: "+N" kutusu (kalanı açar). */
export type FlowKind = "box" | "option" | "more";
/** none: açılacak bir şey yok (işaret çizilmez) · closed · busy (yükleniyor) · open · error. */
export type BranchState = "none" | "closed" | "busy" | "open" | "error";

export interface FlowBranch {
  state: BranchState;
  children?: FlowNode[];
  /** Dal yüklenemediyse kısa hata metni (kutunun yanında). */
  error?: string;
}

export interface FlowNode {
  /** Yol kimliği: aynı kayıt iki yoldan açılırsa iki ayrı düğümdür. */
  id: string;
  kind: FlowKind;
  /** box: kod · option ve more: kutunun yazısı. */
  title: string;
  /** box: ad · option: küçük açıklama (ör. versiyon kodları). */
  text?: string;
  /** box: tür (üçüncü satır). */
  meta?: string;
  /** Kutunun rengi (zemin, çerçeve, yazı): `--flow-<ton>-*` belirteçleri; verilmezse nötr. Seçili kutu her zaman "current". */
  tone?: string;
  /** Sağ üst köşede küçük, nötr etiket (ör. "veya G1"); tonu değiştirmez. */
  badge?: string;
  /** Bu kutuya gelen okun etiketi (ör. "×8 AD"): okun üstünde. */
  edge?: string;
  /** Etiketin ikinci satırı (ör. "Alternatif 1, 2"): okun altında. */
  edgeNote?: string;
  /** Kutunun kendi yönündeki dalı (sağdaki kutuda sağa, soldakinde sola). */
  branch?: FlowBranch;
}

export interface FlowModel { root: FlowNode; left: FlowBranch; right: FlowBranch }

export const SIZE = {
  box: { w: 13, h: 4.4 }, option: { w: 9, h: 2.9 }, more: { w: 9, h: 2.2 },
  column: 22,          // sütun aralığı (kutu + ok ve etiket)
  row: 5.3,            // satır aralığı
  pad: 3,              // çizimin dört yanındaki sabit boşluk
  toggle: 0.7,         // + işaretinin yarıçapı
  stem: 1.6,           // ortak gövde ile kutu (işaret) arasındaki tek çizgi
  corner: 0.9,         // gövdeye giriş ve çıkıştaki yuvarlak köşe
  badgePad: 0.45, badgeChar: 0.43, badgeH: 1.15,
};
/** Çizim birimi: 1 rem = 10 birim (yazı ölçüleri birimde). */
export const U = 10;
export const FONT = { title: 9.2, text: 9.2, meta: 8.5, option: 9.2, optionText: 8, more: 9.2, edge: 8.5, edgeNote: 8, badge: 7.5, toggle: 10.5 };
const MAX = { title: 20, text: 24, meta: 26, option: 16, badge: 13 };

export const cut = (text: string, max: number) => (text.length > max ? `${text.slice(0, Math.max(1, max - 1))}…` : text);
/** Etiketin yazısı ve genişliği (rem). */
export function badgeOf(node: FlowNode): { text: string; w: number } | null {
  if (!node.badge) return null;
  const text = cut(node.badge, MAX.badge);
  return { text, w: text.length * SIZE.badgeChar + SIZE.badgePad * 2 };
}
/** Kutunun görünen satırları: kod etikete yer bırakacak kadar kesilir. */
export function linesOf(node: FlowNode): { title: string; text?: string; meta?: string } {
  if (node.kind === "option") return { title: cut(node.title, MAX.option), text: node.text ? cut(node.text, MAX.option) : undefined };
  if (node.kind === "more") return { title: node.title };
  const badge = badgeOf(node);
  const room = badge ? Math.floor((SIZE.box.w - 1.6 - badge.w) / 0.6) : MAX.title;
  return { title: cut(node.title, Math.min(MAX.title, Math.max(4, room))), text: node.text ? cut(node.text, MAX.text) : undefined, meta: node.meta ? cut(node.meta, MAX.meta) : undefined };
}

export interface Placed {
  node: FlowNode;
  side: FlowSide | "root";
  depth: number;
  /** Sol kenar ve dikey orta (rem). */
  x: number; cy: number; w: number; h: number;
  parent?: Placed;
}
export interface Toggle { id: string; node: FlowNode; side: FlowSide; cx: number; cy: number; state: BranchState; error?: string }
/** Çizgi komutları (rem): M ve L uç nokta, Q denetim noktası ve uç. */
export type Cmd = ["M" | "L", number, number] | ["Q", number, number, number, number];
export interface Edge { id: string; cmds: Cmd[]; arrow: boolean }
export interface EdgeLabel { id: string; label?: string; note?: string; x: number; y: number; anchor: "start" | "end" }
export interface FlowLayout { width: number; height: number; nodes: Placed[]; toggles: Toggle[]; edges: Edge[]; labels: EdgeLabel[]; root: Placed }

interface Item { node: FlowNode; depth: number; y: number; kids: Item[]; branch?: FlowBranch; parent?: Item }

const open = (b?: FlowBranch): FlowNode[] => (b && b.state === "open" ? b.children ?? [] : []);

/** Yapraklar sırayla aşağı, üst düğüm çocuklarının ortasında. */
function lay(node: FlowNode, branch: FlowBranch | undefined, depth: number, st: { y: number; max: number; all: Item[] }, parent?: Item): Item {
  const item: Item = { node, depth, y: 0, kids: [], branch, parent };
  item.kids = open(branch).map((c) => lay(c, c.branch, depth + 1, st, item));
  if (item.kids.length === 0) {
    item.y = st.y;
    st.y += SIZE.row;
  } else {
    item.y = (item.kids[0].y + item.kids[item.kids.length - 1].y) / 2;
  }
  st.max = Math.max(st.max, depth);
  st.all.push(item);
  return item;
}

/** Ortak gövdede (x) `from` hizasından `to` hizasına yuvarlak köşeli dönüş; çizgi gövdeye sağdan girer, soldan çıkar. Aynı hizadaysa boş. */
function turn(x: number, from: number, to: number): Cmd[] {
  const dy = to - from;
  if (Math.abs(dy) < 0.01) return [];
  const r = Math.min(SIZE.corner, Math.abs(dy) / 2);
  const s = Math.sign(dy);
  return [["L", x + r, from], ["Q", x, from, x, from + s * r], ["L", x, to - s * r], ["Q", x, to, x - r, to]];
}

export function layoutFlow(model: FlowModel): FlowLayout {
  const right = { y: 0, max: 0, all: [] as Item[] };
  const left = { y: 0, max: 0, all: [] as Item[] };
  const rootRight = lay(model.root, model.right, 0, right);
  const rootLeft = lay(model.root, model.left, 0, left);
  const dyRight = Math.max(0, rootLeft.y - rootRight.y);
  const dyLeft = Math.max(0, rootRight.y - rootLeft.y);
  const x0 = SIZE.pad + left.max * SIZE.column;
  const width = SIZE.pad * 2 + (left.max + right.max) * SIZE.column + SIZE.box.w;
  const height = SIZE.pad * 2 + Math.max(right.y + dyRight, left.y + dyLeft) - (SIZE.row - SIZE.box.h);

  const placed = new Map<Item, Placed>();
  const place = (item: Item, side: FlowSide, dy: number): Placed => {
    const { w, h } = SIZE[item.node.kind];
    // sağda kutular sütunun soluna, solda sağına yaslanır (ara kutu dar olsa da oklar aynı kenardan çıkar)
    const x = side === "right" ? x0 + item.depth * SIZE.column : x0 - item.depth * SIZE.column + (SIZE.box.w - w);
    const p: Placed = { node: item.node, side: item.depth === 0 ? "root" : side, depth: item.depth, x, cy: SIZE.pad + item.y + dy + SIZE.box.h / 2, w, h,
                        parent: item.parent ? placed.get(item.parent) : undefined };
    placed.set(item, p);
    return p;
  };
  const root = place(rootRight, "right", dyRight);
  placed.set(rootLeft, root);
  // üstler çocuklardan önce yerleşsin (parent bağı için): derinliğe göre
  const order = (items: Item[]) => items.filter((i) => i.depth > 0).sort((a, b) => a.depth - b.depth);
  const nodes: Placed[] = [root, ...order(right.all).map((i) => place(i, "right", dyRight)), ...order(left.all).map((i) => place(i, "left", dyLeft))];

  const toggles: Toggle[] = [];
  const edges: Edge[] = [];
  const labels: EdgeLabel[] = [];
  const out = SIZE.toggle / 2;                   // işaretin merkezi kutunun kenarından bu kadar dışarıda (kutudaki yazıya değmesin)
  const gap = out + SIZE.toggle + 0.5;           // okun ucu ile kutu arasında işaretin yeri
  const add = (p: Placed, side: FlowSide, branch: FlowBranch | undefined, kids: Placed[]) => {
    if (!branch) return;
    if (p.node.kind !== "more" && branch.state !== "none") {
      toggles.push({ id: `${p.node.id}:${side}`, node: p.node, side, cx: side === "right" ? p.x + p.w + out : p.x - out, cy: p.cy, state: branch.state, error: branch.error });
    }
    if (!kids.length) return;
    // Ok malzemenin gittiği yönü gösterir (hep sağdan sola). Sağda: bileşenlerin çizgileri ortak gövdede birleşir, üst kutuya tek ok ucuyla girer.
    // Solda: bileşenden çıkan tek çizgi gövdede dallanır, her kullanana kendi ok ucuyla girer.
    if (side === "right") {
      const tip = p.x + p.w + gap;
      const trunk = tip + SIZE.stem;
      edges.push({ id: `${p.node.id}:stem:right`, cmds: [["M", trunk, p.cy], ["L", tip, p.cy]], arrow: true });
      for (const c of kids) {
        const bend = turn(trunk, c.cy, p.cy);
        edges.push({ id: c.node.id, cmds: [["M", c.x, c.cy], ...(bend.length ? bend : [["L", trunk, c.cy] as Cmd])], arrow: false });
        labels.push({ id: c.node.id, label: c.node.edge, note: c.node.edgeNote, x: c.x - 0.6, y: c.cy - 0.5, anchor: "end" });
      }
    } else {
      const start = p.x - gap;
      const trunk = start - SIZE.stem;
      edges.push({ id: `${p.node.id}:stem:left`, cmds: [["M", start, p.cy], ["L", trunk, p.cy]], arrow: false });
      for (const c of kids) {
        const tip = c.x + c.w + 0.5;
        const bend = turn(trunk, p.cy, c.cy);
        const first: Cmd = bend.length ? ["M", bend[0][1], bend[0][2]] : ["M", trunk, p.cy];
        edges.push({ id: c.node.id, cmds: [first, ...bend.slice(1), ["L", tip, c.cy]], arrow: true });
        labels.push({ id: c.node.id, label: c.node.edge, note: c.node.edgeNote, x: tip + 1, y: c.cy - 0.5, anchor: "start" });
      }
    }
  };
  const kidsOf = (items: Item[], item: Item) => items.filter((i) => i.parent === item).map((i) => placed.get(i)!);
  add(root, "right", model.right, kidsOf(right.all, rootRight));
  add(root, "left", model.left, kidsOf(left.all, rootLeft));
  for (const i of right.all) if (i.depth > 0) add(placed.get(i)!, "right", i.branch, kidsOf(right.all, i));
  for (const i of left.all) if (i.depth > 0) add(placed.get(i)!, "left", i.branch, kidsOf(left.all, i));
  return { width, height: Math.max(height, SIZE.box.h + SIZE.pad * 2), nodes, toggles, edges, labels: labels.filter((l) => l.label || l.note), root };
}

/** Çizgi komutlarından SVG yolu (çizim biriminde). */
export function pathOf(cmds: Cmd[]): string {
  const n = (v: number) => String(Math.round(v * U * 100) / 100);
  return cmds.map((c) => (c[0] === "Q" ? `Q${n(c[1])} ${n(c[2])},${n(c[3])} ${n(c[4])}` : `${c[0]}${n(c[1])} ${n(c[2])}`)).join(" ");
}
