// Kabuğun paylaştığı durum: yazı boyutu (U-23) ve geçici kullanıcı (A-36; kayıtlı görünümler, K-89).
import { createContext, useContext } from "react";

import { DEFAULT_FONT_SIZE, type FontSize } from "../prefs";

export interface ShellState {
  userId: number;
  fontSize: FontSize;
  setFontSize(size: FontSize): void;
}

export const ShellContext = createContext<ShellState>({ userId: 0, fontSize: DEFAULT_FONT_SIZE, setFontSize: () => {} });

export const useShell = () => useContext(ShellContext);
