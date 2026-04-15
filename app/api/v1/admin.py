from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.core.database import get_db
from app.models.user import User
from app.models.arcade import Arcade, ArcadeGame
from app.models.game import Game
from app.models.promo import PromoCode
from app.models.ticket import TicketOffer
from app.api.deps import get_current_admin
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

router = APIRouter()


class CreateArcadeRequest(BaseModel):
    nom: str
    description: Optional[str] = ""
    localisation: str
    latitude: float = 0.0
    longitude: float = 0.0


class CreateGameRequest(BaseModel):
    nom: str
    description: str
    min_players: int = 1
    max_players: int = 2
    ticket_cost: int = 1


class CreatePromoCodeRequest(BaseModel):
    code: str
    tickets_reward: int
    is_single_use_global: bool = False
    is_single_use_per_user: bool = True
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True


class UpdatePromoCodeRequest(BaseModel):
    tickets_reward: Optional[int] = None
    is_single_use_global: Optional[bool] = None
    is_single_use_per_user: Optional[bool] = None
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None


class UpdateUserTicketsRequest(BaseModel):
    user_id: int
    tickets_to_add: int


class ArcadeGameAssignmentRequest(BaseModel):
    arcade_id: int
    game_id: int
    slot_number: int


# === RÉSERVATIONS ===

class AdminReservationResponse(BaseModel):
    id: int
    unlock_code: str
    status: str
    arcade_name: str
    game_name: str
    player_pseudo: str
    player2_pseudo: Optional[str]
    tickets_used: int
    position_in_queue: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/reservations/", response_model=List[AdminReservationResponse])
