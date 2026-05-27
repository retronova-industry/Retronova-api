"""Add Stripe Checkout fields

Revision ID: 007
Revises: 006
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ticket_purchases",
        sa.Column("stripe_session_id", sa.String(), nullable=True),
    )
    op.add_column(
        "ticket_purchases",
        sa.Column(
            "payment_status",
            sa.String(),
            nullable=False,
            server_default="paid",
        ),
    )
    op.create_index(
        "ix_ticket_purchases_stripe_session_id",
        "ticket_purchases",
        ["stripe_session_id"],
        unique=False,
    )
    op.alter_column("ticket_purchases", "payment_status", server_default=None)


def downgrade() -> None:
    op.drop_index(
        "ix_ticket_purchases_stripe_session_id",
        table_name="ticket_purchases",
    )
    op.drop_column("ticket_purchases", "payment_status")
    op.drop_column("ticket_purchases", "stripe_session_id")
