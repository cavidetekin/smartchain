"""Çözümleme katmanı (K-176, K-185): "Baz + fark" tutulan veri tablolarında bir senaryonun geçerli satırları tek yerden çözülür.

Baz'ın satırları temel veridir. Baz'ı izleyen senaryo yalnız farkını tutar:
- fark satırı: `BaseRowId` Baz satırını gösterir; `OverriddenFields`'ta adı geçen alanlar senaryodan, gerisi Baz satırından okunur
  (",ValidTo,DailyCapacity," biçiminde, virgüllerle çevrili). `IsValid` de alan gibidir: "Geçersiz yap" fark satırında `IsValid = 0` yazar.
- senaryonun kendi satırı: `BaseRowId` boş.
Baz'da ve Baz'ı izlemeyen senaryoda yalnız kendi satırları vardır (izlemeyen senaryo ayrılırken Baz'ın o anki değerlerini tam kopyalar).

Senaryo çakışması (K-191 madde 10; A-47): elle müdahale edilen yerde senaryo, edilmeyen yerde Baz geçerlidir. Başlangıcı tekil olan tablolarda
(`KEYS`) izleyen senaryonun kendi satırı, aynı anahtarlı (aynı sahip ve aynı başlangıç) Baz satırının önüne geçer: Baz satırı çözümde görünmez,
senaryonun satırı "Senaryo farkı" olarak gelir (`ShadowId` örtülen Baz satırı; `BaseValues` onun değerleri, `OverriddenFields` farklı alanlar).
Durum, önce senaryoda sonra Baz'da kayıt girilince doğar; veride dönüştürme yapılmaz, kural okurken uygulanır. Senaryonun satırı silinince
("Senaryo farkını kaldır") Baz satırı yeniden görünür. Kural bu modülde tek yerdedir: kapasite girişleri, tedarikçi limiti ve sıradaki tablolar
anahtarını `KEYS`'e yazarak kullanır.

Okuyan her yer (hesap, geçerlilik, ekran listeleri, veri kalitesi) `sql()` ile aynı çözümü kullanır.
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

OWNER = ("ResourceGroupId", "ResourceId")
VALIDITY = ("ValidFrom", "ValidTo")
DAYS = ("DayMon", "DayTue", "DayWed", "DayThu", "DayFri", "DaySat", "DaySun")
# Tablo → çözümlenen alanlar (ortak alanlar dışında)
FIELDS: dict[str, tuple[str, ...]] = {
    "WorkPattern": (*OWNER, *VALIDITY, "DailyCapacity", *DAYS),
    "ResourceEfficiency": (*OWNER, *VALIDITY, "EfficiencyPct"),
    "OvertimeLimit": (*OWNER, *VALIDITY, "DailyLimit"),
    "ResourceDowntime": (*OWNER, "StartDate", "EndDate", "DowntimeType", "Reason"),
    "FactoryCalendar": ("StartDate", "EndDate", "Name", "DayValue"),
}
# Kapasite hesabına giren tablolar (önbelleğin "senaryonun kendi girişi var mı" sorusu yalnız bunlara bakar)
CAPACITY_TABLES = tuple(FIELDS)
# Model kısıtları (K-189): kaynak grubu başına tarihsiz iki değer; kapasite hesabına girmez
FIELDS["ResourceGroupConstraint"] = ("ResourceGroupId", "UnconstrainedCapacityFactor", "TargetUtilizationPct")
# Tedarikçi limiti (K-191): iki kayıt türü tek tabloda; kapasite hesabına girmez
FIELDS["SupplierLimit"] = ("LimitType", "LocationId", "SupplierId", "MaterialId", "ValidFrom", "ValidTo", "UpperLimit", "LimitPeriod", "Reason")
# Malzeme blokajı (K-193): blokajlar birleşir (çakışma anahtarı yok); kapasite hesabına girmez
FIELDS["MaterialHold"] = ("LocationId", "MaterialId", "HoldType", "StartDate", "EndDate", "ClosePct", "Reason")
BASE, DIFF, OWN = "Baz", "Senaryo farkı", "Senaryo"
# Senaryo çakışmasının anahtarı (aynı sahip ve aynı başlangıç): yalnız başlangıcı tekil olan tablolar. Birleşen kayıtlarda (duruş, kapanış, fabrika
# takvimi, malzeme blokajı) çakışma yoktur. İkinci öğe: anahtarın geçerli olduğu satırlar ({a}: tablo takma adı); boşsa bütün satırlar.
KEYS: dict[str, tuple[tuple[str, ...], str]] = {
    "WorkPattern": ((*OWNER, "ValidFrom"), ""),
    "ResourceEfficiency": ((*OWNER, "ValidFrom"), ""),
    "OvertimeLimit": ((*OWNER, "ValidFrom"), ""),
    "SupplierLimit": (("LocationId", "SupplierId", "MaterialId", "ValidFrom"), "{a}.LimitType = N'Üst limit'"),
}


def _same_key(table: str, a: str, b: str) -> str | None:
    """İki satırın çakışma anahtarı aynı mı (boş değerler eşit sayılır); tabloda anahtar yoksa None."""
    if table not in KEYS:
        return None
    keys, where = KEYS[table]
    parts = [f"({a}.[{k}] = {b}.[{k}] OR ({a}.[{k}] IS NULL AND {b}.[{k}] IS NULL))" for k in keys]
    if where:
        parts += [where.format(a=a), where.format(a=b)]
    return " AND ".join(parts)


def _differs(field: str, a: str, b: str) -> str:
    return f"CASE WHEN {a}.[{field}] = {b}.[{field}] OR ({a}.[{field}] IS NULL AND {b}.[{field}] IS NULL) THEN N'' ELSE N'{field},' END"


def _picked(field: str) -> str:
    """Fark satırı alanı değiştirdiyse senaryonun, değilse Baz'ın değeri."""
    return f"CASE WHEN d.Id IS NOT NULL AND d.OverriddenFields LIKE N'%,{field},%' THEN d.[{field}] ELSE b.[{field}] END AS [{field}]"


