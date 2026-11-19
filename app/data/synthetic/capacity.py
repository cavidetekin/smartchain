"""Kapasite hesabının saf Python karşılığı (K-185): sentetik veri setinin Baz girişlerinden kaynak grubu × kaynak × gün.

Üretim kodu değildir: veritabanındaki hesabın (`app/capacity/compute.py`) bağımsız doğrulaması ve sentetik durum denetimleri içindir.
Kural aynıdır: önce seviye (kaynakta o günü kapsayan kayıt varsa kaynağınki, yoksa grubunki), sonra başlangıcı en ileri olan; duruşlar
birleşir ve gün bir kez düşer.
"""
from datetime import date, timedelta

from .dataset import Dataset

DAYS = ("DayMon", "DayTue", "DayWed", "DayThu", "DayFri", "DaySat", "DaySun")


def _covers(row: dict, day: date, start: str = "ValidFrom", end: str = "ValidTo") -> bool:
    return row[start] <= day and (row.get(end) is None or row[end] >= day)


def effective(rows: list[dict], group_id: int, resource_id: int, day: date) -> dict | None:
    """Geçerlilik kuralı (K-185 C): o gün için geçerli kayıt; yoksa None."""
    valid = [r for r in rows if r.get("IsValid", True) and _covers(r, day)]
    own = [r for r in valid if r.get("ResourceId") == resource_id]
    chosen = own or [r for r in valid if r.get("ResourceGroupId") == group_id]
    return max(chosen, key=lambda r: r["ValidFrom"]) if chosen else None


def daily(ds: Dataset, start: date, end: date) -> dict[tuple[int, int, date], dict]:
    """(kaynak grubu, kaynak, gün) → çalışma günü, duruş, günlük kapasite, toplam ve kullanılabilir kapasite, ek mesai limiti."""
    p = ds.params
    out: dict[tuple[int, int, date], dict] = {}
    absences = ds.rows("EmployeeAbsence")
    for m in ds.rows("ResourceGroupMember"):
        g, r = m["ResourceGroupId"], m["ResourceId"]
        day = start
        while day <= end:
            wp = effective(p.get("WorkPattern", []), g, r, day)
            ef = effective(p.get("ResourceEfficiency", []), g, r, day)
            ol = effective(p.get("OvertimeLimit", []), g, r, day)
            working = float(wp[DAYS[day.weekday()]]) if wp else 0.0
            capacity = float(wp["DailyCapacity"]) if wp else 0.0
            eff = float(ef["EfficiencyPct"]) / 100 if ef else 1.0
            losses = [1.0 - float(f["DayValue"]) for f in p.get("FactoryCalendar", []) if f.get("IsValid", True) and _covers(f, day, "StartDate", "EndDate")]
            losses += [1.0 for x in p.get("ResourceDowntime", []) if x.get("IsValid", True) and _covers(x, day, "StartDate", "EndDate")
                       and (x.get("ResourceId") == r or x.get("ResourceGroupId") == g)]
            for a in absences:
                if a["ResourceId"] == r and a["StartDate"] <= day <= a["EndDate"]:
                    hours = a.get("HoursPerDay")
                    losses.append(1.0 if hours is None or capacity <= 0 else min(1.0, float(hours) / capacity))
            downtime = min(working, max(losses, default=0.0))
            workable = working - downtime
            out[(g, r, day)] = {"WorkingDay": working, "Downtime": downtime, "DailyCapacity": capacity, "Capacity": working * capacity * eff,
                                "AvailableCapacity": workable * capacity * eff, "OvertimeLimit": workable * (float(ol["DailyLimit"]) if ol else 0.0)}
            day += timedelta(days=1)
    return out


def group_total(ds: Dataset, group_id: int, start: date, end: date, field: str = "Capacity") -> float:
    return sum(v[field] for (g, _r, _d), v in daily(ds, start, end).items() if g == group_id)


def undefined(ds: Dataset, day: date) -> set[int]:
    """Kapasitesi tanımsız kaynaklar (K-185 H): o gün ne kendisinde ne gruplarından birinde geçerli çalışma düzeni olanlar."""
    rows = ds.params.get("WorkPattern", [])
    groups: dict[int, set[int]] = {}
    for m in ds.rows("ResourceGroupMember"):
        groups.setdefault(m["ResourceId"], set()).add(m["ResourceGroupId"])
    return {r["Id"] for r in ds.rows("Resource")
            if not any(effective(rows, g, r["Id"], day) for g in groups.get(r["Id"], {0}))}
