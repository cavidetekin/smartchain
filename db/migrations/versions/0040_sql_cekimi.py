"""0040 · SQL çekimi (K-130): adm.IntegrationEntity, adm.IntegrationViewVersion; ImportBatch.SourceObject ve SignalId; Job.Result

Var olan partiler ve işler değişmez. IntegrationEntity satırı yoksa tablo Excel sayılır, bugünkü kurulumlar aynı çalışır.
Geri alışta tablo ayarları, view sürümleri ve iş sonuçları kaybolur.

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('IntegrationViewVersion',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('EntityName', sa.Unicode(length=60), nullable=False, comment='Tablo'),
    sa.Column('ViewName', sa.Unicode(length=128), nullable=False, comment='View'),
    sa.Column('VersionNo', sa.Integer(), nullable=False, comment='Sürüm numarası'),
    sa.Column('DefinitionHash', sa.Unicode(length=64), nullable=False, comment='Tanımın özeti'),
    sa.Column('Definition', sa.NVARCHAR(), nullable=True, comment="View tanımı; şifrelenmiş view'da boş"),
    sa.Column('SeenAt', mssql.DATETIME2(), nullable=False, comment='İlk görüldüğü zaman'),
    sa.Column('AppVersion', sa.Unicode(length=20), nullable=False, comment='Smartchain sürümü'),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_IntegrationViewVersion')),
    schema='adm',
    comment="View'ın sürüm geçmişi (K-130): tanım değişince yeni sürüm. Smartchain view oluşturmaz, yalnız okur ve saklar."
    )
    op.create_index(op.f('IX_IntegrationViewVersion_EntityName'), 'IntegrationViewVersion', ['EntityName'], unique=False, schema='adm')
    op.create_table('IntegrationEntity',
    sa.Column('EntityName', sa.Unicode(length=60), autoincrement=False, nullable=False, comment='Tablo (`stg` adı)'),
    sa.Column('Method', sa.Unicode(length=10), nullable=True, comment='Excel | SQL'),
    sa.Column('IsPullEnabled', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Çekim açık; kapalıysa SQL çekimi bu tabloyu atlar, Excel yükleme etkilenmez'),
    sa.Column('DisabledReason', sa.Unicode(length=400), nullable=True, comment='Çekimin kapatılma sebebi'),
    sa.Column('DisabledBy', sa.Integer(), nullable=True, comment='Çekimi kapatan'),
    sa.Column('DisabledAt', mssql.DATETIME2(), nullable=True, comment='Çekimin kapatıldığı zaman'),
    sa.Column('ViewName', sa.Unicode(length=128), nullable=True, comment='Entegrasyon veritabanındaki view'),
    sa.Column('LastCheckAt', mssql.DATETIME2(), nullable=True, comment='Son uyum denetimi'),
    sa.Column('LastCheckStatus', sa.Unicode(length=20), nullable=True, comment='Uyumlu | Uyarılı | Hatalı'),
    sa.Column('LastCheckMessage', sa.Unicode(length=400), nullable=True, comment='Son denetimin özeti'),
    sa.Column('MatchedColumns', sa.Integer(), nullable=True, comment='Uyan sözleşme kolonu'),
    sa.Column('ExpectedColumns', sa.Integer(), nullable=True, comment='Sözleşme kolonu'),
    sa.Column('LastContractHash', sa.Unicode(length=32), nullable=True, comment='Son denetimdeki sözleşme özeti; değiştiyse yeniden denetlenir'),
    sa.Column('LastPullAt', mssql.DATETIME2(), nullable=True, comment='Son okuma'),
    sa.Column('LastPullStatus', sa.Unicode(length=20), nullable=True, comment='Son çekim durumu'),
    sa.Column('LastPullMessage', sa.Unicode(length=400), nullable=True, comment='Son çekim durumunun nedeni'),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment='Son değiştiren'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=True, comment='Son değişiklik'),
    sa.ForeignKeyConstraint(['DisabledBy'], ['adm.AppUser.Id'], name=op.f('FK_IntegrationEntity_DisabledBy')),
    sa.ForeignKeyConstraint(['UpdatedBy'], ['adm.AppUser.Id'], name=op.f('FK_IntegrationEntity_UpdatedBy')),
    sa.PrimaryKeyConstraint('EntityName', name=op.f('PK_IntegrationEntity')),
    schema='adm',
    comment='Tablo başına çekim ayarı (K-130). Satır yoksa ya da yöntem boşsa tablo Excel sayılır, çekim açıktır.'
    )
    op.add_column('ImportBatch', sa.Column('SourceObject', sa.Unicode(length=128), nullable=True, comment='SQL partisinde okunan view'), schema='adm')
    op.add_column('ImportBatch', sa.Column('SignalId', sa.BigInteger(), nullable=True, comment='SQL partisinde okunan `ERP_LoadLog` satırı'), schema='adm')
    op.alter_column('ImportBatch', 'UploadedBy',
               existing_type=sa.INTEGER(),
               comment='Yükleyen kullanıcı; Excel yüklemesinde ve elle çekimde dolu',
               existing_comment='Yükleyen kullanıcı; Excel yüklemesinde dolu',
               existing_nullable=True,
               schema='adm')
    op.alter_column('ImportBatch', 'JobId',
               existing_type=sa.BIGINT(),
               comment='Büyük dosyada ön kontrol işi; SQL partisinde çekim işi',
               existing_comment='Büyük dosyada ön kontrol işi',
               existing_nullable=True,
               schema='adm')
    op.add_column('Job', sa.Column('Result', sa.NVARCHAR(), nullable=True, comment='İşin sonucu (JSON); Veri çekme: tablo başına durum'), schema='adm')
    op.alter_column('Job', 'JobType',
               existing_type=sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım | Excel ön kontrol | Veri çekme …',
               existing_comment='Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım | Excel ön kontrol …',
               existing_nullable=False,
               schema='adm')
    op.alter_column('Job', 'Channel',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece | Hesaplama | Excel | Veri çekme',
               existing_comment='Gece | Hesaplama | Excel',
               existing_nullable=False,
               schema='adm')


def downgrade():
    op.alter_column('Job', 'Channel',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece | Hesaplama | Excel',
               existing_comment='Gece | Hesaplama | Excel | Veri çekme',
               existing_nullable=False,
               schema='adm')
    op.alter_column('Job', 'JobType',
               existing_type=sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım | Excel ön kontrol …',
               existing_comment='Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım | Excel ön kontrol | Veri çekme …',
               existing_nullable=False,
               schema='adm')
    op.drop_column('Job', 'Result', schema='adm')
    op.alter_column('ImportBatch', 'JobId',
               existing_type=sa.BIGINT(),
               comment='Büyük dosyada ön kontrol işi',
               existing_comment='Büyük dosyada ön kontrol işi; SQL partisinde çekim işi',
               existing_nullable=True,
               schema='adm')
    op.alter_column('ImportBatch', 'UploadedBy',
               existing_type=sa.INTEGER(),
               comment='Yükleyen kullanıcı; Excel yüklemesinde dolu',
               existing_comment='Yükleyen kullanıcı; Excel yüklemesinde ve elle çekimde dolu',
               existing_nullable=True,
               schema='adm')
    op.drop_column('ImportBatch', 'SignalId', schema='adm')
    op.drop_column('ImportBatch', 'SourceObject', schema='adm')
    op.drop_table('IntegrationEntity', schema='adm')
    op.drop_index(op.f('IX_IntegrationViewVersion_EntityName'), table_name='IntegrationViewVersion', schema='adm')
    op.drop_table('IntegrationViewVersion', schema='adm')
