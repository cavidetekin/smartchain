// Menünün ve ekranların tek tanımı (docs/12, K-82). Yeni ekran önce buraya eklenir.
// step: ekranın geleceği geliştirme adımı (GELISTIRME_ADIMLARI.md); description: docs/05'teki tek satır.
import type { LucideIcon } from "lucide-react";
import {
  Activity, Boxes, CalendarClock, CalendarRange, ChartGantt, ClipboardList, Database, Factory, FileChartColumn,
  FlaskConical, Gauge, HeartPulse, House, KeyRound, Layers, Lightbulb, Moon, Network, Package, Plug, Send, Settings,
  ShieldCheck, SlidersHorizontal, SlidersVertical, Table2, TriangleAlert, Upload, Users, WandSparkles,
} from "lucide-react";

export type GroupId = "planlama" | "takip" | "veri" | "parametre" | "yonetim";

export interface Screen {
  no: string;
  name: string;
  path: string;
  group: GroupId | null;
  /** Bir ekranın altında listelenir (ör. çalışmanın ekranları Çalışma'nın altında). */
  parent?: string;
  step: string;
  description: string;
  icon: LucideIcon;
  /** Çalışma açık değilken gri ve kapalı (K-43, K-82). */
  requiresWorkspace?: boolean;
}

export interface Group {
  id: GroupId;
  icon: LucideIcon;
}

// Menü sırası: Ana sayfa · Planlama · Takip · Veri · Parametre · Yönetim (K-82).
export const GROUPS: Group[] = [
  { id: "planlama", icon: CalendarRange },
  { id: "takip", icon: Activity },
  { id: "veri", icon: Database },
  { id: "parametre", icon: SlidersHorizontal },
  { id: "yonetim", icon: Settings },
];

const W = { group: "planlama" as const, parent: "09", requiresWorkspace: true };

