"""Add missing Stripe/payment columns to ticket_purchases

Revision ID: 005
Revises: 004
Create Date: 2026-04-15 14:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _existing_columns("ticket_purchases")

    if "stripe_checkout_session_id" not in columns:
        op.add_column(
            "ticket_purchases",
            sa.Column("stripe_checkout_session_id", sa.String(), nullable=True),
        )

    if "stripe_payment_intent_id" not in columns:
        op.add_column(
            "ticket_purchases",
            sa.Column("stripe_payment_intent_id", sa.String(), nullable=True),
        )

    if "status" not in columns:
        op.add_column(
            "ticket_purchases",
            sa.Column(
                "status",
                sa.String(),
                nullable=False,
                server_default="pending",
            ),
        )

    if "paid_at" not in columns:
        op.add_column(
            "ticket_purchases",
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    columns = _existing_columns("ticket_purchases")

    if "paid_at" in columns:
        op.drop_column("ticket_purchases", "paid_at")

    if "status" in columns:
        op.drop_column("ticket_purchases", "status")

    if "stripe_payment_intent_id" in columns:
        op.drop_column("ticket_purchases", "stripe_payment_intent_id")

    if "stripe_checkout_session_id" in columns:
        op.drop_column("ticket_purchases", "stripe_checkout_session_id")