def sql(table: str, valid_only: bool = True, sid: str = ":sid", base: str = ":base", detail: bool = False) -> str:
    """Senaryonun geçerli satırları (SELECT metni). Parametreler: senaryo ve okuduğu Baz (Baz'da ve izlemeyen senaryoda NULL).
    Kolonlar: RowId (Baz satırında Baz'ın, kendi satırında kendi kimliği), StoredId (senaryoda saklanan satır; farkı olmayan Baz satırında
    boş), Origin (Baz · Senaryo farkı · Senaryo), ShadowId (senaryonun kendi satırı aynı anahtarlı bir Baz satırını örtüyorsa o satır; K-191),
    IsValid ve tablonun alanları. valid_only: geçersiz yapılmış satırlar gelmez."""
    fields = FIELDS[table]
    t = f"param.[{table}]"
    same = _same_key(table, "o", "b")
    # detail (giriş ekranları, 7.9b): farkın değiştirdiği alanlar ve Baz'daki değerler (JSON; yalnız farkı olan satırda)
    more_inherited = (f", d.OverriddenFields, CASE WHEN d.Id IS NULL THEN NULL ELSE (SELECT b.IsValid, {', '.join(f'b.[{f}]' for f in fields)} "
                      "FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES) END AS BaseValues") if detail else ""
    more_own = ", CAST(NULL AS varchar(400)) AS OverriddenFields, CAST(NULL AS nvarchar(max)) AS BaseValues" if detail else ""
    hidden = f" AND NOT EXISTS (SELECT 1 FROM {t} o WHERE o.ScenarioDefinitionId = {sid} AND o.BaseRowId IS NULL AND {same})" if same else ""
    inherited = (f"SELECT b.Id AS RowId, d.Id AS StoredId, CASE WHEN d.Id IS NULL THEN N'{BASE}' ELSE N'{DIFF}' END AS Origin, CAST(NULL AS bigint) AS ShadowId, "
                 f"{_picked('IsValid')}, {', '.join(_picked(f) for f in fields)}{more_inherited} FROM {t} b LEFT JOIN {t} d ON d.ScenarioDefinitionId = {sid} "
                 f"AND d.BaseRowId = b.Id WHERE b.ScenarioDefinitionId = {base} AND b.BaseRowId IS NULL{hidden}")
    if same:
        # senaryonun kendi satırı aynı anahtarlı Baz satırını örter: "Senaryo farkı" olarak gelir (Baz'da ve izlemeyen senaryoda {base} boştur: eşleşmez)
        if detail:
            more_own = (f", CASE WHEN b.Id IS NULL THEN NULL ELSE N',' + {' + '.join(_differs(f, 'o', 'b') for f in ('IsValid', *fields))} END AS OverriddenFields, "
                        f"CASE WHEN b.Id IS NULL THEN NULL ELSE (SELECT b.IsValid, {', '.join(f'b.[{f}]' for f in fields)} "
                        "FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES) END AS BaseValues")
        own = (f"SELECT o.Id AS RowId, o.Id AS StoredId, CASE WHEN b.Id IS NULL THEN N'{OWN}' ELSE N'{DIFF}' END AS Origin, b.Id AS ShadowId, o.IsValid, "
               f"{', '.join(f'o.[{f}]' for f in fields)}{more_own} FROM {t} o "
               f"OUTER APPLY (SELECT TOP 1 b.* FROM {t} b WHERE b.ScenarioDefinitionId = {base} AND b.BaseRowId IS NULL AND {same} ORDER BY b.Id DESC) b "
               f"WHERE o.ScenarioDefinitionId = {sid} AND o.BaseRowId IS NULL")
    else:
        own = (f"SELECT o.Id AS RowId, o.Id AS StoredId, N'{OWN}' AS Origin, CAST(NULL AS bigint) AS ShadowId, o.IsValid, "
               f"{', '.join(f'o.[{f}]' for f in fields)}{more_own} FROM {t} o WHERE o.ScenarioDefinitionId = {sid} AND o.BaseRowId IS NULL")
    union = f"{inherited} UNION ALL {own}"
    return f"SELECT z.* FROM ({union}) z WHERE z.IsValid = 1" if valid_only else union


