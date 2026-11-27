"""Malzeme blokajı (ekran 31 üçüncü sekme, fonksiyon 99; K-193): malzeme için belli tarihlerde yeni tedarik planı çıkarılmaz.

Kayıt `param.MaterialHold`'dadır (lokasyon, malzeme, tür, başlangıç, bitiş, dönemi kapatma oranı, sebep); giriş ve Baz + fark ortak altyapıdandır
(`app/capacity/entries.py`, `app/params/resolve.py`). Burada türün tanımı, sahibin (lokasyon, malzeme) kuralları ve plan dönemine çevirme vardır;
liste, servis ve motor arayüzü buradan okur.

Kurallar:
- Blokaj yalnız yeni plan önerilerini durdurur; açık üretim siparişleri ve açık satın alma siparişleri etkilenmez. Satış blokajı yoktur.
- Tür: Üretim · Satın alma · Üretim ve satın alma. Tür malzemenin tedarik biçimine uyar: `Material.IsProducible` Hayır ise "Üretim" içeren,
  `IsPurchasable` Hayır ise "Satın alma" içeren tür reddedilir; alan boşsa (bilinmiyor) izin verilir.
- Blokajlar birleşir: bir gün, türü o tedarik biçimini kapsayan geçerli kayıtlardan herhangi biri kapsıyorsa o tedarik biçiminde blokajlıdır. Aynı
  malzeme ve başlangıçla iki kayıt serbesttir (senaryo çakışması anahtarı yok). Bitişi boş kayıt ufkun sonuna kadar sayılır.
- Plan dönemi (malzeme × tedarik biçimi × dönem): blokajlı gün ÷ dönemin takvim günü, dönemi kapatma oranına eşit ya da ondan büyükse dönem
  kapalıdır (`is_closed`). Döneme dokunan kayıtların oranları farklıysa en düşük oran geçerlidir (en sıkı kural).
"""
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.capacity.entries import Field, Kind, Owner
from app.params import resolve
from app.periods import cache, periods as period_list

TABLE = "MaterialHold"
SOURCE = "Model kısıtları"                     # adm.FieldChange.Source (ekranın adı)
PRODUCTION, PURCHASE, BOTH = "Üretim", "Satın alma", "Üretim ve satın alma"
TYPES = (PRODUCTION, PURCHASE, BOTH)
SUPPLIES = (PRODUCTION, PURCHASE)             # tedarik biçimleri (dönem hesabı ayrı ayrı)
OPEN, CLOSED = "Açık", "Kapalı"
NOT_PRODUCED, NOT_PURCHASED = "Bu malzeme üretilmiyor.", "Bu malzeme satın alınmıyor."


def covers(hold_type: str, supply: str) -> bool:
    """Kaydın türü bu tedarik biçimini kapsıyor mu."""
    return hold_type == supply or hold_type == BOTH


def is_closed(blocked_days: int, days: int, close_pct) -> bool:
    """Dönem kapalı mı: blokajlı gün ÷ dönemin takvim günü ≥ dönemi kapatma oranı (eşitlik kapalı; K-193 madde 5)."""
    return blocked_days * 100 >= Decimal(str(close_pct)) * days


# --- sahip: lokasyon, malzeme --------------------------------------------------------------------------------------------------------------

def _owner_check(session: Session, values: dict) -> list[dict]:
    """Seçimi doğrular ve kimlikleri sayıya çevirir: malzeme (lokasyonuyla) güncel veride olmalı."""
    for name in ("LocationId", "MaterialId"):
        value = values.get(name)
        if value is None or value == "":
            values[name] = None
            return [{"field": "MaterialId", "problem": "Malzeme seçilmeli."}]
        try:
            values[name] = int(value)
        except (TypeError, ValueError):
            return [{"field": "MaterialId", "problem": "Geçersiz seçim."}]
    found = session.execute(sa.text("SELECT TOP 1 1 FROM core.Material m WHERE m.Id = :m AND m.LocationId = :l AND m.VersionTo IS NULL"),
                            {"m": values["MaterialId"], "l": values["LocationId"]}).first()
    return [] if found else [{"field": "MaterialId", "problem": "Güncel veride yok."}]