async def get_all_reservations(
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Récupère toutes les réservations (admin uniquement)."""
    from app.models.reservation import Reservation, ReservationStatus

    reservations = db.query(Reservation).filter(
        Reservation.is_deleted == False
    ).order_by(Reservation.created_at.desc()).all()

    result = []
    for reservation in reservations:
        player2_pseudo = None
        if reservation.player2_id:
            player2 = db.query(User).filter(User.id == reservation.player2_id).first()
            if player2:
                player2_pseudo = player2.pseudo

        position_in_queue = None
        if reservation.status == ReservationStatus.WAITING:
            position_in_queue = db.query(Reservation).filter(
                Reservation.arcade_id == reservation.arcade_id,
                Reservation.status == ReservationStatus.WAITING,
                Reservation.created_at <= reservation.created_at,
                Reservation.is_deleted == False
            ).count()

        result.append(AdminReservationResponse(
            id=reservation.id,
            unlock_code=reservation.unlock_code,
            status=reservation.status.value,
            arcade_name=reservation.arcade.nom,
            game_name=reservation.game.nom,
            player_pseudo=reservation.player.pseudo,
            player2_pseudo=player2_pseudo,
            tickets_used=reservation.tickets_used,
            position_in_queue=position_in_queue,
            created_at=reservation.created_at
        ))

    return result


# === GESTION DES BORNES ===
@router.post("/arcades/")
async def create_arcade(
        arcade_data: CreateArcadeRequest,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Crée une nouvelle borne d'arcade."""

    # Générer une clé API unique pour la borne
    import secrets
    api_key = f"arcade_key_{secrets.token_urlsafe(16)}"

    arcade = Arcade(
        nom=arcade_data.nom,
        description=arcade_data.description,
        api_key=api_key,
        localisation=arcade_data.localisation,
        latitude=arcade_data.latitude,
        longitude=arcade_data.longitude
    )

    db.add(arcade)
    db.commit()
    db.refresh(arcade)

    return {"message": "Borne créée", "arcade_id": arcade.id, "api_key": api_key}


@router.put("/arcades/{arcade_id}")
async def update_arcade(
        arcade_id: int,
        arcade_data: CreateArcadeRequest,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Met à jour les informations d'une borne d'arcade."""

    arcade = db.query(Arcade).filter(
        Arcade.id == arcade_id,
        Arcade.is_deleted == False
    ).first()

    if not arcade:
        raise HTTPException(status_code=404, detail="Borne non trouvée")

    arcade.nom = arcade_data.nom
    arcade.description = arcade_data.description
    arcade.localisation = arcade_data.localisation
    arcade.latitude = arcade_data.latitude
    arcade.longitude = arcade_data.longitude

    db.commit()
    db.refresh(arcade)

    return {"message": "Borne mise à jour", "arcade_id": arcade.id}


@router.put("/arcades/{arcade_id}/games")
async def assign_game_to_arcade(
        assignment: ArcadeGameAssignmentRequest,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Assigne un jeu à une borne sur un slot spécifique."""

    # Vérifier que la borne existe
    arcade = db.query(Arcade).filter(Arcade.id == assignment.arcade_id).first()
    if not arcade:
        raise HTTPException(status_code=404, detail="Borne non trouvée")

    # Vérifier que le jeu existe
    game = db.query(Game).filter(Game.id == assignment.game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Jeu non trouvé")

    # Vérifier que le slot est valide (1 ou 2)
    if assignment.slot_number not in [1, 2]:
        raise HTTPException(status_code=400, detail="Le slot doit être 1 ou 2")

    # Supprimer l'ancien jeu sur ce slot s'il existe
    existing = db.query(ArcadeGame).filter(
        ArcadeGame.arcade_id == assignment.arcade_id,
        ArcadeGame.slot_number == assignment.slot_number
    ).first()

    if existing:
        db.delete(existing)

    # Créer la nouvelle assignation
    arcade_game = ArcadeGame(
        arcade_id=assignment.arcade_id,
        game_id=assignment.game_id,
        slot_number=assignment.slot_number
    )

    db.add(arcade_game)
    db.commit()

    return {"message": f"Jeu {game.nom} assigné au slot {assignment.slot_number} de la borne {arcade.nom}"}


# === GESTION DES JEUX ===
@router.post("/games/")
async def create_game(
        game_data: CreateGameRequest,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Crée un nouveau jeu."""

    game = Game(
        nom=game_data.nom,
        description=game_data.description,
        min_players=game_data.min_players,
        max_players=game_data.max_players,
        ticket_cost=game_data.ticket_cost
    )

    db.add(game)
    db.commit()
    db.refresh(game)

    return {"message": "Jeu créé", "game_id": game.id}


# === GESTION DES CODES PROMO ===
@router.post("/promo-codes/")
async def create_promo_code(
        promo_data: CreatePromoCodeRequest,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Crée un nouveau code promo avec gestion des dates."""

    # Validation des dates
    if promo_data.valid_from and promo_data.valid_until:
        if promo_data.valid_until <= promo_data.valid_from:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La date d'expiration doit être après la date de début"
            )

    # Vérifier que le code n'existe pas déjà
    existing = db.query(PromoCode).filter(
        PromoCode.code == promo_data.code.upper().strip()
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce code promo existe déjà"
        )

    promo_code = PromoCode(
        code=promo_data.code.upper().strip(),
        tickets_reward=promo_data.tickets_reward,
        is_single_use_global=promo_data.is_single_use_global,
        is_single_use_per_user=promo_data.is_single_use_per_user,
        usage_limit=promo_data.usage_limit,
        valid_from=promo_data.valid_from,
        valid_until=promo_data.valid_until,
        is_active=promo_data.is_active
    )

    db.add(promo_code)
    db.commit()
    db.refresh(promo_code)

    return {
        "message": "Code promo créé",
        "promo_code_id": promo_code.id,
        "is_valid_now": promo_code.is_valid_now(),
        "days_until_expiry": promo_code.days_until_expiry()
    }


@router.put("/promo-codes/{promo_code_id}")
async def update_promo_code(
        promo_code_id: int,
        update_data: UpdatePromoCodeRequest,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Met à jour un code promo existant."""

    promo_code = db.query(PromoCode).filter(
        PromoCode.id == promo_code_id,
        PromoCode.is_deleted == False
    ).first()

    if not promo_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Code promo non trouvé"
        )

    # Validation des dates si elles sont mises à jour
    valid_from = update_data.valid_from if update_data.valid_from is not None else promo_code.valid_from
    valid_until = update_data.valid_until if update_data.valid_until is not None else promo_code.valid_until

    if valid_from and valid_until and valid_until <= valid_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date d'expiration doit être après la date de début"
        )

    # Mettre à jour les champs modifiés
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(promo_code, field, value)

    db.commit()
    db.refresh(promo_code)

    return {
        "message": "Code promo mis à jour",
        "promo_code_id": promo_code.id,
        "is_valid_now": promo_code.is_valid_now(),
        "days_until_expiry": promo_code.days_until_expiry()
    }


@router.get("/promo-codes/")
async def list_promo_codes(
        include_expired: bool = False,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Liste tous les codes promo avec filtrage optionnel."""

    query = db.query(PromoCode).filter(PromoCode.is_deleted == False)

    if not include_expired:
        now = datetime.now(timezone.utc)
        query = query.filter(
            (PromoCode.valid_until.is_(None) | (PromoCode.valid_until > now))
        )

    promo_codes = query.order_by(PromoCode.created_at.desc()).all()

    result = []
    for promo in promo_codes:
        result.append({
            "id": promo.id,
            "code": promo.code,
            "tickets_reward": promo.tickets_reward,
            "usage_limit": promo.usage_limit,
            "current_uses": promo.current_uses,
            "is_single_use_global": promo.is_single_use_global,
            "is_single_use_per_user": promo.is_single_use_per_user,
            "valid_from": promo.valid_from.isoformat() if promo.valid_from else None,
            "valid_until": promo.valid_until.isoformat() if promo.valid_until else None,
            "is_active": promo.is_active,
            "is_valid_now": promo.is_valid_now(),
            "is_expired": promo.is_expired(),
            "days_until_expiry": promo.days_until_expiry(),
            "created_at": promo.created_at.isoformat()
        })

    return result


@router.post("/promo-codes/{promo_code_id}/toggle-active")
async def toggle_promo_code_active(
        promo_code_id: int,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Active/désactive manuellement un code promo."""

    promo_code = db.query(PromoCode).filter(
        PromoCode.id == promo_code_id,
        PromoCode.is_deleted == False
    ).first()

    if not promo_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Code promo non trouvé"
        )

    promo_code.is_active = not promo_code.is_active
    db.commit()

    return {
        "message": f"Code promo {'activé' if promo_code.is_active else 'désactivé'}",
        "promo_code_id": promo_code.id,
        "is_active": promo_code.is_active,
        "is_valid_now": promo_code.is_valid_now()
    }


@router.get("/promo-codes/expiring-soon")
async def get_expiring_promo_codes(
        days_ahead: int = 7,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Récupère les codes promo qui expirent bientôt."""

    now = datetime.now(timezone.utc)
    future_date = now + timedelta(days=days_ahead)

    expiring_codes = db.query(PromoCode).filter(
        PromoCode.is_deleted == False,
        PromoCode.is_active == True,
        PromoCode.valid_until.isnot(None),
        PromoCode.valid_until <= future_date,
        PromoCode.valid_until > now
    ).order_by(PromoCode.valid_until).all()

    result = []
    for promo in expiring_codes:
        result.append({
            "id": promo.id,
            "code": promo.code,
            "tickets_reward": promo.tickets_reward,
            "valid_until": promo.valid_until.isoformat(),
            "days_until_expiry": promo.days_until_expiry(),
            "current_uses": promo.current_uses,
            "usage_limit": promo.usage_limit
        })

    return {
        "expiring_codes": result,
        "total_count": len(result),
        "days_ahead": days_ahead
    }

# === GESTION DES UTILISATEURS ===
@router.put("/users/tickets")
async def update_user_tickets(
        update_data: UpdateUserTicketsRequest,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Ajoute ou retire des tickets à un utilisateur."""

    user = db.query(User).filter(
        User.id == update_data.user_id,
        User.is_deleted == False
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    old_balance = user.tickets_balance
    user.tickets_balance += update_data.tickets_to_add

    # Empêcher un solde négatif
    if user.tickets_balance < 0:
        user.tickets_balance = 0

    db.commit()

    return {
        "message": f"Solde mis à jour pour {user.pseudo}",
        "old_balance": old_balance,
        "new_balance": user.tickets_balance,
        "tickets_added": update_data.tickets_to_add
    }


@router.get("/users/deleted")
async def list_deleted_users(
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Liste les utilisateurs supprimés (soft delete)."""

    deleted_users = db.query(User).filter(
        User.is_deleted == True
    ).all()

    return deleted_users


@router.put("/users/{user_id}/restore")
async def restore_user(
        user_id: int,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Restaure un utilisateur supprimé."""

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    if not user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet utilisateur n'est pas supprimé"
        )

    user.is_deleted = False
    user.deleted_at = None
    db.commit()

    return {"message": f"Utilisateur {user.pseudo} restauré"}


@router.delete("/users/{user_id}")
async def soft_delete_user(
        user_id: int,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Supprime un utilisateur (soft delete) - Accès admin uniquement."""

    user = db.query(User).filter(
        User.id == user_id,
        User.is_deleted == False
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    # Vérifier s'il y a des réservations en cours
    from app.models.reservation import Reservation, ReservationStatus
    active_reservations = db.query(Reservation).filter(
        (Reservation.player_id == user_id) | (Reservation.player2_id == user_id),
        Reservation.status.in_([ReservationStatus.WAITING, ReservationStatus.PLAYING]),
        Reservation.is_deleted == False
    ).count()

    if active_reservations > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de supprimer l'utilisateur : {active_reservations} réservation(s) active(s). "
                   "Veuillez d'abord gérer les réservations en cours."
        )

    # Soft delete de l'utilisateur
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)

    # Soft delete des relations d'amitié
    from app.models.friend import Friendship
    friendships = db.query(Friendship).filter(
        (Friendship.requester_id == user_id) | (Friendship.requested_id == user_id),
        Friendship.is_deleted == False
    ).all()

    deleted_friendships = 0
    for friendship in friendships:
        friendship.is_deleted = True
        friendship.deleted_at = datetime.now(timezone.utc)
        deleted_friendships += 1

    # Soft delete des codes promo utilisés (optionnel, pour conformité RGPD)
    from app.models.promo import PromoUse
    promo_uses = db.query(PromoUse).filter(
        PromoUse.user_id == user_id,
        PromoUse.is_deleted == False
    ).all()

    deleted_promo_uses = 0
    for promo_use in promo_uses:
        promo_use.is_deleted = True
        promo_use.deleted_at = datetime.now(timezone.utc)
        deleted_promo_uses += 1

    # Soft delete des achats de tickets (optionnel, pour conformité RGPD)
    from app.models.ticket import TicketPurchase
    ticket_purchases = db.query(TicketPurchase).filter(
        TicketPurchase.user_id == user_id,
        TicketPurchase.is_deleted == False
    ).all()

    deleted_purchases = 0
    for purchase in ticket_purchases:
        purchase.is_deleted = True
        purchase.deleted_at = datetime.now(timezone.utc)
        deleted_purchases += 1

    db.commit()

    return {
        "message": f"Utilisateur '{user.pseudo}' supprimé avec succès",
        "user_id": user.id,
        "deleted_friendships": deleted_friendships,
        "deleted_promo_uses": deleted_promo_uses,
        "deleted_purchases": deleted_purchases,
        "note": "Les scores sont conservés de manière anonymisée pour l'intégrité des données de jeu"
    }


@router.get("/users/{user_id}/deletion-impact")
async def get_user_deletion_impact(
        user_id: int,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Analyse l'impact de la suppression d'un utilisateur avant de la confirmer."""

    user = db.query(User).filter(
        User.id == user_id,
        User.is_deleted == False
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    # Compter les éléments qui seraient affectés
    from app.models.reservation import Reservation, ReservationStatus
    from app.models.friend import Friendship
    from app.models.promo import PromoUse
    from app.models.ticket import TicketPurchase
    from app.models.score import Score

    # Réservations actives (bloquantes)
    active_reservations = db.query(Reservation).filter(
        (Reservation.player_id == user_id) | (Reservation.player2_id == user_id),
        Reservation.status.in_([ReservationStatus.WAITING, ReservationStatus.PLAYING]),
        Reservation.is_deleted == False
    ).count()

    # Réservations terminées (conservées)
    completed_reservations = db.query(Reservation).filter(
        (Reservation.player_id == user_id) | (Reservation.player2_id == user_id),
        Reservation.status.in_([ReservationStatus.COMPLETED, ReservationStatus.CANCELLED]),
        Reservation.is_deleted == False
    ).count()

    # Amitiés
    friendships_count = db.query(Friendship).filter(
        (Friendship.requester_id == user_id) | (Friendship.requested_id == user_id),
        Friendship.is_deleted == False
    ).count()

    # Codes promo utilisés
    promo_uses_count = db.query(PromoUse).filter(
        PromoUse.user_id == user_id,
        PromoUse.is_deleted == False
    ).count()

    # Achats de tickets
    purchases_count = db.query(TicketPurchase).filter(
        TicketPurchase.user_id == user_id,
        TicketPurchase.is_deleted == False
    ).count()

    # Scores (conservés de manière anonymisée)
    scores_as_player1 = db.query(Score).filter(
        Score.player1_id == user_id,
        Score.is_deleted == False
    ).count()

    scores_as_player2 = db.query(Score).filter(
        Score.player2_id == user_id,
        Score.is_deleted == False
    ).count()

    total_scores = scores_as_player1 + scores_as_player2

    can_delete = active_reservations == 0

    return {
        "user": {
            "id": user.id,
            "pseudo": user.pseudo,
            "email": user.email,
            "tickets_balance": user.tickets_balance,
            "created_at": user.created_at.isoformat()
        },
        "can_delete": can_delete,
        "blocking_factors": {
            "active_reservations": active_reservations
        } if not can_delete else {},
        "deletion_impact": {
            "friendships_to_delete": friendships_count,
            "promo_uses_to_delete": promo_uses_count,
            "purchases_to_delete": purchases_count,
            "completed_reservations_preserved": completed_reservations,
            "scores_anonymized": total_scores
        },
        "recommendations": [
                               "Les scores seront conservés de manière anonymisée pour préserver l'intégrité des classements",
                               "Les réservations terminées seront préservées pour l'historique",
                               "Les données personnelles seront marquées comme supprimées conformément au RGPD"
                           ] + (
                               ["⚠️ Annulez d'abord les réservations actives avant la suppression"] if not can_delete else [])
    }


@router.put("/users/{user_id}/force-cancel-reservations")
async def force_cancel_user_reservations(
        user_id: int,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Force l'annulation de toutes les réservations actives d'un utilisateur (admin uniquement)."""

    user = db.query(User).filter(
        User.id == user_id,
        User.is_deleted == False
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    # Annuler toutes les réservations actives
    from app.models.reservation import Reservation, ReservationStatus
    active_reservations = db.query(Reservation).filter(
        (Reservation.player_id == user_id) | (Reservation.player2_id == user_id),
        Reservation.status.in_([ReservationStatus.WAITING, ReservationStatus.PLAYING]),
        Reservation.is_deleted == False
    ).all()

    cancelled_count = 0
    refunded_tickets = 0

    for reservation in active_reservations:
        # Annuler la réservation
        reservation.status = ReservationStatus.CANCELLED

        # Rembourser les tickets si l'utilisateur était le joueur principal
        if reservation.player_id == user_id:
            user.tickets_balance += reservation.tickets_used
            refunded_tickets += reservation.tickets_used

        cancelled_count += 1

    db.commit()

    return {
        "message": f"Réservations de l'utilisateur '{user.pseudo}' annulées",
        "user_id": user.id,
        "cancelled_reservations": cancelled_count,
        "refunded_tickets": refunded_tickets,
        "new_tickets_balance": user.tickets_balance
    }

# === STATISTIQUES ===
@router.get("/stats")
async def get_admin_stats(
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Récupère les statistiques globales de la plateforme."""

    # Compter les utilisateurs actifs
    active_users = db.query(User).filter(User.is_deleted == False).count()

    # Compter les bornes
    total_arcades = db.query(Arcade).filter(Arcade.is_deleted == False).count()

    # Compter les jeux
    total_games = db.query(Game).filter(Game.is_deleted == False).count()

    # Compter les codes promo actifs
    active_promo_codes = db.query(PromoCode).filter(
        PromoCode.is_deleted == False
    ).count()

    # Total de tickets en circulation
    total_tickets = db.query(func.sum(User.tickets_balance)).filter(
        User.is_deleted == False
    ).scalar() or 0

    return {
        "active_users": active_users,
        "total_arcades": total_arcades,
        "total_games": total_games,
        "active_promo_codes": active_promo_codes,
        "total_tickets_in_circulation": total_tickets,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.delete("/arcades/{arcade_id}")
async def soft_delete_arcade(
        arcade_id: int,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Supprime une borne d'arcade (soft delete)."""

    arcade = db.query(Arcade).filter(
        Arcade.id == arcade_id,
        Arcade.is_deleted == False
    ).first()

    if not arcade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borne d'arcade non trouvée"
        )

    # Vérifier s'il y a des réservations en cours sur cette borne
    from app.models.reservation import Reservation, ReservationStatus
    active_reservations = db.query(Reservation).filter(
        Reservation.arcade_id == arcade_id,
        Reservation.status.in_([ReservationStatus.WAITING, ReservationStatus.PLAYING]),
        Reservation.is_deleted == False
    ).count()

    if active_reservations > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de supprimer la borne : {active_reservations} réservation(s) active(s)"
        )

    # Soft delete
    arcade.is_deleted = True
    arcade.deleted_at = datetime.now(timezone.utc)

    # Soft delete des associations arcade-jeux
    arcade_games = db.query(ArcadeGame).filter(
        ArcadeGame.arcade_id == arcade_id,
        ArcadeGame.is_deleted == False
    ).all()

    for ag in arcade_games:
        ag.is_deleted = True
        ag.deleted_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "message": f"Borne '{arcade.nom}' supprimée avec succès",
        "arcade_id": arcade.id,
        "deleted_associations": len(arcade_games)
    }


@router.get("/arcades/deleted")
async def list_deleted_arcades(
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Liste les bornes d'arcade supprimées (soft delete)."""

    deleted_arcades = db.query(Arcade).filter(
        Arcade.is_deleted == True
    ).order_by(Arcade.deleted_at.desc()).all()

    return deleted_arcades


@router.put("/arcades/{arcade_id}/restore")
async def restore_arcade(
        arcade_id: int,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Restaure une borne d'arcade supprimée."""

    arcade = db.query(Arcade).filter(Arcade.id == arcade_id).first()

    if not arcade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borne d'arcade non trouvée"
        )

    if not arcade.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette borne n'est pas supprimée"
        )

    # Vérifier l'unicité de la clé API (au cas où elle aurait été réassignée)
    existing_api_key = db.query(Arcade).filter(
        Arcade.api_key == arcade.api_key,
        Arcade.is_deleted == False,
        Arcade.id != arcade_id
    ).first()

    if existing_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La clé API de cette borne est maintenant utilisée par une autre borne. "
                   "Veuillez générer une nouvelle clé API."
        )

    # Restaurer la borne
    arcade.is_deleted = False
    arcade.deleted_at = None

    # Restaurer les associations arcade-jeux
    arcade_games = db.query(ArcadeGame).filter(
        ArcadeGame.arcade_id == arcade_id,
        ArcadeGame.is_deleted == True
    ).all()

    restored_associations = 0
    for ag in arcade_games:
        # Vérifier que le jeu existe toujours
        game_exists = db.query(Game).filter(
            Game.id == ag.game_id,
            Game.is_deleted == False
        ).first()

        if game_exists:
            # Vérifier qu'il n'y a pas de conflit de slot
            slot_conflict = db.query(ArcadeGame).filter(
                ArcadeGame.arcade_id == arcade_id,
                ArcadeGame.slot_number == ag.slot_number,
                ArcadeGame.is_deleted == False,
                ArcadeGame.id != ag.id
            ).first()

            if not slot_conflict:
                ag.is_deleted = False
                ag.deleted_at = None
                restored_associations += 1

    db.commit()

    return {
        "message": f"Borne '{arcade.nom}' restaurée avec succès",
        "arcade_id": arcade.id,
        "restored_associations": restored_associations,
        "note": f"{len(arcade_games) - restored_associations} association(s) non restaurée(s) en raison de conflits" if restored_associations < len(
            arcade_games) else None
    }


@router.put("/arcades/{arcade_id}/regenerate-api-key")
async def regenerate_arcade_api_key(
        arcade_id: int,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_admin)
):
    """Régénère la clé API d'une borne d'arcade."""

    arcade = db.query(Arcade).filter(
        Arcade.id == arcade_id
    ).first()

    if not arcade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borne d'arcade non trouvée"
        )

    # Générer une nouvelle clé API unique
    import secrets
    new_api_key = f"arcade_key_{secrets.token_urlsafe(16)}"

    # Vérifier l'unicité (au cas où)
    while db.query(Arcade).filter(Arcade.api_key == new_api_key).first():
        new_api_key = f"arcade_key_{secrets.token_urlsafe(16)}"

    old_api_key = arcade.api_key
    arcade.api_key = new_api_key
    db.commit()

    return {
        "message": f"Clé API de la borne '{arcade.nom}' régénérée",
        "arcade_id": arcade.id,
        "old_api_key": old_api_key[:20] + "...",  # Masquer partiellement
        "new_api_key": new_api_key
    }