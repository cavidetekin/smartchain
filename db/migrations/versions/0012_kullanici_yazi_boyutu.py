"""0012 · Kullanıcının yazı boyutu (U-23; AppUser.FontSize, geliştirme 2.3)

Boş: henüz seçilmedi (standart 13 geçerli); tarayıcıdaki eski değer bir kez buraya taşınır.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-03
"""
from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('AppUser', sa.Column('FontSize', sa.Integer(), nullable=True, comment='Yazı boyutu tercihi, px: 12, 13, 14 ya da 16 (U-23); boşsa seçilmedi, standart 13 geçerli'), schema='adm')


def downgrade():
    op.drop_column('AppUser', 'FontSize', schema='adm')