def _owner_label(session: Session, row: dict) -> str:
    """Kaydın okunur adı: malzemenin kodu (güncel kayıt yoksa son versiyonun kodu)."""
    code = session.execute(sa.text("SELECT TOP 1 Code FROM core.Material WHERE Id = :i ORDER BY VersionFrom DESC"), {"i": row.get("MaterialId")}).scalar()
    return str(code or row.get("MaterialId"))


MATERIAL = Owner(("LocationId", "MaterialId"), _owner_check, _owner_label, lambda row: None,      # aynı başlangıç denetlenmez: blokajlar birleşir
                 locked="Lokasyon ve malzeme kayıttan sonra değişmez; kaydı silip yeniden girin.",
                 locked_fields=("LocationCode", "MaterialCode", "MaterialName"))


def _rules(row: dict) -> list[tuple[str, str]]:
    pct = row.get("ClosePct")
    return [("ClosePct", "0'dan büyük, en çok 100 olmalı.")] if pct is not None and not (0 < pct <= 100) else []


def _type_fits(session: Session, row: dict) -> list[tuple[str, str]]:
    """Tür malzemenin tedarik biçimine uyar (K-193 madde 3): yalnız açıkça "Hayır" olan reddedilir; alan boşsa ya da malzeme güncel değilse denetlenmez."""
    hold_type = row.get("HoldType")
    if hold_type not in TYPES or row.get("MaterialId") is None:
        return []
    found = session.execute(sa.text("SELECT TOP 1 m.IsProducible, m.IsPurchasable FROM core.Material m WHERE m.Id = :m AND m.VersionTo IS NULL"),
                            {"m": row["MaterialId"]}).first()
    if found is None:
        return []
    if covers(hold_type, PRODUCTION) and found.IsProducible is not None and not found.IsProducible:
        return [("HoldType", NOT_PRODUCED)]
    if covers(hold_type, PURCHASE) and found.IsPurchasable is not None and not found.IsPurchasable:
        return [("HoldType", NOT_PURCHASED)]
    return []


HOLD_KIND = Kind("material-holds", TABLE, "Malzeme blokajı",
                 (Field("HoldType", "Tür", "choice", choices=TYPES), Field("StartDate", "Başlangıç", "date"), Field("EndDate", "Bitiş", "date", required=False),
                  Field("ClosePct", "Dönemi kapatma oranı (%)", "number", decimals=2), Field("Reason", "Sebep", "text", required=False, max_length=255)),
                 MATERIAL, start="StartDate", end="EndDate", source=SOURCE, rules=_rules, checks=_type_fits)


# --- seçenekler ----------------------------------------------------------------------------------------------------------------------------

def options(session: Session) -> list[dict]:
    """Pencerenin seçenekleri: güncel malzemeler, lokasyonu ve tedarik biçimiyle (`producible` ve `purchasable` boş olabilir: bilinmiyor)."""
    found = session.execute(sa.text(
        "SELECT m.LocationId, l.Code AS Location, m.Id, m.Code, m.Name, m.IsProducible, m.IsPurchasable FROM core.Material m "
        "JOIN core.Location l ON l.Id = m.LocationId WHERE m.VersionTo IS NULL ORDER BY l.Code, m.Code")).mappings()
    return [{"location_id": r["LocationId"], "location": r["Location"], "material_id": r["Id"], "code": r["Code"], "name": r["Name"],
             "producible": None if r["IsProducible"] is None else bool(r["IsProducible"]),
             "purchasable": None if r["IsPurchasable"] is None else bool(r["IsPurchasable"])} for r in found]


# --- plan dönemine çevirme -----------------------------------------------------------------------------------------------------------------

