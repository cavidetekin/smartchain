"""Yetki matrisi (fonksiyon 90; K-99, K-100): 4 rol × 98 fonksiyon, Faz 1'de kodda sabit, tek kaynak.

Grup düzeyi docs/06 fonksiyon 90'daki tabloyla birebirdir (test). Arayüz rolün düzeylerini GET /api/auth/me ile alır;
app/shared/permissions.json yalnız üretilmiş kopyadır (ön yüz testleri, ileride matris ekranı 2.4):

    python -m app.api.permissions        # app/shared/permissions.json'u yazar
"""
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

SYSTEM_OWNER, ADMIN, KEY_USER, END_USER = "System owner", "Admin", "Key user", "End user"
ROLES = (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)  # en geniş → en dar


class Level(StrEnum):
    FULL = "full"    # okur ve değiştirir
    OWNER = "owner"  # hepsini okur, yalnız kendi nesnesini değiştirir (F: kendi çalışması)
    SELF = "self"    # yalnız kendi kayıtlarını okur ve değiştirir (98: kendi kayıtları; 48: kendi işleri)
    READ = "read"    # salt okunur
    NONE = "none"


class Access(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class Function:
    no: int
    name: str
    group: str  # A..K


@dataclass(frozen=True)
class GroupRow:
    """Matrisin grup satırı (mockup m24f-0743: 11 grup, K üç satır)."""
    key: str
    letter: str
    name: str
    first: int
    last: int
    levels: tuple[Level, Level, Level, Level]  # ROLES sırasıyla


F, R, O, S, N = Level.FULL, Level.READ, Level.OWNER, Level.SELF, Level.NONE

GROUP_ROWS: tuple[GroupRow, ...] = (
    GroupRow("A", "A", "Veri alma", 1, 9, (F, F, F, N)),
    GroupRow("B", "B", "Ana veri ve kurallar", 10, 21, (F, F, F, R)),
    GroupRow("C", "C", "Parametre", 22, 28, (F, F, F, N)),
    GroupRow("D", "D", "Planlama motoru", 29, 39, (F, F, F, N)),
    GroupRow("E", "E", "Senaryo ve çalışma", 40, 49, (F, F, F, N)),
    GroupRow("F", "F", "Manuel planlama", 50, 63, (F, F, O, N)),
    GroupRow("G", "G", "Malzeme ve öneriler", 64, 69, (F, F, F, R)),
    GroupRow("H", "H", "Analiz", 70, 75, (F, F, F, R)),
    GroupRow("I", "I", "Yayın", 76, 81, (F, F, F, N)),
    GroupRow("J", "J", "Takip ve rapor", 82, 87, (F, F, F, R)),
    GroupRow("K1", "K", "Kullanıcı, entegrasyon, işler, sağlık", 88, 95, (F, F, N, N)),
    GroupRow("K2", "K", "System owner ayarları, sürüm", 96, 97, (F, N, N, N)),
    GroupRow("K3", "K", "Denetim izi", 98, 98, (F, F, S, N)),
)

# Fonksiyon istisnaları: grup düzeyinden ayrılan hücreler (rol → düzey) ve gerekçesi.
EXCEPTIONS: dict[int, tuple[dict[str, Level], str]] = {
    48: ({END_USER: S}, "End user kendi işlerini görür: arka planda hazırlanan Excel'in bildirimi ve indirmesi (K-99)"),
    86: ({END_USER: F}, "Excel'e aktarma End user'ın hakkı (K-99)"),
    87: ({END_USER: S}, "End user yalnız kendi dışa aktarım kayıtlarını görür"),
    89: ({KEY_USER: F, END_USER: F}, "Giriş ve oturum herkese açık"),
    90: ({ADMIN: R}, "Admin matrisi görür, değiştiremez (Faz 1'de matris sabit)"),
}

# Fonksiyon adları docs/06'daki fonksiyon listesiyle birebir (test). Her satır: numara ve ad.
_NAMES = """
01 Veri çekme
02 Excel şablonu indirme
03 Excel ile yükleme
04 Doğrulama
05 Tam yükleme
06 Kısmi yükleme
07 Veri versiyonlama
08 Yükleme geçmişi
09 Ham veri temizliği
10 Ana veri görüntüleme
11 Değerin kaynağını gösterme
12 Elle değer girme
13 Elle değeri kaldırma
14 Değişiklik geçmişi
15 Excel ile toplu düzeltme (öneri)
16 Veri kuralı tanımlama
17 Kural önizleme
18 Kural sıralama ve aç / kapa
19 Kural uygulama
20 Veri kalitesi kontrolü
21 Kalite düzeltme aksiyonu
22 Parametre seti
23 Zaman yapısı
24 Kapasite parametreleri
25 Alokasyon ve öncelik kuralı
26 Uyarı eşikleri
27 Gece senaryo tanımı
28 Senaryo sırası ve aç / kapa
29 Ön hesap
30 MRP patlatma
31 Model kurma
32 Çözücü adaptörü
33 Kurallı yerleştirme ve sezgisel
34 Süre bütçesi
35 Son hesap
36 Mevcut arz önerileri
37 Uyarı üretme
38 Metrik hesaplama
39 Açıklama üretme
40 Gece akışı
41 Senaryoyu yeniden çalıştırma (öneri)
42 Senaryo karşılaştırma
43 Çalışma açma
44 Değişiklik izi
45 Değişikliği geri alma
46 Yeniden hesap
47 Eş zamanlı çalışma sınırı
48 İş bitti bildirimi
49 Çalışma kapatma
50 Ürün bazlı · üretim miktarı girme
51 Ürün bazlı · talebe eşitle
52 Kaynak bazlı · yük taşıma
53 Kaynak bazlı · alternatif kaynağa aktarma
54 Kaynak bazlı · fasona aktarma
55 Geçici kaynak parametresi
56 Sipariş bazlı · öncelik değiştirme
57 Sipariş bazlı · hedef tarih ve koruma
58 Manuel pegging
59 Gantt · sürükle-bırak
60 Gantt · bölme ve birleştirme
61 Kilitleme ve kilit kaldırma
62 Anlık etki önizlemesi
63 Dondurulmuş dönem koruması
64 Malzeme planı
65 Eksik filtresi
66 Planlı sipariş kararı
67 Toplu karar
68 Mevcut arz önerisi kararı
69 Önerileri dışa aktarma
70 Pegging
71 Gecikme nedeni
72 Termin sorgusu
73 Olay senaryosu
74 Ürün simülasyonu
75 Olayı çalışmaya uygulama
76 Yayın öncesi kontrol
77 Onaylı plan yayınlama
78 Varsayılan yap
79 Yayın notu
80 Plan karşılaştırma
81 Onaylı plan saklama
82 Sabah özeti
83 Uyarı iş listesi
84 Uyarıdan kayda gitme
85 Rapor görüntüleme
86 Excel'e aktarma
87 Dışa aktarım izi
88 Kullanıcı yönetimi
89 Giriş ve oturum
90 Rol bazlı yetki
91 Entegrasyon tanımı
92 Zamanlanmış işler
93 İş kuyruğu yönetimi (öneri)
94 Sistem sağlığı
95 Destek paketi
96 System owner ayarları
97 Sürüm güncelleme (öneri)
98 Denetim izi (öneri)
"""


def _parse_names() -> dict[int, str]:
    return {int(line[:2]): line[3:] for line in _NAMES.strip().splitlines()}


def _group_of(no: int) -> GroupRow:
    return next(g for g in GROUP_ROWS if g.first <= no <= g.last)


FUNCTIONS: dict[int, Function] = {no: Function(no, name, _group_of(no).letter) for no, name in _parse_names().items()}


def level(role: str, fn: int) -> Level:
    if role not in ROLES or fn not in FUNCTIONS:
        return Level.NONE
    override = EXCEPTIONS.get(fn, ({}, ""))[0].get(role)
    return override or _group_of(fn).levels[ROLES.index(role)]


def allows(role: str, fn: int, access: Access, own: bool = True) -> bool:
    """own: istek kullanıcının kendi nesnesi/kaydı üzerinde mi (sahibi ve kendi düzeyleri için)."""
    lv = level(role, fn)
    if lv == Level.FULL:
        return True
    if lv == Level.OWNER:
        return access == Access.READ or own
    if lv == Level.SELF:
        return own
    if lv == Level.READ:
        return access == Access.READ
    return False


def required_role(fn: int, access: Access) -> str:
    """O erişime (başkasının nesnesi dahil) izin veren en dar rol."""
    for role in reversed(ROLES):
        if allows(role, fn, access, own=False):
            return role
    return SYSTEM_OWNER


def forbidden_message(fn: int, access: Access) -> str:
    role = required_role(fn, access)
    whom = "Smartchain desteğine başvurun." if role == SYSTEM_OWNER else "Yetki için yöneticinize başvurun."
    return f"Bu işlem için {role} yetkisi gerekir. {whom}"


def role_permissions(role: str) -> dict[str, str]:
    """GET /api/auth/me: rolün her fonksiyondaki düzeyi (anahtar fonksiyon numarası)."""
    return {str(no): level(role, no).value for no in FUNCTIONS}


def matrix() -> dict:
    """Matrisin tamamı (2.4: ekran ve Excel; arayüz kopyası)."""
    return {
        "roles": list(ROLES),
        "groups": [{"key": g.key, "letter": g.letter, "name": g.name, "first": g.first, "last": g.last,
                    "levels": dict(zip(ROLES, (lv.value for lv in g.levels)))} for g in GROUP_ROWS],
        "functions": [{"no": f.no, "name": f.name, "group": f.group,
                       "levels": {r: level(r, f.no).value for r in ROLES}} for f in FUNCTIONS.values()],
        "exceptions": {str(no): reason for no, (_, reason) in EXCEPTIONS.items()},
    }


SHARED = Path(__file__).resolve().parents[1] / "shared" / "permissions.json"


def render() -> str:
    return json.dumps({"source": "app/api/permissions.py", **matrix()}, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    SHARED.write_text(render(), encoding="utf-8", newline="\n")
    print(f"{SHARED} yazıldı")
