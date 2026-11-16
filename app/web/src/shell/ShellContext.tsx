// Kabuğun paylaştığı durum: yazı boyutu (U-23), oturumdaki kullanıcının Id'si (K-97; kişisel tercihler), arka planda
// hazırlanan Excel aktarımları (K-91; bitince sağ altta bildirim) ve seçili senaryo (K-177).
import { createContext, useContext } from "react";

import { DEFAULT_FONT_SIZE, type FontSize } from "../prefs";

export interface TrackedExport {
  jobId: number;
  title: string;
  fileName: string;
  rows: number;
}

/** Seçili senaryo (K-177): senaryoya bağlı ekranlar bunun verisini gösterir. Pasif senaryo yalnız Senaryolar ekranından açılır. */
export interface ShellScenario { id: number; name: string; isBase: boolean; isActive: boolean }

export interface ShellState {
  userId: number;
  fontSize: FontSize;
  setFontSize(size: FontSize): void;
  trackExport(e: TrackedExport): void;
  /** Yüklenene kadar null. */
  scenario: ShellScenario | null;
  /** Senaryoya geçer ve seçimi hatırlatır; kaydedilmemiş değişiklik varsa önce onay ister. Geçildiyse true. */
  selectScenario(id: number): Promise<boolean>;
  /** Senaryolar değişince (ad, pasif, silme): seçili senaryo ve bağlam çubuğunun listesi yeniden okunur. */
  refreshScenario(): void;
  /** Artınca bağlam çubuğunun senaryo listesi yeniden okunur. */
  scenarioTick: number;
}

export const ShellContext = createContext<ShellState>({
  userId: 0, fontSize: DEFAULT_FONT_SIZE, setFontSize: () => {}, trackExport: () => {},
  scenario: null, selectScenario: async () => false, refreshScenario: () => {}, scenarioTick: 0,
});

export const useShell = () => useContext(ShellContext);
