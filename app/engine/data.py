"""PlanningData'nın SQL uygulaması: core.* tablolarını veri versiyonuna göre salt okunur verir (K-58, K-63)."""
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata


class SqlPlanningData:
    def __init__(self, session: Session, data_version_id: int, scenario_definition_id: int | None = None):
        self.session = session
        self.data_version_id = data_version_id
        self.scenario_definition_id = scenario_definition_id

    def period_values(self, name: str, date_from: date, date_to: date) -> list[dict]:
        """Dönem değerleri (docs/09): ekranın önbelleğini kuran hesabın kendisi; girişler senaryoludur, güncel girişler ve üyelikler okunur."""
        if self.scenario_definition_id is None:
            raise ValueError("Dönem değerleri için senaryo gerekir.")
        from app import periods
        return periods.values(self.session, name, self.scenario_definition_id, date_from, date_to)

    def model_constraints(self) -> list[dict]:
        """Model kısıtları (docs/09, K-189): senaryoda geçerli değerler; yalnız kritik ve güncel kaynak grupları."""
        if self.scenario_definition_id is None:
            raise ValueError("Model kısıtları için senaryo gerekir.")
        from app import modelconstraints
        return modelconstraints.constraints(self.session, self.scenario_definition_id)

    def supplier_limits(self, date_from: date, date_to: date) -> list[dict]:
        """Tedarikçi limiti (docs/09, K-191): senaryonun gün bazında üst limitleri ve kapanışları."""
        if self.scenario_definition_id is None:
            raise ValueError("Tedarikçi limiti için senaryo gerekir.")
        from app import supplierlimits
        return supplierlimits.daily(self.session, self.scenario_definition_id, date_from, date_to)

    def warning_thresholds(self) -> list[dict]:
        """Uyarı eşikleri (docs/09, K-190): senaryonun aktif uyarıları."""
        if self.scenario_definition_id is None:
            raise ValueError("Uyarı eşikleri için senaryo gerekir.")
        from app.params import service as params
        return params.warning_thresholds(self.session, self.scenario_definition_id)

    def read(self, table: str, columns: Sequence[str] | None = None) -> list[dict]:
        name = table if "." in table else f"core.{table}"
        if not name.startswith("core."):
            raise ValueError(f"Motor yalnız core tablolarını okur: {table}")
        t = metadata.tables.get(name)
        if t is None:
            raise ValueError(f"Bilinmeyen tablo: {table}")
        if columns:
            unknown = [c for c in columns if c not in t.c]
            if unknown:
                raise ValueError(f"{name}: bilinmeyen alan {', '.join(unknown)}")
            q = sa.select(*(t.c[c] for c in columns))
        else:
            q = sa.select(t)
        if "VersionFrom" in t.c:
            v = self.data_version_id
            q = q.where(t.c.VersionFrom <= v, sa.or_(t.c.VersionTo.is_(None), t.c.VersionTo >= v))
        if "Id" in t.c:
            q = q.order_by(t.c.Id)
        return [dict(r) for r in self.session.execute(q).mappings()]
