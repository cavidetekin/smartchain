// Tarayıcıda hatırlanan tercihler (docs/12): açık gruplar, daraltılmış menü, yazı boyutu.
// Kullanıcıya göre ayrı tutulur; 2.3'te sunucudaki kullanıcı ayarına taşınır.
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

export function userPrefs(userId: number) {
  const key = (name: string) => `u${userId}.${name}`;
  return {
    openGroups: (): string[] => read<string[]>(key("openGroups"), ["planlama", "takip", "veri", "parametre", "yonetim"]),
    setOpenGroups: (groups: string[]) => write(key("openGroups"), groups),
    collapsed: (): boolean => read<boolean>(key("collapsed"), false),
    setCollapsed: (value: boolean) => write(key("collapsed"), value),
    fontSize: (): FontSize => {
      const v = read<number>(key("fontSize"), DEFAULT_FONT_SIZE);
      return (FONT_SIZES as readonly number[]).includes(v) ? (v as FontSize) : DEFAULT_FONT_SIZE;
    },
    setFontSize: (value: FontSize) => write(key("fontSize"), value),
  };
}

/** U-23: seviye bütün arayüzü ölçekler (ölçüler rem cinsinden). */
export function applyFontSize(size: FontSize): void {
  document.documentElement.style.fontSize = `${size}px`;
}
