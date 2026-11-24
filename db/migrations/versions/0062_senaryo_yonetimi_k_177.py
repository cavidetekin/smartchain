"""0062 · Senaryo yönetimi (K-177): Baz'ı izler, kullanıcının seçili senaryosu, denetim izinde senaryo adı

- `param.ScenarioDefinition.FollowsBase` ("Baz'ı izler"; Baz'da boş). Var olan Baz dışı senaryolar Baz'dan bağımsız kurulmuştu: Hayır yazılır.
- `adm.AppUser.ScenarioDefinitionId`: kullanıcının son seçtiği senaryo (bağ yok; okurken doğrulanır).
- `adm.AuditLog.ScenarioName`: senaryoya bağlı işlemde senaryonun adı. Var olan parametre kayıtları (nesne "Senaryo", kayıt "<ad> · …") doldurulur;
  denetim izinin değişmezliği (K-109) uygulama hesabı içindir, doldurma bu geçişle bir kez yapılır.
- 0058'in pasife çevirdiği eski sentetik setin kalıntısı ("Sentetik v0") silinir (K-165, açık onay 17.11.2026): yalnız sentetik, Baz olmayan, adı
  "Sentetik v0" olan ve plan hesabı bulunmayan kayıt ve ona bağlı satırlar. Geri alışta geri gelmez.
- Açıklamalar modelden (docs/02); veri sözlüğü eşitlenir.

Revision ID: 0062
Revises: 0061
Create Date: 2026-11-17
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata
from frozen import frozen

# Bu geçişin okuduğu tablo ve kolon açıklamaları sabittir: geçişin yazıldığı andaki modelden (commit da46820); güncel modelden okunmaz
# (K-197). Boş anahtar tablonun açıklamasıdır.
COMMENTS = {
    'adm.AppUser': {
        '': "Uygulama kullanıcısı (Faz 1'de yerel).",
        'Id': 'Kullanıcı kimliği',
        'UserName': 'Kullanıcı adı',
        'FullName': 'Ad soyad',
        'Role': 'System owner | Admin | Key user | End user',
        'PasswordHash': 'Özetlenmiş şifre; Argon2id PHC metni, tuz içinde (K-98); boşsa hesap arayüzden giremez',
        'MustChangePassword': 'Şifre değiştirilmeli; ilk giriş ya da sıfırlama sonrası',
        'PasswordChangeReason': 'İlk giriş | Sıfırlama | Süre doldu',
        'PasswordChangedAt': 'Şifrenin son değiştiği zaman (UTC)',
        'PasswordExpiresAt': 'Şifrenin süresinin dolduğu zaman (UTC); değişiklik anındaki politikayla hesaplanır',
        'FailedAttempts': 'Art arda hatalı giriş',
        'LockedUntil': 'Kilit bitişi (UTC); geçmişse ya da boşsa kilit yok',
        'LastLoginAt': 'Son başarılı giriş (UTC)',
        'IsActive': 'Aktif',
        'FontSize': 'Yazı boyutu tercihi, px: 12, 13, 14 ya da 16 (U-23); boşsa seçilmedi, standart 13 geçerli',
        'ScenarioDefinitionId': 'Kullanıcının son seçtiği senaryo (K-177); boşsa, senaryo pasifse ya da silinmişse Baz açılır',
    },
    'adm.AuditLog': {
        '': 'Kim, ne zaman, neyi değiştirdi; giriş kayıtları; kayıtlar silinemez (K-109).',
        'Id': 'Kayıt kimliği',
        'UserId': 'Kullanıcı',
        'At': 'Zaman',
        'Action': 'İşlem',
        'ObjectType': 'Nesne',
        'ObjectKey': 'Kayıt',
        'OldValue': 'Önceki',
        'NewValue': 'Yeni',
        'ScenarioName': 'Senaryoya bağlı işlemde senaryonun adı (K-177); veri yönetimi işlemlerinde boş. Ad olarak saklanır: senaryo silinse de iz okunur',
    },
    'param.ScenarioDefinition': {
        '': 'Senaryo tanımı (K-175): parametrelerinin tamamını kendisi taşır (PlanningSetting, TimeBucketDefinition, ObjectiveDefinition ve senaryoya bağlı öteki tablolar); senaryolar arasında paylaşılan set yoktur. Kurulumda tek senaryo "Baz" gelir; silinemez, pasif yapılamaz.',
        'Id': 'Tanım kimliği',
        'LocationId': 'Lokasyon; Baz kurulumda veri gelmeden açıldığı için boş olabilir',
        'Name': 'Senaryo adı',
        'IsBase': 'Baz senaryo: silinemez, pasif yapılamaz; tek kayıtta Evet',
        'IsActive': 'Aktif; pasif senaryo bağlam çubuğundaki listede görünmez ve gece çalışmaz, parametreleri durur (K-177)',
        'FollowsBase': "Baz'ı izler: veri tablolarında Baz'ın değerlerini okur, yalnız farkını tutar (K-176); Baz'da boş; Hayır'a dönen senaryo yeniden bağlanmaz",
        'RunsNightly': 'Gece çalışsın: kapalı senaryo yeniden açılana kadar gece akışında hesaplanmaz (K-177)',
        'NightlyPriority': "Gece sırası: gece çalışan senaryolar arasında 1'den boşluksuz; gece çalışmayanda boş",
        'IsSynthetic': 'Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79)',
    },
    'planning.Scenario': {
        '': 'Senaryo sonucu: bir senaryonun bir veri versiyonuyla hesaplanmış planı. Bir sonraki gece silinmez, saklanır; saklama süresi sistem ayarıdır (K-177; ekranda "plan versiyonu").',
        'Id': 'Kayıt kimliği',
        'ScenarioDefinitionId': 'Tanım',
        'DataVersionId': 'Veri versiyonu',
        'PlanRunId': 'Üreten plan çalışması',
        'CreatedAt': 'Oluşma',
        'Status': 'Bitti | Kısmen | Hata',
    },
}
FROZEN = frozen(COMMENTS)

revision = '0062'
down_revision = '0061'
branch_labels = None
depends_on = None

SD = 'param.ScenarioDefinition'
LEFTOVER = (f"SELECT d.Id FROM {SD} d WHERE d.IsSynthetic = 1 AND ISNULL(d.IsBase, 0) = 0 AND d.Name = N'Sentetik v0' "
            "AND NOT EXISTS (SELECT 1 FROM planning.PlanRun r WHERE r.ScenarioDefinitionId = d.Id) "
            "AND NOT EXISTS (SELECT 1 FROM planning.Scenario s WHERE s.ScenarioDefinitionId = d.Id)")
CHILDREN = ('PlanningSetting', 'TimeBucketDefinition', 'ObjectiveDefinition', 'PriorityRule', 'AllocationRule', 'ResourceEfficiency', 'ResourcePeriodLimit',
            'OvertimeLimit', 'SupplierLimit')
OLD = {('param', 'ScenarioDefinition', 'IsActive'): 'Aktif; pasif senaryo seçilemez ve çalışmaz (senaryo yönetimi adımı)',
       ('param', 'ScenarioDefinition', 'RunsNightly'): 'Gece çalışsın (senaryo yönetimi adımı)',
       ('param', 'ScenarioDefinition', 'NightlyPriority'): 'Gece çalışma sırası',
       ('planning', 'Scenario', None): 'Gece üretilen senaryo; bir sonraki gece akışında silinir.'}


def _comment(schema, table, column, text):
    """MS SQL'de var olan açıklama güncellenir."""
    level2 = f", 'column', '{column}'" if column else ""
    escaped = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{escaped}', 'schema', '{schema}', 'table', '{table}'{level2}")


