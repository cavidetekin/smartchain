"""adm.SystemSetting yazma. Okuma: app.jobs.settings.read_int_settings. Commit çağırana bırakılır."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

SETTING = metadata.tables["adm.SystemSetting"]


def set_setting(session: Session, key: str, value: str) -> None:
    if session.execute(sa.update(SETTING).where(SETTING.c.SettingKey == key).values(Value=value)).rowcount == 0:
        session.execute(sa.insert(SETTING).values(SettingKey=key, Value=value))
