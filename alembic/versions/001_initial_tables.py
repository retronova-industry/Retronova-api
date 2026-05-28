# Créer le fichier alembic/versions/001_initial_tables.py

"""Initial tables

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
now = sa.func.now()

def upgrade() -> None:
    # Users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('firebase_uid', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('nom', sa.String(), nullable=False),
        sa.Column('prenom', sa.String(), nullable=False),
        sa.Column('pseudo', sa.String(), nullable=False),
        sa.Column('date_naissance', sa.Date(), nullable=False),
        sa.Column('numero_telephone', sa.String(), nullable=False),
        sa.Column('tickets_balance', sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_firebase_uid'), 'users', ['firebase_uid'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_pseudo'), 'users', ['pseudo'], unique=True)

    # Games table
    op.create_table('games',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('nom', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('min_players', sa.Integer(), nullable=False, default=1),
        sa.Column('max_players', sa.Integer(), nullable=False, default=2),
        sa.Column('ticket_cost', sa.Integer(), nullable=False, default=1),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_games_id'), 'games', ['id'], unique=False)

    # Arcades table
    op.create_table('arcades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('nom', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('api_key', sa.String(), nullable=False),
        sa.Column('localisation', sa.String(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_arcades_id'), 'arcades', ['id'], unique=False)
    op.create_index(op.f('ix_arcades_api_key'), 'arcades', ['api_key'], unique=True)

    # Arcade Games association table
    op.create_table('arcade_games',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('arcade_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('slot_number', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['arcade_id'], ['arcades.id'], ),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_arcade_games_id'), 'arcade_games', ['id'], unique=False)

    # Ticket Offers table
    op.create_table('ticket_offers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('tickets_amount', sa.Integer(), nullable=False),
        sa.Column('price_euros', sa.Float(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticket_offers_id'), 'ticket_offers', ['id'], unique=False)

    # Ticket Purchases table
    op.create_table('ticket_purchases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('offer_id', sa.Integer(), nullable=False),
        sa.Column('tickets_received', sa.Integer(), nullable=False),
        sa.Column('amount_paid', sa.Float(), nullable=False),
        sa.Column('stripe_payment_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['offer_id'], ['ticket_offers.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticket_purchases_id'), 'ticket_purchases', ['id'], unique=False)

    # Friendships table
    op.create_table('friendships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('requester_id', sa.Integer(), nullable=False),
        sa.Column('requested_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'ACCEPTED', 'REJECTED', name='friendshipstatus'), nullable=True),
        sa.ForeignKeyConstraint(['requested_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_friendships_id'), 'friendships', ['id'], unique=False)

    # Reservations table
    op.create_table('reservations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('player2_id', sa.Integer(), nullable=True),
        sa.Column('arcade_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('unlock_code', sa.String(length=1), nullable=False),
        sa.Column('status', sa.Enum('WAITING', 'PLAYING', 'COMPLETED', 'CANCELLED', name='reservationstatus'), nullable=True),
        sa.Column('tickets_used', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['arcade_id'], ['arcades.id'], ),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ),
        sa.ForeignKeyConstraint(['player2_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['player_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reservations_id'), 'reservations', ['id'], unique=False)

    # Scores table
    op.create_table('scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('player1_id', sa.Integer(), nullable=False),
        sa.Column('player2_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('arcade_id', sa.Integer(), nullable=False),
        sa.Column('score_j1', sa.Integer(), nullable=False),
        sa.Column('score_j2', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['arcade_id'], ['arcades.id'], ),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ),
        sa.ForeignKeyConstraint(['player1_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['player2_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scores_id'), 'scores', ['id'], unique=False)

    # Promo Codes table
    op.create_table('promo_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('tickets_reward', sa.Integer(), nullable=False),
        sa.Column('is_single_use_global', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_single_use_per_user', sa.Boolean(), nullable=False, default=True),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('current_uses', sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_promo_codes_id'), 'promo_codes', ['id'], unique=False)
    op.create_index(op.f('ix_promo_codes_code'), 'promo_codes', ['code'], unique=True)

    # Promo Uses table
    op.create_table('promo_uses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=now, nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('promo_code_id', sa.Integer(), nullable=False),
        sa.Column('tickets_received', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['promo_code_id'], ['promo_codes.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_promo_uses_id'), 'promo_uses', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('promo_uses')
    op.drop_table('promo_codes')
    op.drop_table('scores')
    op.drop_table('reservations')
    op.drop_table('friendships')
    op.drop_table('ticket_purchases')
    op.drop_table('ticket_offers')
    op.drop_table('arcade_games')
    op.drop_table('arcades')
    op.drop_table('games')
    op.drop_table('users')