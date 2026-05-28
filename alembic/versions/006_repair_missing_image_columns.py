"""Repair missing image columns

Revision ID: 006
Revises: 005
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE arcades ADD COLUMN IF NOT EXISTS arcade_image VARCHAR")
    op.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS game_image VARCHAR")


def downgrade() -> None:
    op.execute("ALTER TABLE games DROP COLUMN IF EXISTS game_image")
    op.execute("ALTER TABLE arcades DROP COLUMN IF EXISTS arcade_image")
