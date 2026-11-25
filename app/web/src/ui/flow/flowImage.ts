// Akış çiziminin PNG çıktısı (docs/12 "Akış çizimi standardı", K-200): açık çizimin tamamı, %100 boyda, beyaz zeminde; üstte başlık satırı,
// altta renk açıklaması. Tarayıcıda, ekran dışı tuvalde çizilir (internetsiz; yazı tipleri sayfaya gömülü fontlardan, grafik görseliyle aynı
// yol, K-179). Ekrandaki SVG ile aynı yerleşimi ve aynı renk belirteçlerini kullanır; + işaretleri görsele girmez.
import { tokenColor } from "../palette";
import { badgeOf, type Cmd, FONT, type FlowLayout, linesOf, type Placed, SIZE } from "./flowLayout";

const REM = 13;                    // çıktı standart yazı boyunda (kullanıcının yazı boyundan bağımsız)
const SANS = '"Instrument Sans", "Segoe UI", sans-serif';
const NUM = 'Inter, "Segoe UI", sans-serif';
const MAX_SIDE = 16000;            // tarayıcıların tuval sınırının altında
const MAX_AREA = 100_000_000;

export interface FlowImageOptions {
  /** Başlık satırı (ör. "MAM-006 · Kaplin ünitesi · Lokasyon ORM-01"). */
  title: string;
  /** Başlığın altında kalın not (ör. benzetilen ürün). */
  note?: string;
  /** Renk açıklaması: ad ve ton. */
  legend: { label: string; tone: string }[];
}

const px = (rem: number) => rem * REM;
const unit = (u: number) => (u / 10) * REM;      // çizim birimi (yazı ölçüleri) → piksel
const tone = (name: string, part: "bg" | "border" | "text" | "meta") => tokenColor(`flow-${name}-${part}`);
export const toneOf = (p: Placed): string => (p.side === "root" ? "current" : p.node.kind === "option" ? "option" : p.node.tone ?? "box");

