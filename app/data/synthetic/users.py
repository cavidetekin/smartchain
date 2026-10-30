"""Sentetik kullanıcılar ve geçici şifreleri (docs/11 "Kullanıcılar", K-98).

Her çalıştırmada her hesaba rastgele bir geçici şifre verilir ve hesap "İlk giriş" ile şifre değiştirmeye zorlanır.
Şifreler kodda ve repoda yer almaz: konsola bir kez yazılır ve git dışı .local/gecici-sifreler.txt'ye kaydedilir.
"""
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api import security
from app.api.repositories import auth as repo
from app.api.services import auth

USERS = [
    ("sahip", "Sistem Sahibi", "Sistem sahibi"),
    ("yonetici", "Ayşe Yönetici", "Admin"),
    ("planlama", "Mert Planlama", "Key user"),
    ("izleme", "Deniz İzleme", "End user"),
]

NOTE = ("# Smartchain sentetik kullanıcıların geçici şifreleri (python -m app.data.synthetic users).\n"
        "# Yalnız geliştirme ve demo içindir; repoya ve kurulum paketine girmez. İlk girişte şifre değiştirilir.\n")


def reset_users(engine: Engine) -> list[tuple[str, str, str]]:
    """Hesapları açar ya da geçici şifreye döndürür; (kullanıcı adı, rol, geçici şifre) listesi."""
    out = []
    with Session(engine) as session:
        for user_name, full_name, role in USERS:
            row = repo.find_user(session, user_name)
            if row is None:
                user_id = session.execute(sa.insert(repo.USER).values(
                    UserName=user_name, FullName=full_name, Role=role, IsActive=True).returning(repo.USER.c.Id)).scalar_one()
            else:
                user_id = row["Id"]
                repo.update_user(session, user_id, FullName=full_name, Role=role, IsActive=True)
            password = security.temporary_password()
            auth.set_temporary_password(session, user_id, password)
            repo.end_user_sessions(session, user_id, auth.END_CLOSED)
            out.append((user_name, role, password))
        session.commit()
    return out


def write_file(path: Path, users: list[tuple[str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [NOTE, f"# {datetime.now():%d.%m.%Y %H:%M}\n"]
    lines += [f"{name:<10} {role:<14} {password}\n" for name, role, password in users]
    path.write_text("".join(lines), encoding="utf-8")
