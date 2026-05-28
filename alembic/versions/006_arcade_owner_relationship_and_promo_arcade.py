"""arcade owner relationship and promo arcade scope

Revision ID: 006
Revises: 005
Create Date: 2026-05-06

Migration:
- Adds `owner_admin_id` (nullable FK to admins.id) on `arcades` — canonical owner relationship.
- Backfills `arcades.owner_admin_id` from existing `admins.arcade_id` rows (where role = arcade_owner).
- Drops `admins.arcade_id` (replaced by reverse FK).
- Adds `arcade_id` (nullable FK to arcades.id) on `promo_codes` — arcade_owner promos are scoped to their arcade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'arcades',
        sa.Column('owner_admin_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_arcades_owner_admin_id',
        'arcades', 'admins',
        ['owner_admin_id'], ['id'],
        ondelete='SET NULL',
    )

    op.execute(
        """
        UPDATE arcades a
        SET owner_admin_id = ad.id
        FROM admins ad
        WHERE ad.arcade_id = a.id
          AND ad.role = 'arcade_owner'
          AND ad.is_deleted = false
        """
    )

    op.drop_constraint('admins_arcade_id_fkey', 'admins', type_='foreignkey')
    op.drop_column('admins', 'arcade_id')

    op.add_column(
        'promo_codes',
        sa.Column('arcade_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_promo_codes_arcade_id',
        'promo_codes', 'arcades',
        ['arcade_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_promo_codes_arcade_id', 'promo_codes', type_='foreignkey')
    op.drop_column('promo_codes', 'arcade_id')

    op.add_column(
        'admins',
        sa.Column('arcade_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'admins_arcade_id_fkey',
        'admins', 'arcades',
        ['arcade_id'], ['id'],
    )
    op.execute(
        """
        UPDATE admins ad
        SET arcade_id = a.id
        FROM arcades a
        WHERE a.owner_admin_id = ad.id
        """
    )

    op.drop_constraint('fk_arcades_owner_admin_id', 'arcades', type_='foreignkey')
    op.drop_column('arcades', 'owner_admin_id')
