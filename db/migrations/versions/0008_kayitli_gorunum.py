"""0008 · Kayıtlı görünüm (K-89)

adm.TableView (kayıtlı tablo görünümü: kolonlar, genişlik, sabitleme, sıralama, filtre, gruplama; kişisel ya da
paylaşılan) ve adm.TableViewDefault (kullanıcının liste başına varsayılan görünümü). Yalnız yeni tablolar; veri yok.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('TableView',
    sa.Column('Id', sa.Integer(), autoincrement=True, nullable=False, comment='Görünüm kimliği'),
    sa.Column('ListName', sa.Unicode(length=60), nullable=False, comment='Liste adı (ör. materials)'),
    sa.Column('OwnerUserId', sa.Integer(), nullable=False, comment='Sahibi'),
    sa.Column('Name', sa.Unicode(length=100), nullable=False, comment='Görünüm adı'),
    sa.Column('IsShared', sa.Boolean(), server_default=sa.text('0'), nullable=False, comment='Paylaşılan'),
    sa.Column('Definition', sa.NVARCHAR(), nullable=False, comment='Görünüm içeriği; JSON, sürümlü (docs/08)'),
    sa.Column('CreatedAt', mssql.DATETIME2(), nullable=False, comment='Oluşturulma zamanı'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['OwnerUserId'], ['adm.AppUser.Id'], name=op.f('FK_TableView_OwnerUserId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_TableView')),
    schema='adm',
    comment='Kayıtlı tablo görünümü (K-89): kolon seti ve sırası, genişlikler, sabitleme, sıralama, filtreler, gruplama.'
    )
    op.create_index('UX_TableView_ListName_OwnerUserId_Name', 'TableView', ['ListName', 'OwnerUserId', 'Name'], unique=True, schema='adm')
    op.create_table('TableViewDefault',
    sa.Column('UserId', sa.Integer(), autoincrement=False, nullable=False, comment='Kullanıcı'),
    sa.Column('ListName', sa.Unicode(length=60), autoincrement=False, nullable=False, comment='Liste adı'),
    sa.Column('ViewId', sa.Integer(), nullable=False, comment='Varsayılan görünüm'),
    sa.ForeignKeyConstraint(['UserId'], ['adm.AppUser.Id'], name=op.f('FK_TableViewDefault_UserId')),
    sa.ForeignKeyConstraint(['ViewId'], ['adm.TableView.Id'], name=op.f('FK_TableViewDefault_ViewId')),
    sa.PrimaryKeyConstraint('UserId', 'ListName', name=op.f('PK_TableViewDefault')),
    schema='adm',
    comment='Kullanıcının bir liste için varsayılan görünümü (K-89). Satır yoksa liste tanımındaki "Standart" görünüm açılır.'
    )


def downgrade():
    op.drop_table('TableViewDefault', schema='adm')
    op.drop_index('UX_TableView_ListName_OwnerUserId_Name', table_name='TableView', schema='adm')
    op.drop_table('TableView', schema='adm')
