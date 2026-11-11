"""Geliştirme veritabanı koruması (K-165, CLAUDE.md): adı `_test` ile bitmeyen veritabanında yıkıcı komut (alembic downgrade, sentetik reset,
unload ve load) yalnız etkileşimli terminalde, veritabanının adı yazılınca çalışır. Girdi terminal değilse (komut zinciri, yönlendirilmiş girdi, betik)
hiçbir şey değiştirmeden durur; ortam değişkeniyle atlanamaz. Test veritabanı (`_test`) serbesttir.
"""
import os
import sys
from collections.abc import Callable
from typing import TextIO


class Refused(SystemExit):
    """Onay yok: komut hiçbir şey değiştirmeden durur (çıkış kodu 2)."""

    def __init__(self, message: str):
        super().__init__(2)
        self.message = message

    def __str__(self) -> str:
        return self.message


def is_test_database(name: str | None) -> bool:
    return bool(name) and name.lower().endswith("_test")


def interactive(stream: TextIO | None) -> bool:
    """Gerçek terminal mi. Windows'ta boş aygıt (NUL, ör. `< NUL`, subprocess.DEVNULL) isatty() için terminal sayılır; konsol olduğu
    GetConsoleMode ile doğrulanır. Dosya tanıtıcısı olmayan akışta (testteki sahte akış) isatty() geçerlidir."""
    if stream is None or not stream.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        fileno = stream.fileno()
    except (AttributeError, OSError, ValueError):
        return True
    import ctypes
    import msvcrt
    mode = ctypes.c_uint()
    return bool(ctypes.windll.kernel32.GetConsoleMode(msvcrt.get_osfhandle(fileno), ctypes.byref(mode)))


def require_terminal(database: str | None, action: str, stdin: TextIO | None = None) -> None:
    """Bağlanmadan önceki denetim: test veritabanı değilse ve terminal yoksa Refused."""
    if not is_test_database(database) and not interactive(stdin or sys.stdin):
        raise Refused(f"DURDU: {action} geliştirme veritabanında ({database or '(adsız)'}) açık onay ister; yalnız etkileşimli terminalde, veritabanının adı "
                      "yazılınca çalışır. Komut zincirinde ve yönlendirilmiş girdiyle çalışmaz; hiçbir şey değişmedi.")


def confirm(database: str | None, action: str, status: str | None = None, *, stdin: TextIO | None = None,
            ask: Callable[[str], str] = input, out: TextIO | None = None) -> None:
    """Onay alınamazsa Refused fırlatır. status: mevcut durum (ör. geçiş numarası), onaydan önce gösterilir."""
    if is_test_database(database):
        return
    require_terminal(database, action, stdin)
    out = out or sys.stdout
    name = database or "(adsız)"
    print(f"{action} · veritabanı: {name}", file=out)
    if status:
        print(f"  Mevcut durum: {status}", file=out)
    answer = ask(f"Onaylamak için veritabanının adını yazın ({name}): ").strip()
    if answer != database:
        raise Refused("Ad tutmadı; hiçbir şey değişmedi.")
