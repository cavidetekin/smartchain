"""Veritabanı bağlantısı. Motor (engine) tektir, oturum (Session) her istek için açılır ve kapanır."""
import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .settings import get_settings

log = logging.getLogger("smartchain.db")


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    return create_engine(s.db_url, pool_pre_ping=True, connect_args={"timeout": s.db_connect_timeout})


def get_session() -> Iterator[Session | None]:
    """Motor kurulamazsa (ör. ODBC sürücüsü yok) None verir; uç nokta bunu anlamlı bir mesaja çevirir."""
    try:
        engine = get_engine()
    except Exception as exc:
        log.error("Veritabanı motoru kurulamadı: %s", exc)
        yield None
        return
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