export const SCREENS: Screen[] = [
  { no: "01", name: "Ana sayfa", path: "/ana-sayfa", group: null, step: "9.1", icon: House,
    description: "Gece akışının özeti, kritik uyarılar, dünden bugüne veride ve planda ne değişti." },

  { no: "08", name: "Senaryolar", path: "/planlama/senaryolar", group: "planlama", step: "8.1", icon: Layers,
    description: "Gece senaryolarının listesi, durumu ve metrikleri; yan yana karşılaştırma; çalışma açma." },
  { no: "09", name: "Çalışma", path: "/planlama/calisma", group: "planlama", step: "8.2", icon: FlaskConical,
    description: "Bir senaryo üzerindeki çalışma alanı: özet metrikler, yapılan değişiklikler, yeniden hesap." },
  { ...W, no: "10", name: "Kaynak doluluk", path: "/planlama/calisma/kaynak-doluluk", step: "8.3", icon: Gauge,
    description: "Kaynak × dönem doluluğu; dünden farkı; detaya iniş." },
  { ...W, no: "11", name: "Ürün bazlı planlama", path: "/planlama/calisma/urun-bazli", step: "8.4", icon: Package,
    description: "Ürün × dönem: talep, üretim, stok projeksiyonu, kümülatif eksik." },
  { ...W, no: "12", name: "Kaynak bazlı planlama", path: "/planlama/calisma/kaynak-bazli", step: "8.5", icon: Factory,
    description: "Kaynak × dönem: yükü taşıma, alternatif kaynağa ya da fasona aktarma." },
  { ...W, no: "13", name: "Sipariş bazlı planlama", path: "/planlama/calisma/siparis-bazli", step: "8.6",
    icon: ClipboardList, description: "Sipariş satırları, planlanan tarih, gecikme ve nedeni; öncelik ve hedef tarih." },
  { ...W, no: "14", name: "Gantt", path: "/planlama/calisma/gantt", step: "8.7", icon: ChartGantt,
    description: "Kaynak ya da sipariş satırlı, dönem sınırına oturan sürükle-bırak." },
  { ...W, no: "15", name: "Malzeme planı", path: "/planlama/calisma/malzeme-plani", step: "8.9", icon: Boxes,
    description: "Malzeme × dönem: brüt ihtiyaç, arz, stok projeksiyonu, eksik." },
  { ...W, no: "16", name: "Öneriler", path: "/planlama/calisma/oneriler", step: "8.10", icon: Lightbulb,
    description: "Planlı siparişler ve mevcut arz için öneriler." },
  { ...W, no: "17", name: "Pegging", path: "/planlama/calisma/pegging", step: "8.11", icon: Network,
    description: "Talepten aşağı, arzdan yukarı ağaç; eksikliğin nedeni." },
  { ...W, no: "18", name: "Termin ve olaylar", path: "/planlama/calisma/termin-olaylar", step: "10.12",
    icon: CalendarClock, description: "Ürün, miktar ve tarihle termin sorgusu; olay senaryolarıyla etki analizi." },
  { ...W, no: "19", name: "Yayın", path: "/planlama/calisma/yayin", step: "8.12", icon: Send,
    description: "Onaylı plan yayını; eski veri ve çakışma uyarıları." },

  { no: "20", name: "Uyarılar", path: "/takip/uyarilar", group: "takip", step: "9.2", icon: TriangleAlert,
    description: "Kategoriye ve öneme göre uyarılar; filtre, not, kapatma." },
  { no: "21", name: "Raporlar", path: "/takip/raporlar", group: "takip", step: "9.3", icon: FileChartColumn,
    description: "Onaylı plan ve senaryo raporları; Excel'e aktarım. Raporlar 9.4'te bu başlığın altına gelir." },

  { no: "02", name: "Veri yükleme", path: "/veri/veri-yukleme", group: "veri", step: "5.5", icon: Upload,
    description: "Çekilen veriyi görme, doğrulama sonucu, tam ya da kısmi yükleme, yükleme geçmişi." },
  { no: "03", name: "Ana veri", path: "/veri/ana-veri", group: "veri", step: "6.1", icon: Table2,
    description: "Kaynak, malzeme, ürün ağacı, rota, tedarikçi, müşteri, proje, takvim, vardiya." },
  { no: "04", name: "Veri kuralları", path: "/veri/veri-kurallari", group: "veri", step: "4.2", icon: WandSparkles,
    description: "Kural listesi, kural editörü, önizleme (kaç kayıt değişir)." },
  { no: "05", name: "Veri kalitesi", path: "/veri/veri-kalitesi", group: "veri", step: "6.5", icon: ShieldCheck,
    description: "Ana veri ve işlem verisi uyarıları; düzeltme listesi." },

  { no: "06", name: "Parametre setleri", path: "/parametre/parametre-setleri", group: "parametre", step: "7.1",
    icon: SlidersVertical, description: "Verim, dönem üst limitleri, fazla mesai limitleri, alokasyon, öncelik kuralı." },
  { no: "07", name: "Gece senaryoları", path: "/parametre/gece-senaryolari", group: "parametre", step: "7.6",
    icon: Moon, description: "Hangi senaryolar gece çalışır; parametre seti, eksen ayarları, öncelik." },

  { no: "22", name: "Kullanıcılar", path: "/yonetim/kullanicilar", group: "yonetim", step: "2.3", icon: Users,
    description: "Kullanıcı açma, kapatma, rol atama, şifre sıfırlama." },
  { no: "23", name: "Entegrasyon", path: "/yonetim/entegrasyon", group: "yonetim", step: "5.6", icon: Plug,
    description: "API, Excel ve SQL bağlantıları, servis hesapları, gece akışının zamanlaması." },
  { no: "24", name: "Sistem sağlığı", path: "/yonetim/sistem-sagligi", group: "yonetim", step: "2.5", icon: HeartPulse,
    description: "Son çalışmalar, iş kuyruğu, hatalar, çözüm süreleri; destek paketi." },
  { no: "25", name: "Sistem sahibi", path: "/yonetim/sistem-sahibi", group: "yonetim", step: "2.4", icon: KeyRound,
    description: "Veri sözlüğü, motor ayarları (çözücü, süre bütçesi, işçi sayısı), lisans." },
];

export const HOME = SCREENS[0];

export function screensInGroup(group: GroupId): Screen[] {
  return SCREENS.filter((s) => s.group === group && !s.parent);
}

export function childrenOf(no: string): Screen[] {
  return SCREENS.filter((s) => s.parent === no);
}

export function screenByPath(path: string): Screen | undefined {
  return SCREENS.find((s) => s.path === path);
}
