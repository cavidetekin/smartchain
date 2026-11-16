// Ayar ekranı düzeni (docs/12 "Ayar ekranı standardı"; K-164, K-165, K-166, K-175): birden çok bölümde solda alt menü, sağda sıkı kart; alanlar
// satır satır (ad solda, değer sağda), altında ince çizgi ve sağda Vazgeç ile Kaydet. Sistem ayarları ve Parametreler bu bileşenleri kullanır.
import { type ReactNode, useEffect, useState } from "react";

import { formatNumber, parseTrNumber } from "../format";
import { tr } from "../i18n/tr";
import { SwitchCell } from "../table/CellEditors";
import { Alert } from "./Alert";
import { Button } from "./Button";
import { Segment } from "./fields";
import { Tooltip } from "./Tooltip";

export interface SettingsSection { key: string; title: string }

/** Solda alt menü, sağda seçili bölüm; tek bölümde menü çıkmaz. */
export function SettingsLayout({ label, sections, current, onSelect, children }: {
  /** Menünün erişilebilir adı için sekmenin adı ("<ad> bölümleri"). */
  label: string; sections: SettingsSection[]; current: string; onSelect(key: string): void; children: ReactNode;
}) {
  if (sections.length <= 1) return <>{children}</>;
  return (
    <div className="sc-settings-body">
      <nav className="sc-settings-nav" aria-label={tr.ui.subMenu(label)}>
        {sections.map((s) => (
          <button key={s.key} type="button" aria-current={s.key === current ? "true" : undefined} onClick={() => onSelect(s.key)}>{s.title}</button>
        ))}
      </nav>
      {children}
    </div>
  );
}

/** Vazgeç ve Kaydet (K-166): değişiklik yokken ikisi pasif; kartın ve form içi tablonun altında, sağda. */
export function SettingsFoot({ dirty, busy, invalid, onDiscard, onSave }: {
  dirty: boolean; busy: boolean; invalid?: boolean; onDiscard(): void; onSave(): void;
}) {
  return (
    <footer className="sc-settings-foot">
      <Button variant="ghost" disabled={!dirty || busy} onClick={onDiscard}>{tr.ui.cancel}</Button>
      <Button variant="primary" busy={busy} disabled={!dirty || invalid} onClick={onSave}>{tr.ui.save}</Button>
    </footer>
  );
}

/** Bölüm kartı: alan satırları ve altında düğmeler. wide: seçenekli alanlar için geniş değer kolonu (Parametreler). */
export function SettingsCard({ title, wide, error, children, ...foot }: {
  title: string; wide?: boolean; error?: string | null; children: ReactNode;
  dirty: boolean; busy: boolean; invalid?: boolean; onDiscard(): void; onSave(): void;
}) {
  return (
    <div className="sc-settings-section">
      <section className={`sc-settings-card${wide ? " sc-settings-card--wide" : ""}`} aria-label={title}>
        <div className="sc-field-rows">{children}</div>
        <SettingsFoot {...foot} />
      </section>
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
}

function RowLabel({ label, tip }: { label: string; tip?: string }) {
  const name = <span className="sc-field-label">{label}</span>;
  return tip ? <Tooltip content={tip}>{name}</Tooltip> : name;
}

/** Evet/Hayır ayarı: ad solda, 44×24 anahtar değer kolonunda (K-165, K-166). */
export function SwitchRow({ label, checked, onToggle, disabled, tip }: {
  label: string; checked: boolean; onToggle(next: boolean): void; disabled?: boolean; tip?: string;
}) {
  return (
    <div className={`sc-field sc-switch-row${disabled ? " is-disabled" : ""}`}>
      <RowLabel label={label} tip={tip} />
      <SwitchCell label={label} checked={checked} editable={!disabled} size="md" onToggle={onToggle} />
    </div>
  );
}

/** Seçenekli ayar: ad solda, parçalı seçim değer kolonunda. */
export function ChoiceRow({ label, options, value, onChange, tip, error }: {
  label: string; options: readonly string[]; value: string; onChange(v: string): void; tip?: string; error?: string;
}) {
  return (
    <div className={`sc-field sc-choice-row${error ? " is-invalid" : ""}`}>
      <RowLabel label={label} tip={tip} />
      <Segment<string> label={label} hideLabel value={value} onChange={onChange} options={options.map((o) => ({ value: o, label: o }))} />
      {error && <p className="sc-field-error">{error}</p>}
    </div>
  );
}

/** Değer ve birimi tek satırda (ör. fix periyot: 2 · Hafta): dar sayı kutusu ve parçalı birim seçimi; altında isteğe bağlı bilgi satırı. */
export function UnitRow({ label, value, onValue, unit, units, onUnit, unitLabel, tip, error, help, disabled }: {
  label: string; value: number | null; onValue(v: number | null): void; unit: string; units: readonly string[]; onUnit(v: string): void;
  unitLabel: string; tip?: string; error?: string; help?: string; disabled?: boolean;
}) {
  const [text, setText] = useState(value === null ? "" : formatNumber(value));
  useEffect(() => setText((t) => (parseTrNumber(t) === value ? t : value === null ? "" : formatNumber(value))), [value]);
  const commit = () => onValue(text.trim() ? parseTrNumber(text) : null);
  return (
    <div className={`sc-field sc-unit-row${error ? " is-invalid" : ""}`}>
      <RowLabel label={label} tip={tip} />
      <div className="sc-unit-value">
        <input className="sc-input sc-input--number" inputMode="numeric" aria-label={label} aria-invalid={Boolean(error)} value={text} disabled={disabled}
               onChange={(e) => setText(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} />
        <Segment<string> label={unitLabel} hideLabel value={unit} onChange={onUnit} options={units.map((o) => ({ value: o, label: o, disabled }))} />
      </div>
      {error ? <p className="sc-field-error">{error}</p> : help ? <p className="sc-field-help">{help}</p> : null}
    </div>
  );
}
