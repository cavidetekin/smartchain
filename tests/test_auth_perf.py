"""Giriş performansı (K-98): Argon2id doğrulaması dahil giriş ortancası 300 ms altında (ayrıca: pytest -m perf)."""
import statistics
import time

import pytest

from test_auth_api import NAME, PASSWORD, client, engine, login, user  # noqa: F401  (fikstürler)

pytestmark = [pytest.mark.db, pytest.mark.perf]

TARGET_MS = 300
RUNS = 7


def test_login_under_target(engine, user):  # noqa: F811
    times = []
    for _ in range(RUNS):
        c = client()
        start = time.perf_counter()
        assert login(c, NAME, PASSWORD).status_code == 200
        times.append((time.perf_counter() - start) * 1000)
    ms = statistics.median(times)
    print(f"\ngiriş (Argon2id + oturum + iz): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS
