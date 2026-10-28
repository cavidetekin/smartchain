// Kabuğun paylaştığı durum: yazı boyutu (U-23), geçici kullanıcı (A-36; kayıtlı görünümler, K-89) ve arka planda
// hazırlanan Excel aktarımları (K-91; bitince sağ altta bildirim).
import { createContext, useContext } from "react";

import { DEFAULT_FONT_SIZE, type FontSize } from "../prefs";

export interface TrackedExport {
  jobId: number;
  title: string;
  fileName: string;
  rows: number;
}

export interface ShellState {
  userId: number;
  fontSize: FontSize;
  setFontSize(size: FontSize): void;
  trackExport(e: TrackedExport): void;
}

export const ShellContext = createContext<ShellState>({
  userId: 0, fontSize: DEFAULT_FONT_SIZE, setFontSize: () => {}, trackExport: () => {},
});

export const useShell = () => useContext(ShellContext);