def periods_sql(sid: str = ":sid", base: str = ":base", periods: str = ":periods", days: str = ":days") -> str:
    """Malzeme × tedarik biçimi × plan dönemi; yalnız blokajlı günü olan dönemler. Parametreler: senaryo, okuduğu Baz, dönemler ve ufkun günleri
    (`app.periods.periods` `to_json`, `days_json`). SELECT: LocationId, MaterialId, Supply, PeriodNo, dönem alanları (PeriodType, Period, PeriodStart,
    PeriodEnd, Week, Month, Quarter, Year, PeriodDays), BlockedDays (birleşmiş: aynı gün bir kez), ClosePct (döneme dokunan kayıtların en düşüğü), Ratio
    (blokajlı gün ÷ takvim günü, yüzde), Closed, SourceRowId (döneme dokunan ilk kayıt), Records (döneme dokunan kayıt sayısı)."""
    supplies = ", ".join(f"(N'{s}')" for s in SUPPLIES)
    touched = (f"SELECT r.LocationId, r.MaterialId, s.Supply, d.[no], COUNT(DISTINCT d.[d]) AS BlockedDays, MIN(r.ClosePct) AS ClosePct, MIN(r.RowId) AS SourceRowId, "
               f"COUNT(DISTINCT r.RowId) AS Records FROM ({resolve.sql(TABLE, sid=sid, base=base)}) r CROSS JOIN (VALUES {supplies}) s(Supply) "
               f"JOIN OPENJSON({days}) WITH ({period_list.DAY_JSON_SCHEMA}) d ON d.[d] >= r.StartDate AND (r.EndDate IS NULL OR d.[d] <= r.EndDate) "
               f"WHERE r.HoldType = s.Supply OR r.HoldType = N'{BOTH}' GROUP BY r.LocationId, r.MaterialId, s.Supply, d.[no]")
    return ("SELECT x.LocationId, x.MaterialId, x.Supply, p.[no] AS PeriodNo, p.[type] AS PeriodType, p.[label] AS Period, p.[start] AS PeriodStart, p.[end] AS PeriodEnd, "
            "p.[week] AS Week, p.[month] AS Month, p.[quarter] AS Quarter, p.[year] AS Year, p.[days] AS PeriodDays, x.BlockedDays, x.ClosePct, "
            "CAST(x.BlockedDays * 100.0 / p.[days] AS decimal(6,2)) AS Ratio, CAST(CASE WHEN x.BlockedDays * 100.0 >= x.ClosePct * p.[days] THEN 1 ELSE 0 END AS bit) AS Closed, "
            f"x.SourceRowId, x.Records FROM ({touched}) x JOIN OPENJSON({periods}) WITH ({period_list.PERIOD_JSON_SCHEMA}) p ON p.[no] = x.[no]")


def period_binds(session: Session, scenario_id: int, today: date, prefix: str = "") -> dict:
    """`periods_sql`'in parametreleri: senaryo, okuduğu Baz ve senaryonun plan dönemleri."""
    found = period_list.read(session, scenario_id, today)
    scenario = cache.scenario_row(session, scenario_id)
    return {f"{prefix}sid": scenario_id, f"{prefix}base": cache.base_of(session, scenario), f"{prefix}periods": period_list.to_json(found),
            f"{prefix}days": period_list.days_json(found)}


def periods(session: Session, scenario_id: int, today: date) -> list[dict]:
    """Motor arayüzü (docs/09): senaryonun plan dönemlerinde {LocationId, MaterialId, Supply, PeriodNo, PeriodStart, PeriodEnd, Days, BlockedDays,
    ClosePct, Closed}; yalnız blokajlı günü olan dönemler. Ekrandaki Geçerlilik tablosuyla aynı hesap."""
    # Dönem ve gün listeleri uzun metindir: alt sorgu olarak ve tipli (nvarchar(max)) bağlanır. Düz metin sorguda tip sürücüye geçmez, uzun metin
    # ntext gider ve OPENJSON kabul etmez.
    binds = period_binds(session, scenario_id, today)
    names = ("LocationId", "MaterialId", "Supply", "PeriodNo", "PeriodStart", "PeriodEnd", "PeriodDays", "BlockedDays", "ClosePct", "Closed")
    source = sa.text(periods_sql()).bindparams(
        sa.bindparam("sid", binds["sid"], sa.Integer()), sa.bindparam("base", binds["base"], sa.Integer()),
        sa.bindparam("periods", binds["periods"], sa.UnicodeText()), sa.bindparam("days", binds["days"], sa.UnicodeText())).columns(*[sa.column(n) for n in names]).subquery("z")
    rows = session.execute(sa.select(*[source.c[n] for n in names]).order_by(source.c.LocationId, source.c.MaterialId, source.c.Supply, source.c.PeriodNo)).mappings()
    return [{"LocationId": r["LocationId"], "MaterialId": r["MaterialId"], "Supply": r["Supply"], "PeriodNo": r["PeriodNo"], "PeriodStart": r["PeriodStart"],
             "PeriodEnd": r["PeriodEnd"], "Days": r["PeriodDays"], "BlockedDays": r["BlockedDays"], "ClosePct": r["ClosePct"], "Closed": bool(r["Closed"])} for r in rows]
