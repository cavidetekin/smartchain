"""Zincirin ilk adımı: veri kuralları (fonksiyon 19, K-134). 4.1'e kadar boş geçer; 4.1'de staging'in güncel hâline uygulanır."""
from sqlalchemy.orm import Session


def run(session: Session, entity: str) -> int:
    """Uygulanan kural sayısı. 3.4'te kural uygulanmaz."""
    return 0