def has_own(session: Session, scenario_id: int, tables: tuple[str, ...] = CAPACITY_TABLES) -> bool:
    """Senaryonun bu tablolarda saklanan satırı var mı (fark ya da kendi satırı). Yoksa izleyen senaryonun sonucu Baz'ınkiyle aynıdır."""
    for table in tables:
        if session.execute(sa.text(f"SELECT TOP 1 1 FROM param.[{table}] WHERE ScenarioDefinitionId = :s"), {"s": scenario_id}).first():
            return True
    return False


def materializer(table: str):
    """Baz'dan ayırma (K-176): Baz'ın o anki geçerli değerleri (senaryonun farklarıyla) senaryoya tam kopyalanır; fark satırları silinir.
    Geçersiz yapılmış Baz satırı da kopyalanır (`IsValid = 0` ile): ayrıldıktan sonra da senaryoda geçersiz kalır."""
    fields = FIELDS[table]
    names = ", ".join(f"[{f}]" for f in fields)

    def run(session: Session, scenario_id: int) -> None:
        base = session.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar()
        if base is None or base == scenario_id:
            return
        t = f"param.[{table}]"
        same = _same_key(table, "o", "b")     # senaryonun kendi satırının örttüğü Baz satırı kopyalanmaz (K-191)
        hidden = f" AND NOT EXISTS (SELECT 1 FROM {t} o WHERE o.ScenarioDefinitionId = :sid AND o.BaseRowId IS NULL AND {same})" if same else ""
        inherited = (f"SELECT {_picked('IsValid')}, {', '.join(_picked(f) for f in fields)} FROM {t} b LEFT JOIN {t} d "
                     f"ON d.ScenarioDefinitionId = :sid AND d.BaseRowId = b.Id WHERE b.ScenarioDefinitionId = :base AND b.BaseRowId IS NULL{hidden}")
        session.execute(sa.text(f"INSERT INTO {t} (ScenarioDefinitionId, IsValid, {names}, UpdatedAt) "
                                f"SELECT :sid, x.IsValid, {', '.join(f'x.[{f}]' for f in fields)}, SYSUTCDATETIME() FROM ({inherited}) x"),
                        {"sid": scenario_id, "base": base})
        session.execute(sa.text(f"DELETE FROM {t} WHERE ScenarioDefinitionId = :sid AND BaseRowId IS NOT NULL"), {"sid": scenario_id})
    return run
