"""Testlerde oturum (K-97): kullanıcı başına oturum çerezi, şifre sormadan açılır (services.auth.open_session).

    api.get("/api/materials/views", headers=auth(user_id))

Kullanıcı silinmeden önce oturumları, şifre geçmişi ve denetim izi satırları silinir (delete_users).
"""
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.api.db import get_engine
from app.api.deps import COOKIE
from app.api.services.auth import open_session

_tokens: dict[int, str] = {}


def token(user_id: int, fresh: bool = False) -> str:
    """Kullanıcının paylaşılan test oturumu; fresh=True yeni ve paylaşılmayan bir oturum açar (kapatılacaksa)."""
    if fresh:
        with Session(get_engine()) as s:
            return open_session(s, user_id, agent="pytest")
    if user_id not in _tokens:
        _tokens[user_id] = token(user_id, fresh=True)
    return _tokens[user_id]


def auth(user_id: int, fresh: bool = False) -> dict:
    """İstek başlığı: bu kullanıcının oturum çerezi (istemcinin çerezini ezer)."""
    return {"Cookie": f"{COOKIE}={token(user_id, fresh)}"}


def ensure_user(conn, user_name: str, role: str = "Key user", full_name: str | None = None) -> int:
    """Şifresiz deneme kullanıcısı (arayüzden giremez; oturum testte doğrudan açılır)."""
    conn.execute(text("IF NOT EXISTS (SELECT 1 FROM adm.AppUser WHERE UserName = :n) "
                      "INSERT INTO adm.AppUser (UserName, FullName, Role, MustChangePassword) VALUES (:n, :f, :r, 0)"),
                 {"n": user_name, "f": full_name, "r": role})
    return conn.execute(text("SELECT Id FROM adm.AppUser WHERE UserName = :n"), {"n": user_name}).scalar_one()


def delete_users(conn, ids: list[int]) -> None:
    """Kullanıcıları ve onlara bağlı oturum, şifre geçmişi, iz ve görünüm satırlarını siler."""
    if not ids:
        return
    p = {"ids": list(ids)}
    for sql in ("DELETE FROM adm.UserSession WHERE UserId IN :ids",
                "DELETE FROM adm.PasswordHistory WHERE UserId IN :ids",
                "DELETE FROM adm.AuditLog WHERE UserId IN :ids",
                "DELETE FROM adm.TableViewDefault WHERE UserId IN :ids",
                "DELETE d FROM adm.TableViewDefault d JOIN adm.TableView v ON v.Id = d.ViewId WHERE v.OwnerUserId IN :ids",
                "DELETE FROM adm.TableView WHERE OwnerUserId IN :ids",
                "DELETE FROM adm.Job WHERE RequestedBy IN :ids",
                "DELETE FROM adm.AppUser WHERE Id IN :ids"):
        conn.execute(text(sql).bindparams(bindparam("ids", expanding=True)), p)
    for i in ids:
        _tokens.pop(i, None)
