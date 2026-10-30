"""0010 · Giriş ve oturum (K-97, K-98; fonksiyon 89)

adm.UserSession, adm.PasswordHistory, adm.LoginThrottle yeni. adm.AppUser: PasswordHash varbinary(256) → nvarchar(200)
(Argon2id PHC metni, boş olabilir), IsLocked yerine LockedUntil; PasswordChangeReason, PasswordChangedAt,
PasswordExpiresAt, LastLoginAt. Mevcut şifre özetleri yer tutucudur (0x00): boşaltılır, o hesaplar şifre verilene kadar
arayüzden giremez.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('LoginThrottle',
    sa.Column('UserName', sa.Unicode(length=60), autoincrement=False, nullable=False, comment='Yazılan kullanıcı adı'),
    sa.Column('FailedAttempts', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='Art arda hatalı giriş'),
    sa.Column('LockedUntil', mssql.DATETIME2(), nullable=True, comment='Kilit bitişi (UTC)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son deneme (UTC)'),
    sa.PrimaryKeyConstraint('UserName', name=op.f('PK_LoginThrottle')),
    schema='adm',
    comment='Bilinmeyen, şifresiz ya da pasif hesap adına yapılan hatalı girişlerin sayacı (K-98). Gerçek hesaptaki sayaçla aynı davranır; giriş cevabından hesabın var olup olmadığı anlaşılmaz.'
    )
    op.create_table('PasswordHistory',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('UserId', sa.Integer(), nullable=False, comment='Kullanıcı'),
    sa.Column('PasswordHash', sa.Unicode(length=200), nullable=False, comment='Şifre özeti'),
    sa.Column('CreatedAt', mssql.DATETIME2(), nullable=False, comment='Şifrenin belirlendiği zaman (UTC)'),
    sa.ForeignKeyConstraint(['UserId'], ['adm.AppUser.Id'], name=op.f('FK_PasswordHistory_UserId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_PasswordHistory')),
    schema='adm',
    comment='Kullanıcının önceki şifre özetleri (K-98): yeni şifre son `PasswordHistoryCount` şifreden farklı olmalı.'
    )
    op.create_table('UserSession',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Oturum kimliği'),
    sa.Column('TokenHash', mssql.VARBINARY(length=32), nullable=False, comment='Çerezdeki anahtarın SHA-256 özeti'),
    sa.Column('UserId', sa.Integer(), nullable=False, comment='Kullanıcı'),
    sa.Column('CreatedAt', mssql.DATETIME2(), nullable=False, comment='Açılış (UTC)'),
    sa.Column('LastActivityAt', mssql.DATETIME2(), nullable=False, comment='Son kullanıcı etkinliği (UTC); hareketsizlik buna göre ölçülür'),
    sa.Column('EndedAt', mssql.DATETIME2(), nullable=True, comment='Kapanış (UTC); boşsa açık'),
    sa.Column('EndReason', sa.Unicode(length=15), nullable=True, comment='Çıkış | Zaman aşımı | Şifre değişti | Kapatıldı'),
    sa.Column('ClientAddress', sa.Unicode(length=45), nullable=True, comment='İstemci adresi'),
    sa.Column('UserAgent', sa.Unicode(length=200), nullable=True, comment='Tarayıcı'),
    sa.ForeignKeyConstraint(['UserId'], ['adm.AppUser.Id'], name=op.f('FK_UserSession_UserId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_UserSession')),
    schema='adm',
    comment='Sunucu tarafı oturum (K-97). Tarayıcıdaki çerez rastgele bir anahtar taşır; tabloda yalnız anahtarın SHA-256 özeti durur.'
    )
    op.create_index('UX_UserSession_TokenHash', 'UserSession', ['TokenHash'], unique=True, schema='adm')
    op.add_column('AppUser', sa.Column('PasswordChangeReason', sa.Unicode(length=15), nullable=True, comment='İlk giriş | Sıfırlama | Süre doldu'), schema='adm')
    op.add_column('AppUser', sa.Column('PasswordChangedAt', mssql.DATETIME2(), nullable=True, comment='Şifrenin son değiştiği zaman (UTC)'), schema='adm')
    op.add_column('AppUser', sa.Column('PasswordExpiresAt', mssql.DATETIME2(), nullable=True, comment='Şifrenin süresinin dolduğu zaman (UTC); değişiklik anındaki politikayla hesaplanır'), schema='adm')
    op.add_column('AppUser', sa.Column('LockedUntil', mssql.DATETIME2(), nullable=True, comment='Kilit bitişi (UTC); geçmişse ya da boşsa kilit yok'), schema='adm')
    op.add_column('AppUser', sa.Column('LastLoginAt', mssql.DATETIME2(), nullable=True, comment='Son başarılı giriş (UTC)'), schema='adm')
    # Yer tutucu özetler (0x00) metne çevrilmez: önce boş olabilir yapılır ve boşaltılır, sonra tip değişir.
    op.alter_column('AppUser', 'PasswordHash', existing_type=mssql.VARBINARY(length=256), nullable=True, schema='adm')
    op.execute("UPDATE adm.AppUser SET PasswordHash = NULL")
    op.alter_column('AppUser', 'PasswordHash',
               existing_type=mssql.VARBINARY(length=256),
               type_=sa.Unicode(length=200),
               existing_nullable=True,
               comment='Özetlenmiş şifre; Argon2id PHC metni, tuz içinde (K-98); boşsa hesap arayüzden giremez',
               existing_comment='Özetlenmiş şifre',
               schema='adm')
    op.alter_column('AppUser', 'MustChangePassword',
               existing_type=mssql.BIT(),
               comment='Şifre değiştirilmeli; ilk giriş ya da sıfırlama sonrası',
               existing_comment='İlk girişte değiştir',
               existing_nullable=True,
               existing_server_default=sa.text('((1))'),
               schema='adm')
    op.alter_column('AppUser', 'FailedAttempts',
               existing_type=sa.INTEGER(),
               comment='Art arda hatalı giriş',
               existing_comment='Hatalı deneme',
               existing_nullable=True,
               existing_server_default=sa.text('((0))'),
               schema='adm')
    op.drop_column('AppUser', 'IsLocked', schema='adm', mssql_drop_default=True)


def downgrade():
    op.add_column('AppUser', sa.Column('IsLocked', mssql.BIT(), server_default=sa.text('((0))'), autoincrement=False, nullable=True, comment='Kilitli'), schema='adm')
    op.execute("UPDATE adm.AppUser SET IsLocked = 1 WHERE LockedUntil > SYSUTCDATETIME()")
    op.alter_column('AppUser', 'FailedAttempts',
               existing_type=sa.INTEGER(),
               comment='Hatalı deneme',
               existing_comment='Art arda hatalı giriş',
               existing_nullable=True,
               existing_server_default=sa.text('((0))'),
               schema='adm')
    op.alter_column('AppUser', 'MustChangePassword',
               existing_type=mssql.BIT(),
               comment='İlk girişte değiştir',
               existing_comment='Şifre değiştirilmeli; ilk giriş ya da sıfırlama sonrası',
               existing_nullable=True,
               existing_server_default=sa.text('((1))'),
               schema='adm')
    # SQL Server nvarchar → varbinary tip değişikliğine (kolon boş olsa da) izin vermez: kolon silinip eski tipte
    # yeniden açılır, eski yer tutucu (0x00) yazılır, zorunlu yapılır. Özetler zaten eski şemada kullanılamaz.
    op.drop_column('AppUser', 'PasswordHash', schema='adm')
    op.add_column('AppUser', sa.Column('PasswordHash', mssql.VARBINARY(length=256), nullable=True,
                                       comment='Özetlenmiş şifre'), schema='adm')
    op.execute("UPDATE adm.AppUser SET PasswordHash = 0x00")
    op.alter_column('AppUser', 'PasswordHash', existing_type=mssql.VARBINARY(length=256), nullable=False, schema='adm')
    op.drop_column('AppUser', 'LastLoginAt', schema='adm')
    op.drop_column('AppUser', 'LockedUntil', schema='adm')
    op.drop_column('AppUser', 'PasswordExpiresAt', schema='adm')
    op.drop_column('AppUser', 'PasswordChangedAt', schema='adm')
    op.drop_column('AppUser', 'PasswordChangeReason', schema='adm')
    op.drop_index('UX_UserSession_TokenHash', table_name='UserSession', schema='adm')
    op.drop_table('UserSession', schema='adm')
    op.drop_table('PasswordHistory', schema='adm')
    op.drop_table('LoginThrottle', schema='adm')
