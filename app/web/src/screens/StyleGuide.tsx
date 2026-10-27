// Stil örnekleri (/stil; K-85, docs/12). Ekran değildir, menüde yer almaz. Renk değerleri tokens.css'ten okunur.
import { Download, Lock, RefreshCw, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { FONT_SIZES } from "../prefs";
import { useShell } from "../shell/ShellContext";
import {
  Alert, Badge, Button, Card, Checkbox, DateField, KpiCard, NumberField, OccupancyCell, OccupancyLegend, RadioGroup,
  SearchField, Segment, SelectField, TextareaField, TextField, type OccupancyThresholds,
} from "../ui";

const T = tr.style;
const ALT_THRESHOLDS: OccupancyThresholds = { low: 30, normal: 60, risk: 85, over: 95 };
const OCC_SAMPLE = [38, 44, 72, 86, 92, 100.4, 104, 112];

function Swatch({ token, label }: { token: string; label?: string }) {
  const [value, setValue] = useState("");
  useEffect(() => {
    setValue(getComputedStyle(document.documentElement).getPropertyValue(`--${token}`).trim());
  }, [token]);
  return (
    <div className="sc-swatch">
      <span className="sc-swatch-color" style={{ background: `var(--${token})` }} />
      <span>{label ?? token}</span>
      <code className="sc-num sc-muted">--{token} {value}</code>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <h2>{title}</h2>
      {children}
    </Card>
  );
}

export function StyleGuide() {
  const { fontSize, setFontSize } = useShell();
  const [qty, setQty] = useState<number | null>(1234.5);
  const [date, setDate] = useState<Date | null>(new Date(2026, 9, 27));
  const [text, setText] = useState("Baz senaryo");
  const [note, setNote] = useState("");
  const [bucket, setBucket] = useState("hafta");
  const [model, setModel] = useState("LP");
  const [check, setCheck] = useState(true);
  const [search, setSearch] = useState("");
  const [showAlert, setShowAlert] = useState(true);

  return (
    <section className="sc-page">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
        <p className="sc-muted">{T.intro}</p>
      </header>
      <div className="sc-guide">
        <Section title={T.sections.palette}>
          <p className="sc-muted">{T.usage.lead}</p>
          <div className="sc-grid">
            {["lead-50", "lead-100", "lead-300", "lead-600", "lead-700", "lead-900"].map((t) => <Swatch key={t} token={t} />)}
          </div>
          <p className="sc-muted">{T.usage.indigo}</p>
          <div className="sc-grid">
            {["indigo-50", "indigo-100", "indigo-300", "indigo-500", "indigo-700", "indigo-900"].map((t) => <Swatch key={t} token={t} />)}
          </div>
        </Section>

        <Section title={T.sections.status}>
          <div className="sc-grid">
            <Swatch token="status-risk" label={T.usage.risk} />
            <Swatch token="status-over" label={T.usage.over} />
            <Swatch token="status-ok" label={T.usage.ok} />
            <Swatch token="info" label={T.usage.info} />
          </div>
        </Section>

        <Section title={T.sections.occupancy}>
          <div className="sc-row">
            {OCC_SAMPLE.map((v, i) => <OccupancyCell key={v} value={v} delta={i % 3 === 0 ? -1 : i + 1} />)}
          </div>
          <OccupancyLegend />
          <p className="sc-muted">{T.thresholdsNote}</p>
          <div className="sc-row" data-testid="occ-alt">
            {OCC_SAMPLE.map((v) => <OccupancyCell key={v} value={v} thresholds={ALT_THRESHOLDS} />)}
          </div>
          <OccupancyLegend thresholds={ALT_THRESHOLDS} />
        </Section>

        <Section title={T.sections.type}>
          <Segment label={tr.user.fontSize} value={fontSize} onChange={setFontSize}
                   options={FONT_SIZES.map((s) => ({ value: s, label: `${tr.user.fontSizes[s]} ${s}` }))} />
          {["xs", "sm", "base", "md", "lg", "xl", "2xl", "kpi"].map((s) => (
            <div key={s} className="sc-type-row">
              <code>--fs-{s}</code>
              <span style={{ fontSize: `var(--fs-${s})` }}>{T.sample}</span>
            </div>
          ))}
          <div className="sc-type-row">
            <code>--font-num</code>
            <span className="sc-num">{formatNumber(1234.5, 1)} · 27.10.2026 · H44</span>
          </div>
        </Section>

        <Section title={T.sections.buttons}>
          <div className="sc-row">
            <Button variant="primary" icon={RefreshCw}>Yeniden hesapla</Button>
            <Button icon={Download}>Dışa aktar</Button>
            <Button variant="ghost">Talebe eşitle</Button>
            <Button variant="danger" icon={Trash2}>İptal et</Button>
            <Button size="sm" icon={Save}>Kaydet</Button>
            <Button disabled title="Önce bir çalışma açın">Yayına hazırla</Button>
            <Button variant="primary" busy>Kaydet</Button>
          </div>
        </Section>

        <Section title={T.sections.badges}>
          <div className="sc-row">
            <Badge>taslak</Badge>
            <Badge tone="info">bilgi</Badge>
            <Badge tone="ok">tamam</Badge>
            <Badge tone="risk">yüksek</Badge>
            <Badge tone="critical">kritik</Badge>
            <Badge tone="critical">süre aşımı</Badge>
            <Badge tone="info">12</Badge>
          </div>
        </Section>

        <Section title={T.sections.cards}>
          <div className="sc-grid">
            <KpiCard label="Ortalama doluluk" value="%76" note="8 kaynak · 8 hafta" />
            <KpiCard label="Aşırı yüklü kaynak-hafta" value="5" tone="over" note="Doluluk %100 üstü" />
            <KpiCard label="Zamanında teslim" value="%92,4" tone="ok" note="dün %93,1" />
            <KpiCard label="Kapasite açığı" value="28 sa" note="Fazla mesai veya fason ile kapanmalı" />
          </div>
          <Card title="Kaynak × hafta doluluğu" subtitle="Detay için bir kaynak seçin"
                actions={<Button size="sm" icon={Download}>Dışa aktar</Button>}>
            <p className="sc-muted">Kart başlığı, alt başlık ve sağda aksiyon.</p>
          </Card>
        </Section>

        <Section title={T.sections.forms}>
          <div className="sc-stack">
            <SearchField label="Malzeme ara" value={search} onChange={setSearch} />
            <div className="sc-grid">
              <TextField label="Senaryo adı" value={text} onChange={setText} required help="En çok 100 karakter" />
              <NumberField label="Planlanan miktar (adet)" value={qty} onChange={setQty} decimals={1} />
              <NumberField label="Fazla mesai (sa)" value={null} onChange={() => {}} error="Fazla mesai sınırı 20 sa" />
              <DateField label="Teslim tarihi" value={date} onChange={setDate} />
              <SelectField label="Model tipi" value={model} onChange={setModel}
                           options={[{ value: "LP", label: "LP" }, { value: "MILP", label: "MILP" }]} />
              <TextField label="Veri versiyonu" value="v43" onChange={() => {}} disabled />
              <TextareaField label="Neden (bildirimde görünür)" value={note} onChange={setNote} />
            </div>
            <div className="sc-row sc-row--top">
              <Segment<string> label="Dönem" value={bucket} onChange={setBucket}
                       options={[{ value: "gun", label: "Günlük" }, { value: "hafta", label: "Haftalık" }, { value: "ay", label: "Aylık" }]} />
              <RadioGroup label="Kaynak kısıtı" value="Kısıtlı" onChange={() => {}}
                          options={["Kısıtsız", "Kısıtlı", "Kısmi"].map((v) => ({ value: v, label: v }))} />
            </div>
            <div className="sc-row">
              <Checkbox label="Fazla mesai dahil" checked={check} onChange={setCheck} />
              <Checkbox label="Dondurulmuş dönem" checked onChange={() => {}} disabled />
            </div>
          </div>
        </Section>

        <Section title={T.sections.alerts}>
          <div className="sc-guide">
            <Alert tone="info">Kısa işler (termin sorgusu) ayrı küçük kotadan çalışır; uzun hesapları beklemez.</Alert>
            <Alert tone="ok" title="Hesap bitti">Çalışma yeniden hesaplandı; 3 sipariş öne çekildi.</Alert>
            <Alert tone="risk">Freze merkezi H46–H47 doluluğu %98; risk sınırında.</Alert>
            {showAlert && (
              <Alert tone="error" title="Sıcak hesap sınırı dolu" onClose={() => setShowAlert(false)}>
                3 / 3 sürüyor. İsteğiniz sıraya alındı: 1. sırada, tahmini 1 dk 20 sn.
              </Alert>
            )}
          </div>
        </Section>

        <Section title={T.sections.cells}>
          <div className="sc-row">
            <span className="sc-cell">45</span>
            <span className="sc-cell sc-cell--manual" title="Manuel değişiklik">50</span>
            <span className="sc-cell sc-cell--frozen" title="Dondurulmuş dönem"><Lock aria-label="Dondurulmuş" role="img" />40</span>
            <span className="sc-cell sc-cell--shortage" title="Kümülatif eksik">-10</span>
          </div>
          <p className="sc-muted">Manuel değişiklik (U-4, U-16) · dondurulmuş dönem · kümülatif eksik. Tablo 1.3'te kullanır.</p>
        </Section>

        <Section title={T.sections.chart}>
          <div className="sc-row">
            {["İndigo", "Petrol", "Hardal", "Kurşun", "Erik", "Kahve"].map((name, i) => (
              <span key={name} className="sc-chart-swatch"><span className={`sc-chart-${i + 1}`} />{i + 1}. {name}</span>
            ))}
          </div>
        </Section>
      </div>
    </section>
  );
}
