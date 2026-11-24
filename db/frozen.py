"""Geçişlerin sabit açıklamaları (K-197; db/README.md): bir geçiş, tablo ve kolon açıklamalarını güncel modelden (`db/models.py`) okumaz;
yazıldığı andaki değerleri kendi içinde sabit taşır. Model sonradan değişse de (kolon kalkar, açıklama değişir) eski geçiş aynı işi yapar:
sıfırdan kurulum ile adım adım yükseltilmiş veritabanı ayrışmaz.

`frozen(COMMENTS)` sabit sözlüğü modelin okunduğu biçimde sunar: `FROZEN.tables["param.X"].comment`, `.c.Kolon.comment`, `.c["Kolon"].comment`,
`.columns` (adı ve açıklamasıyla), `FROZEN.tables.get(...)`. Sözlük: tablo → {kolon: açıklama}; boş anahtar tablonun açıklamasıdır.
"""


class _Column:
    def __init__(self, name: str, comment: str | None):
        self.name, self.comment = name, comment


class _Columns:
    def __init__(self, table: str, comments: dict):
        self._table, self._items = table, {name: _Column(name, text) for name, text in comments.items() if name}

    def __getitem__(self, name: str) -> _Column:
        try:
            return self._items[name]
        except KeyError:
            raise KeyError(f"{self._table}.{name}: açıklaması geçişe sabit yazılmamış") from None

    def __getattr__(self, name: str) -> _Column:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def __iter__(self):
        return iter(self._items.values())


class _Table:
    def __init__(self, key: str, comments: dict):
        self.comment = comments.get("")
        self.c = _Columns(key, comments)

    @property
    def columns(self):
        return list(self.c)


class _Frozen:
    def __init__(self, comments: dict):
        self.tables = {key: _Table(key, cols) for key, cols in comments.items()}


def frozen(comments: dict) -> _Frozen:
    return _Frozen(comments)