function rounded(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function trace(ctx: CanvasRenderingContext2D, cmds: Cmd[]) {
  ctx.beginPath();
  for (const c of cmds) {
    if (c[0] === "Q") ctx.quadraticCurveTo(px(c[1]), px(c[2]), px(c[3]), px(c[4]));
    else if (c[0] === "M") ctx.moveTo(px(c[1]), px(c[2]));
    else ctx.lineTo(px(c[1]), px(c[2]));
  }
  ctx.stroke();
}

/** Çıktının ölçüleri (piksel, ölçeksiz) ve ölçeği: çok büyük çizim tuval sınırına sığacak kadar küçülür. */
export function imageSize(layout: FlowLayout, options: FlowImageOptions): { width: number; height: number; head: number; foot: number; scale: number } {
  const head = options.note ? 62 : 44;
  const foot = 40;
  const width = Math.max(px(layout.width), 520);
  const height = head + px(layout.height) + foot;
  const scale = Math.min(2, MAX_SIDE / Math.max(width, height), Math.sqrt(MAX_AREA / (width * height)));
  return { width, height, head, foot, scale };
}

export async function flowPng(layout: FlowLayout, options: FlowImageOptions): Promise<Blob> {
  // gömülü yazı tipleri yüklü olsun (tuval yüklenmemiş fontu beklemez, yedek fontla çizer)
  await Promise.all([document.fonts.load(`600 12px ${NUM}`), document.fonts.load(`400 12px ${NUM}`), document.fonts.load(`400 12px ${SANS}`),
                     document.fonts.load(`600 12px ${SANS}`)]);
  await document.fonts.ready;
  const size = imageSize(layout, options);
  const el = document.createElement("canvas");
  el.width = Math.round(size.width * size.scale);
  el.height = Math.round(size.height * size.scale);
  const ctx = el.getContext("2d");
  if (!ctx) throw new Error("canvas");
  ctx.scale(size.scale, size.scale);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, size.width, size.height);
  ctx.textBaseline = "alphabetic";

  // başlık satırı
  const left = px(SIZE.pad);
  ctx.fillStyle = tokenColor("text");
  ctx.font = `600 15px ${SANS}`;
  ctx.fillText(options.title, left, 28);
  if (options.note) {
    ctx.font = `600 13px ${SANS}`;
    ctx.fillText(options.note, left, 48);
  }

  ctx.save();
  ctx.translate(0, size.head);
  // oklar: çizgi kalınlığı her yerde aynı; ok ucu son parçanın yönünde
  ctx.lineWidth = unit(1.3);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const e of layout.edges) {
    ctx.strokeStyle = tokenColor("flow-edge");
    trace(ctx, e.cmds);
    if (!e.arrow) continue;
    const end = e.cmds[e.cmds.length - 1];
    const prev = e.cmds[e.cmds.length - 2];
    const [ex, ey] = [end[end.length - 2] as number, end[end.length - 1] as number];
    const dir = Math.sign(ex - (prev[prev.length - 2] as number)) || -1;
    ctx.strokeStyle = tokenColor("flow-toggle-border");
    ctx.lineWidth = unit(1.5);
    ctx.beginPath();
    ctx.moveTo(px(ex) - dir * unit(6), px(ey) - unit(4));
    ctx.lineTo(px(ex), px(ey));
    ctx.lineTo(px(ex) - dir * unit(6), px(ey) + unit(4));
    ctx.stroke();
    ctx.lineWidth = unit(1.3);
  }
  // ok etiketleri (zeminli)
  for (const l of layout.labels) {
    const draw = (text: string, y: number, font: string) => {
      ctx.font = font;
      ctx.textAlign = l.anchor === "end" ? "right" : "left";
      ctx.lineWidth = unit(3);
      ctx.strokeStyle = "#ffffff";
      ctx.strokeText(text, px(l.x), y);
      ctx.fillStyle = tokenColor("flow-edge-text");
      ctx.fillText(text, px(l.x), y);
    };
    if (l.label) draw(l.label, px(l.y), `400 ${unit(FONT.edge)}px ${NUM}`);
    if (l.note) draw(l.note, px(l.y) + unit(15.5), `400 ${unit(FONT.edgeNote)}px ${SANS}`);
  }
  // kutular
  for (const p of layout.nodes) {
    const n = p.node;
    const t = n.kind === "more" ? "box" : toneOf(p);
    const x = px(p.x);
    const y = px(p.cy - p.h / 2);
    const w = px(p.w);
    const h = px(p.h);
    rounded(ctx, x, y, w, h, n.kind === "box" ? unit(5) : h / 2);
    ctx.fillStyle = tone(t, "bg");
    ctx.fill();
    ctx.lineWidth = unit(1);
    ctx.strokeStyle = tone(t, "border");
    if (n.kind === "more") ctx.setLineDash([unit(3), unit(2)]);
    ctx.stroke();
    ctx.setLineDash([]);
    const lines = linesOf(n);
    if (n.kind === "box") {
      ctx.textAlign = "left";
      ctx.fillStyle = tone(t, "text");
      ctx.font = `600 ${unit(FONT.title)}px ${NUM}`;
      ctx.fillText(lines.title, x + unit(10), y + unit(14.5));
      if (lines.text) {
        ctx.font = `400 ${unit(FONT.text)}px ${SANS}`;
        ctx.fillText(lines.text, x + unit(10), y + unit(26.5));
      }
      if (lines.meta) {
        ctx.fillStyle = tone(t, "meta");
        ctx.font = `400 ${unit(FONT.meta)}px ${SANS}`;
        ctx.fillText(lines.meta, x + unit(10), y + unit(38));
      }
      const badge = badgeOf(n);
      if (badge) {
        const bw = px(badge.w);
        const bh = px(SIZE.badgeH);
        rounded(ctx, x + w - bw - unit(5), y + unit(5), bw, bh, bh / 2);
        ctx.fillStyle = tokenColor("flow-badge-bg");
        ctx.fill();
        ctx.strokeStyle = tokenColor("flow-badge-border");
        ctx.stroke();
        ctx.fillStyle = tokenColor("flow-badge-text");
        ctx.textAlign = "center";
        ctx.font = `400 ${unit(FONT.badge)}px ${SANS}`;
        ctx.fillText(badge.text, x + w - bw / 2 - unit(5), y + unit(5) + bh - unit(3.4));
      }
    } else if (n.kind === "option") {
      ctx.textAlign = "center";
      ctx.fillStyle = tone(t, "text");
      ctx.font = `600 ${unit(FONT.option)}px ${SANS}`;
      ctx.fillText(lines.title, x + w / 2, y + unit(lines.text ? 12.5 : 18));
      if (lines.text) {
        ctx.fillStyle = tone(t, "meta");
        ctx.font = `400 ${unit(FONT.optionText)}px ${SANS}`;
        ctx.fillText(lines.text, x + w / 2, y + unit(23));
      }
    } else {
      ctx.textAlign = "center";
      ctx.fillStyle = tone("box", "meta");
      ctx.font = `400 ${unit(FONT.more)}px ${NUM}`;
      ctx.fillText(lines.title, x + w / 2, y + unit(14.5));
    }
  }
  ctx.restore();

  // renk açıklaması
  let lx = left;
  const ly = size.height - size.foot / 2;
  ctx.textAlign = "left";
  ctx.font = `400 12px ${SANS}`;
  for (const item of options.legend) {
    rounded(ctx, lx, ly - 7, 14, 14, 3);
    ctx.fillStyle = tone(item.tone, "bg");
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = tone(item.tone, "border");
    ctx.stroke();
    ctx.fillStyle = tokenColor("text-muted");
    ctx.fillText(item.label, lx + 20, ly + 4);
    lx += 20 + ctx.measureText(item.label).width + 22;
  }
  return new Promise<Blob>((resolve, reject) => el.toBlob((b) => (b ? resolve(b) : reject(new Error("png"))), "image/png"));
}
