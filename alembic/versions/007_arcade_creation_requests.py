"""arcade creation requests

Revision ID: 007
Revises: 006
Create Date: 2026-05-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'arcade_creation_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requested_by_admin_id', sa.Integer(), nullable=False),
        sa.Column('nom', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('localisation', sa.String(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='arcaderequeststatus'), nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.String(), nullable=True),
        sa.Column('created_arcade_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by_admin_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['requested_by_admin_id'], ['admins.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by_admin_id'], ['admins.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_arcade_id'], ['arcades.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_arcade_creation_requests_id', 'arcade_creation_requests', ['id'])
    op.create_index('ix_arcade_creation_requests_status', 'arcade_creation_requests', ['status'])


def downgrade() -> None:
    op.drop_index('ix_arcade_creation_requests_status', table_name='arcade_creation_requests')
    op.drop_index('ix_arcade_creation_requests_id', table_name='arcade_creation_requests')
    op.drop_table('arcade_creation_requests')
    op.execute("DROP TYPE IF EXISTS arcaderequeststatus")
