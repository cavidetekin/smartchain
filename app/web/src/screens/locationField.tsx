// Lokasyon alanı (K-194; docs/12 "Pencere ve form standardı"): lokasyon taşıyan kayıt giren her Yeni kayıt ve Düzenle penceresinde Lokasyon ayrı ve
// ilk alandır. Yeni kayıtta aramalı seçimdir; seçenek tekse dolu gelir (yine görünür). Düzenle'de kilitlidir. Pencerenin kod listeleri seçili
// lokasyona süzülür ve lokasyon değişince seçilmiş kod temizlenir (pencerenin işi; `onChange` içinde). Lokasyon listesi her pencerede verideki bütün
// lokasyonlardır (K-194 demo): "tek lokasyonda dolu gelir" veride tek lokasyon olmasına bakar; seçilen lokasyonda kayıt yoksa kod listesi boştur ve
// içinde "Bu lokasyonda kayıt yok." yazar. Ayrıca: veride birden çok lokasyon var mı (kart başlıkları ve zaman çubuğu kodu lokasyonla yazar).
import { useEffect, useMemo, useState } from "react";

import { getJson } from "../api/client";
import { tr } from "../i18n/tr";
import { SearchSelect, TextField } from "../ui";

export interface LocationOption { id: string; code: string; name?: string | null }

/** Kod listesinden lokasyonlar: sırası korunur, aynı lokasyon bir kez. */
export function locationsOf<T>(items: T[], pick: (item: T) => LocationOption | null): LocationOption[] {
  const seen = new Map<string, LocationOption>();
  for (const item of items) {
    const found = pick(item);
    if (found && !seen.has(found.id)) seen.set(found.id, found);
  }
  return [...seen.values()].sort((a, b) => a.code.localeCompare(b.code, "tr"));
}

/** Lokasyon seçimi: seçenekler gelince tek lokasyon varsa dolu gelir. start: dolu gelen lokasyon (karttan, satırdan, zaman çubuğundan). */
export function useLocationChoice(options: LocationOption[] | null, start = ""): [string, (value: string) => void] {
  const [value, setValue] = useState(start);
  useEffect(() => {
    if (options && options.length === 1 && value === "") setValue(options[0].id);
  }, [options, value]);
  return [value, setValue];
}

/** Pencerenin ilk alanı. locked: Düzenle'de lokasyonun kodu (değişmez). */
export function LocationField({ options, value, onChange, error, locked }: {
  options: LocationOption[]; value: string; onChange(value: string): void; error?: string;
  locked?: string | null;
}) {
  return (
    <div className="sc-form-full">
      {locked !== undefined ? <TextField label={tr.capacity.location} value={locked ?? ""} onChange={() => undefined} disabled />
        : <SearchSelect label={tr.capacity.location} value={value} onChange={onChange} error={error} emptyText={tr.capacity.noMatch}
                        options={options.map((o) => ({ value: o.id, code: o.code, name: o.name ?? undefined }))} />}
    </div>
  );
}

let known: Promise<LocationOption[]> | null = null;
/** Verideki lokasyonlar (bir kez okunur; okunamazsa boş). */
export function allLocations(): Promise<LocationOption[]> {
  known ??= getJson<{ locations: { id: number; code: string; name: string | null }[] }>("/api/capacity/locations")
    .then((d) => d.locations.map((l) => ({ id: String(l.id), code: l.code, name: l.name })))
    .catch(() => { known = null; return []; });
  return known;
}
/** Pencerenin lokasyon listesi: verideki bütün lokasyonlar (kaydı olmayan lokasyon da listelenir). key "code": lokasyonun anahtarı kodudur (kaynak ve
 *  grup listeleri lokasyonu koduyla taşır). Lokasyonlar okunamazsa kod listesinden türetilenler (fallback). */
export function useLocations(fallback: LocationOption[] | null, key: "id" | "code" = "id"): LocationOption[] | null {
  const [all, setAll] = useState<LocationOption[] | null>(null);
  useEffect(() => {
    let alive = true;
    void allLocations().then((found) => { if (alive) setAll(found); });
    return () => { alive = false; };
  }, []);
  return useMemo(() => {
    if (all === null) return null;
    if (!all.length) return fallback;
    return key === "code" ? all.map((l) => ({ ...l, id: l.code })) : all;
  }, [all, fallback, key]);
}

/** Kod listesinin boş metni: seçili lokasyonda hiç kayıt yoksa "Bu lokasyonda kayıt yok."; yoksa aramada eşleşen olmadığını söyler. */
export const emptyTextOf = (location: string, count: number) => (location && count === 0 ? tr.capacity.noRecordsHere : tr.capacity.noMatch);

/** Testler arasında sıfırlanır. */
export function forgetLocations(): void { known = null; }

/** Veride birden çok lokasyon var mı: kart başlığı ve zaman çubuğu kodu lokasyonla yazar ("ORM-01 · T-01"); tek lokasyonda yalnız kod. */
export function useManyLocations(): boolean {
  const [many, setMany] = useState(false);
  useEffect(() => {
    let alive = true;
    void allLocations().then((all) => { if (alive) setMany(all.length > 1); });
    return () => { alive = false; };
  }, []);
  return many;
}

/** Kodun lokasyonla yazımı (birden çok lokasyonda). */
export const withLocation = (many: boolean, location: unknown, code: string) => (many && location ? `${String(location)} · ${code}` : code);
