"""Özel alokasyon (K-198): arz satırının seviyesi, anahtarı ve satır bayrağı.

Tek kural: anahtarlı arz yalnız sahibine gider, anahtarsız arz herkese açıktır. Bu modül arzın (stok, üretim siparişi, satın alma satırı) anahtarını
hesaplar; kuralın motordaki ve pegging'deki uygulanışı kendi adımlarındadır (7.15, 7.17, Aşama 10).

Hesap (aktarım, sentetik yükleme ve yeniden hesap aynı ifadeleri kullanır):
- Malzemenin güncel kaydında `IsCustomAllocated` Evet değilse (Hayır ya da boş) satır geneldir: bayrak Hayır, seviye ve anahtar boş; satırda
  sahip bilgisi dolu olsa da.
- Evetse satırda ERP'nin yazdığı en detaylı sahip anahtardır: sipariş satırı → kalemsiz sipariş → proje → müşteri.
  - Sipariş satırı (sipariş no ve satır no dolu): seviye Sipariş, anahtar "sipariş no|satır no|alt satır no"; alt satır yoksa 0.
  - Kalemsiz sipariş (sipariş no dolu, satır no boş): seviye Sipariş, anahtar yalnız sipariş no.
  - Proje: proje kodu. Müşteri: müşteri kodu.
- Lokasyon anahtara girmez. Hiç sahip yazmıyorsa satır geneldir.
- Hesap satırın kendi ham alanlarına (`SalesOrderNo`…, `ProjectCode`, `CustomerCode`: ERP'den geldiği gibi) ve malzemeye bakar; sahibin sistemde
  bulunmasına bakmaz. Sahibi bulunamayan ya da kapanmış ayrılmış arz genele düşmez, bir alt seviyeye de düşmez: anahtarıyla boşta bekler.

Alanlar `core`'dadır, sözleşmede (stg, prc) yoktur: veri kuralı yazamaz, kullanıcı değiştiremez (kaynak "Yüklemede diğer tablolardan").
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

TABLES = ("Stock", "WorkOrder", "PurchaseOrderLine")
FLAG, LEVEL, KEY = "IsCustomAllocated", "AllocationLevel", "AllocationKey"
FIELDS = (FLAG, LEVEL, KEY)
ORDER, PROJECT, CUSTOMER = "Sipariş", "Proje", "Müşteri"
LEVELS = (ORDER, PROJECT, CUSTOMER)
SEP = "|"
KEY_LENGTH = 60
BIN = "Latin1_General_100_BIN2"


def _core(name: str) -> sa.Table:
    return metadata.tables[f"core.{name}"]


def _number(col) -> sa.ColumnElement:
    return sa.cast(col, sa.Unicode(12))


def expressions(row) -> dict[str, sa.ColumnElement]:
    """Satırın bayrağı, seviyesi ve anahtarı. `row`: MaterialId, SalesOrderNo, SalesOrderLineNo, SalesOrderLineItemNo, ProjectCode ve
    CustomerCode kolonlarını taşıyan tablo (ana tablo ya da aktarımın geçici tablosu); yalnız malzemenin güncel kaydına bakılır."""
    mat = _core("Material").alias("al_mat")
    allocated = sa.exists().where(mat.c.Id == row.c.MaterialId, mat.c.VersionTo.is_(None), mat.c.IsCustomAllocated == sa.true())
    order, project, customer = row.c.SalesOrderNo, row.c.ProjectCode, row.c.CustomerCode
    line_key = sa.func.concat(order, SEP, _number(row.c.SalesOrderLineNo), SEP, _number(sa.func.coalesce(row.c.SalesOrderLineItemNo, 0)))
    steps = ((sa.and_(order.is_not(None), row.c.SalesOrderLineNo.is_not(None)), ORDER, line_key), (order.is_not(None), ORDER, order),
             (project.is_not(None), PROJECT, project), (customer.is_not(None), CUSTOMER, customer))
    level = sa.case((~allocated, sa.null()), *[(cond, sa.literal(name, sa.Unicode(10))) for cond, name, _ in steps], else_=sa.null())
    key = sa.case((~allocated, sa.null()), *[(cond, sa.func.left(value, KEY_LENGTH)) for cond, _, value in steps], else_=sa.null())
    flag = sa.case((sa.and_(allocated, sa.or_(*[cond for cond, _, _ in steps])), sa.true()), else_=sa.false())
    return {FLAG: flag, LEVEL: level, KEY: key}


def fill(session: Session, table) -> None:
    """Tablonun bütün satırlarına yazar (aktarımın geçici tablosu: değişiklik karşılaştırmasından önce)."""
    session.execute(sa.update(table).values(expressions(table)))


def _differs(a, b, text: bool) -> sa.ColumnElement:
    if text:
        a, b = a.collate(BIN), b.collate(BIN)
    return sa.or_(sa.and_(a.is_(None), b.is_not(None)), sa.and_(a.is_not(None), b.is_(None)), sa.and_(a.is_not(None), b.is_not(None), a != b))


def _stale(t: sa.Table, ex: dict) -> sa.ColumnElement:
    return sa.or_(*[_differs(t.c[f], ex[f], f != FLAG) for f in FIELDS])


def update_in_place(session: Session) -> dict[str, int]:
    """Güncel satırları yerinde günceller (versiyon açmaz): sentetik yükleme ana tablolara doğrudan yazar, aktarım değildir."""
    out = {}
    for name in TABLES:
        t = _core(name)
        ex = expressions(t)
        out[name] = session.execute(sa.update(t).where(t.c.VersionTo.is_(None), _stale(t, ex)).values(ex)).rowcount
    return out


def refresh(session: Session, run) -> dict[str, int]:
    """Aktarım koşusunun sonunda (tam ve kısmi): bütün arz tablolarının güncel satırları yeniden hesaplanır. Bu koşuda yazılan satır zaten
    günceldir; aktarılmayan tablonun (eşiği aşan, veri gelmeyen) ya da aktarılmayan satırın değeri malzemenin alanı değiştiği için eskimiş olabilir. Değeri değişen satır koşunun veri versiyonuyla yeni versiyon açar ve Geçmiş'e yazılır."""
    from app import history
    from app.manual import as_text

    out = {}
    for name in TABLES:
        t = _core(name)
        ex = expressions(t)
        tmp = sa.Table(f"#alloc_{name}", sa.MetaData(), sa.Column("Id", sa.BigInteger, primary_key=True), sa.Column(FLAG, sa.Boolean),
                       sa.Column(LEVEL, sa.Unicode(10, collation="DATABASE_DEFAULT")), sa.Column(KEY, sa.Unicode(KEY_LENGTH, collation="DATABASE_DEFAULT")))
        tmp.create(bind=session.connection())
        try:
            sel = sa.select(t.c.Id, *[ex[f] for f in FIELDS]).where(t.c.VersionTo.is_(None), _stale(t, ex))
            out[name] = session.execute(sa.insert(tmp).from_select(["Id", *FIELDS], sel)).rowcount
            if not out[name]:
                continue
            cur = sa.and_(t.c.Id == tmp.c.Id, t.c.VersionTo.is_(None))
            for f in FIELDS:  # geçmiş: alan alan, eski ve yeni değer
                hist = (sa.select(*history._base(name, run, tmp.c.Id, history.CHANGED), sa.literal(f, sa.Unicode(60)), as_text(t.c[f], t.c[f]),
                                  as_text(tmp.c[f], t.c[f])).select_from(tmp.join(t, cur)).where(_differs(t.c[f], tmp.c[f], f != FLAG)))
                session.execute(sa.insert(history.FIELD_CHANGE).from_select([*history.BASE_COLS, "FieldName", "OldValue", "NewValue"], hist))
            ids = sa.select(tmp.c.Id)
            # bu koşuda yazılmış satır (beklenmez): yerinde
            session.execute(sa.update(t).where(t.c.VersionTo.is_(None), t.c.VersionFrom == run.version, t.c.Id.in_(ids))
                            .values({f: sa.select(tmp.c[f]).where(tmp.c.Id == t.c.Id).scalar_subquery() for f in FIELDS}))
            # önceki versiyon kapanır, aynı Id ile yeni versiyon açılır (öteki kolonlar aynen)
            session.execute(sa.update(t).where(t.c.VersionTo.is_(None), t.c.VersionFrom < run.version, t.c.Id.in_(ids))
                            .values(VersionTo=run.version - 1, UpdatedAt=run.now))
            prev, live = t.alias("prev"), t.alias("live")
            cols = {c.name: prev.c[c.name] for c in t.columns}
            cols.update({f: tmp.c[f] for f in FIELDS})
            cols.update(VersionFrom=sa.literal(run.version), VersionTo=sa.null(), UpdatedAt=sa.literal(run.now))
            new = (sa.select(*[v.label(k) for k, v in cols.items()]).select_from(prev.join(tmp, tmp.c.Id == prev.c.Id))
                   .where(prev.c.VersionTo == run.version - 1, ~sa.exists().where(live.c.Id == prev.c.Id, live.c.VersionTo.is_(None))))
            session.execute(sa.insert(t).from_select(list(cols), new))
        finally:
            tmp.drop(bind=session.connection())
    return out
