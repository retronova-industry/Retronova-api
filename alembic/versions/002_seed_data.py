"""Seed data

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:01:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Définir les tables pour les insertions
    ticket_offers = table('ticket_offers',
        column('id', sa.Integer),
        column('tickets_amount', sa.Integer),
        column('price_euros', sa.Float),
        column('name', sa.String),
        column('created_at', sa.DateTime),
        column('updated_at', sa.DateTime),
        column('is_deleted', sa.Boolean)
    )

    games = table('games',
        column('id', sa.Integer),
        column('nom', sa.String),
        column('description', sa.String),
        column('min_players', sa.Integer),
        column('max_players', sa.Integer),
        column('ticket_cost', sa.Integer),
        column('created_at', sa.DateTime),
        column('updated_at', sa.DateTime),
        column('is_deleted', sa.Boolean)
    )

    arcades = table('arcades',
        column('id', sa.Integer),
        column('nom', sa.String),
        column('description', sa.String),
        column('api_key', sa.String),
        column('localisation', sa.String),
        column('latitude', sa.Float),
        column('longitude', sa.Float),
        column('created_at', sa.DateTime),
        column('updated_at', sa.DateTime),
        column('is_deleted', sa.Boolean)
    )

    arcade_games = table('arcade_games',
        column('id', sa.Integer),
        column('arcade_id', sa.Integer),
        column('game_id', sa.Integer),
        column('slot_number', sa.Integer),
        column('created_at', sa.DateTime),
        column('updated_at', sa.DateTime),
        column('is_deleted', sa.Boolean)
    )

    # Utiliser datetime.now(timezone.utc) au lieu de sa.func.now()
    now = datetime.now(timezone.utc)

    # Insertion des offres de tickets
    op.bulk_insert(ticket_offers, [
        {
            'tickets_amount': 1,
            'price_euros': 2.0,
            'name': '1 Ticket',
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'tickets_amount': 10,
            'price_euros': 15.0,
            'name': '10 Tickets',
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'tickets_amount': 20,
            'price_euros': 20.0,
            'name': '20 Tickets',
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        }
    ])

    # Insertion des jeux
    op.bulk_insert(games, [
        {
            'nom': 'Street Fighter',
            'description': 'Jeu de combat classique',
            'min_players': 1,
            'max_players': 2,
            'ticket_cost': 1,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'nom': 'Pac-Man',
            'description': 'Jeu d\'arcade emblématique',
            'min_players': 1,
            'max_players': 1,
            'ticket_cost': 1,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'nom': 'Tekken',
            'description': 'Jeu de combat en 3D',
            'min_players': 1,
            'max_players': 2,
            'ticket_cost': 1,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'nom': 'Space Invaders',
            'description': 'Shoot\'em up spatial',
            'min_players': 1,
            'max_players': 1,
            'ticket_cost': 1,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        }
    ])

    # Insertion des bornes d'arcade
    op.bulk_insert(arcades, [
        {
            'nom': 'Arcade Central',
            'description': 'Borne principale du centre-ville',
            'api_key': 'arcade_key_central_123',
            'localisation': 'Centre-ville Toulouse',
            'latitude': 43.6047,
            'longitude': 1.4442,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'nom': 'Arcade Campus',
            'description': 'Borne du campus universitaire',
            'api_key': 'arcade_key_campus_456',
            'localisation': 'Campus Université Toulouse',
            'latitude': 43.5615,
            'longitude': 1.4679,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        }
    ])

    # Association des jeux aux bornes (on suppose que les IDs sont 1,2,3,4 pour les jeux et 1,2 pour les bornes)
    op.bulk_insert(arcade_games, [
        {
            'arcade_id': 1,
            'game_id': 1,
            'slot_number': 1,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'arcade_id': 1,
            'game_id': 2,
            'slot_number': 2,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'arcade_id': 2,
            'game_id': 3,
            'slot_number': 1,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        },
        {
            'arcade_id': 2,
            'game_id': 4,
            'slot_number': 2,
            'created_at': now,
            'updated_at': now,
            'is_deleted': False
        }
    ])


def downgrade() -> None:
    # Supprimer les données de seed dans l'ordre inverse
    op.execute("DELETE FROM arcade_games WHERE arcade_id IN (1, 2)")
    op.execute("DELETE FROM arcades WHERE id IN (1, 2)")
    op.execute("DELETE FROM games WHERE id IN (1, 2, 3, 4)")
    op.execute("DELETE FROM ticket_offers WHERE id IN (1, 2, 3)")