def upgrade():
    def new(schema, table, column):
        t = FROZEN.tables[f"{schema}.{table}"]
        return t.c[column].comment if column else t.comment

    op.add_column('AppUser', sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=True, comment=new('adm', 'AppUser', 'ScenarioDefinitionId')), schema='adm')
    op.add_column('AuditLog', sa.Column('ScenarioName', sa.Unicode(length=100), nullable=True, comment=new('adm', 'AuditLog', 'ScenarioName')), schema='adm')
    op.add_column('ScenarioDefinition', sa.Column('FollowsBase', sa.Boolean(), nullable=True, comment=new('param', 'ScenarioDefinition', 'FollowsBase')),
                  schema='param')
    for key in OLD:
        _comment(*key, new(*key))
    # eski sentetik setin kalıntısı
    for child in CHILDREN:
        op.execute(f"DELETE FROM param.[{child}] WHERE ScenarioDefinitionId IN ({LEFTOVER})")
    op.execute(f"DELETE FROM {SD} WHERE Id IN ({LEFTOVER})")
    # var olan Baz dışı senaryolar Baz'ı izlemez
    op.execute(f"UPDATE {SD} SET FollowsBase = 0 WHERE ISNULL(IsBase, 0) = 0")
    # denetim izinde senaryo adı: kayıt "<ad> · <parametre>" biçiminde yazılmıştı
    op.execute("UPDATE adm.AuditLog SET ScenarioName = LEFT(ObjectKey, CHARINDEX(N' · ', ObjectKey) - 1) "
               "WHERE ObjectType = N'Senaryo' AND ScenarioName IS NULL AND CHARINDEX(N' · ', ObjectKey) > 1")
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)


def downgrade():
    for key, text in OLD.items():
        _comment(*key, text)
    op.execute("DELETE FROM adm.FieldDefinition WHERE (TableName = N'ScenarioDefinition' AND FieldName = N'FollowsBase')")
    op.drop_column('ScenarioDefinition', 'FollowsBase', schema='param')
    op.drop_column('AuditLog', 'ScenarioName', schema='adm')
    op.drop_column('AppUser', 'ScenarioDefinitionId', schema='adm')
