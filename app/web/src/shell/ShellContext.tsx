// Kabuğun paylaştığı durum: yazı boyutu (U-23). Örnek sayfa ve kullanıcı menüsü aynı ayarı kullanır.
import { createContext, useContext } from "react";

import { DEFAULT_FONT_SIZE, type FontSize } from "../prefs";

export interface ShellState {
  fontSize: FontSize;
  setFontSize(size: FontSize): void;
}

export const ShellContext = createContext<ShellState>({ fontSize: DEFAULT_FONT_SIZE, setFontSize: () => {} });

export const useShell = () => useContext(ShellContext);
