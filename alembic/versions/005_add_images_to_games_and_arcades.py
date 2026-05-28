"""Add image columns to games and arcades

Revision ID: 005
Revises: 004
Create Date: 2026-04-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("arcades", sa.Column("arcade_image", sa.String(), nullable=True))
    op.add_column("games", sa.Column("game_image", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "game_image")
    op.drop_column("arcades", "arcade_image")
