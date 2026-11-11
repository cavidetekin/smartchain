// Tarayıcıda hatırlanan tercihler (docs/12): açık gruplar, daraltılmış menü. Kullanıcıya göre ayrı tutulur.
// Yazı boyutu kullanıcı kaydındadır (U-23, 2.3); tarayıcıdaki eski değer bir kez sunucuya taşınır.
// Tarayıcı depolaması kapalıysa (gizli pencere vb.) varsayılanlarla çalışır.

const PREFIX = "smartchain";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(`${PREFIX}.${key}`);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

/** Ana–detay düzeninde ayracın oranı, ekran başına (K-161). */
export const loadPaneRatio = (id: string): number | null => read<number | null>(`pane.${id}`, null);
export const savePaneRatio = (id: string, ratio: number): void => write(`pane.${id}`, ratio);

function remove(key: string): void {
  try {
    window.localStorage.removeItem(`${PREFIX}.${key}`);
  } catch {
    // depolama yoksa silinecek de yok
  }
}

function write(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(`${PREFIX}.${key}`, JSON.stringify(value));
  } catch {
    // depolama yoksa tercih yalnız bu oturumda geçerli
  }
}

export const FONT_SIZES = [12, 13, 14, 16] as const;
export type FontSize = (typeof FONT_SIZES)[number];
export const DEFAULT_FONT_SIZE: FontSize = 13;

/** Geçerli boyut ya da null (sunucudan gelen değer de buradan geçer). */
export function validFontSize(value: unknown): FontSize | null {
  return (FONT_SIZES as readonly unknown[]).includes(value) ? (value as FontSize) : null;
}

export function userPrefs(userId: number) {
  const key = (name: string) => `u${userId}.${name}`;
  return {
    openGroups: (): string[] => read<string[]>(key("openGroups"), ["planlama", "takip", "veri", "parametre", "yonetim"]),
    setOpenGroups: (groups: string[]) => write(key("openGroups"), groups),
    collapsed: (): boolean => read<boolean>(key("collapsed"), false),
    setCollapsed: (value: boolean) => write(key("collapsed"), value),
    /** 2.3'ten önce tarayıcıda kalmış yazı boyutu (yalnız taşıma için). */
    legacyFontSize: (): FontSize | null => validFontSize(read<number | null>(key("fontSize"), null)),
    clearLegacyFontSize: () => remove(key("fontSize")),
    /** Bildirimi çıkmış zamanlanmış iş çalıştırmaları (K-163): aynı durma her açılışta yeniden bildirilmez. */
    notifiedFlowRuns: (): number[] => read<number[]>(key("flowRuns"), []),
    setNotifiedFlowRuns: (ids: number[]) => write(key("flowRuns"), ids.slice(-50)),
  };
}

/** U-23: seviye bütün arayüzü ölçekler (ölçüler rem cinsinden). */
export function applyFontSize(size: FontSize): void {
  document.documentElement.style.fontSize = `${size}px`;
}
