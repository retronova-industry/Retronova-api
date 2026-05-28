import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.arcade import Arcade, ArcadeGame
from app.models.game import Game
from app.models.promo import PromoCode
from app.models.ticket import TicketOffer
from app.models.admin import Admin, AdminRole
from app.models.arcade_request import ArcadeCreationRequest, ArcadeRequestStatus
from app.api.deps import get_current_admin, get_current_super_admin, get_current_arcade_owner
from app.core.security import set_admin_custom_claims, create_firebase_admin_user, generate_password_reset_link
from app.core.email import send_arcade_owner_invitation
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateArcadeRequest(BaseModel):
    nom: str
    description: str
    localisation: str
    latitude: float
    longitude: float


class UpdateArcadeRequest(BaseModel):
    nom: Optional[str] = None
    description: Optional[str] = None
    localisation: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CreateGameRequest(BaseModel):
    nom: str
    description: str
    min_players: int = 1
    max_players: int = 2
    ticket_cost: int = 1


class CreatePromoCodeRequest(BaseModel):
    code: str
    tickets_reward: int
    arcade_id: int
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


class AdminMeResponse(BaseModel):
    id: int
    firebase_uid: str
    email: str
    role: str
    arcade_ids: List[int]

    class Config:
        from_attributes = True


def _admin_to_me(admin: Admin) -> AdminMeResponse:
    arcade_ids = [a.id for a in admin.arcades if not a.is_deleted] if admin.role == AdminRole.arcade_owner else []
    return AdminMeResponse(
        id=admin.id,
        firebase_uid=admin.firebase_uid,
        email=admin.email,
        role=admin.role.value if hasattr(admin.role, "value") else admin.role,
        arcade_ids=arcade_ids,
    )


# === PROFIL ADMIN ===
@router.get("/me", response_model=AdminMeResponse)
async def get_admin_me(
        current_admin: Admin = Depends(get_current_admin)
):
    """Retourne les informations de l'admin connecté."""
    return _admin_to_me(current_admin)


# === GESTION DES BORNES ===
@router.post("/arcades/")
async def create_arcade(
        arcade_data: CreateArcadeRequest,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return create_arcade_service(db, arcade_data)


@router.put("/arcades/{arcade_id}", responses=ARCADE_NOT_FOUND_RESPONSE)
async def update_arcade(
    arcade_id: int,
    arcade_data: CreateArcadeRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return update_arcade_service(db, arcade_id, arcade_data)


@router.put("/arcades/{arcade_id}")
async def update_arcade(
        arcade_id: int,
        arcade_data: UpdateArcadeRequest,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Met à jour les informations d'une borne. arcade_owner ne peut modifier que ses propres bornes."""
    arcade = db.query(Arcade).filter(
        Arcade.id == arcade_id,
        Arcade.is_deleted == False
    ).first()
    if not arcade:
        raise HTTPException(status_code=404, detail="Borne non trouvée")

    if current_admin.role == AdminRole.arcade_owner:
        owned_ids = [a.id for a in current_admin.arcades]
        if arcade_id not in owned_ids:
            raise HTTPException(status_code=403, detail="Vous ne pouvez modifier que vos propres bornes")

    if arcade_data.nom is not None:
        arcade.nom = arcade_data.nom
    if arcade_data.description is not None:
        arcade.description = arcade_data.description
    if arcade_data.localisation is not None:
        arcade.localisation = arcade_data.localisation
    if arcade_data.latitude is not None:
        arcade.latitude = arcade_data.latitude
    if arcade_data.longitude is not None:
        arcade.longitude = arcade_data.longitude

    db.commit()
    db.refresh(arcade)
    return arcade


@router.put("/arcades/{arcade_id}/games")
async def assign_game_to_arcade(
        assignment: ArcadeGameAssignmentRequest,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Assigne un jeu à une borne sur un slot spécifique. arcade_owner ne peut modifier que ses propres bornes."""

    # Vérifier que la borne existe
    arcade = db.query(Arcade).filter(Arcade.id == assignment.arcade_id).first()
    if not arcade:
        raise HTTPException(status_code=404, detail="Borne non trouvée")

    if current_admin.role == AdminRole.arcade_owner:
        owned_ids = [a.id for a in current_admin.arcades]
        if assignment.arcade_id not in owned_ids:
            raise HTTPException(status_code=403, detail="Vous ne pouvez modifier que les bornes qui vous sont assignées")

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


@router.delete("/arcades/{arcade_id}/games/{slot_number}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_game_from_slot(
        arcade_id: int,
        slot_number: int,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Retire le jeu d'un slot. arcade_owner ne peut modifier que ses propres bornes."""
    if slot_number not in [1, 2]:
        raise HTTPException(status_code=400, detail="Le slot doit être 1 ou 2")

    if current_admin.role == AdminRole.arcade_owner:
        owned_ids = [a.id for a in current_admin.arcades]
        if arcade_id not in owned_ids:
            raise HTTPException(status_code=403, detail="Vous ne pouvez modifier que les bornes qui vous sont assignées")

    existing = db.query(ArcadeGame).filter(
        ArcadeGame.arcade_id == arcade_id,
        ArcadeGame.slot_number == slot_number
    ).first()

    if existing:
        db.delete(existing)
        db.commit()


# === GESTION DES JEUX ===
@router.post("/games/")
async def create_game(
        game_data: CreateGameRequest,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return create_game_service(db, game_data)


@router.put("/games/{game_id}")
async def update_game(
        game_id: int,
        game_data: CreateGameRequest,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Met à jour un jeu existant."""
    game = db.query(Game).filter(
        Game.id == game_id,
        Game.is_deleted == False
    ).first()
    if not game:
        raise HTTPException(status_code=404, detail="Jeu non trouvé")

    game.nom = game_data.nom
    game.description = game_data.description
    game.min_players = game_data.min_players
    game.max_players = game_data.max_players
    game.ticket_cost = game_data.ticket_cost

    db.commit()
    db.refresh(game)
    return game


@router.delete("/games/{game_id}")
async def soft_delete_game(
        game_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Supprime un jeu (soft delete)."""

    game = db.query(Game).filter(
        Game.id == game_id,
        Game.is_deleted == False
    ).first()

    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jeu non trouvé"
        )

    # Bloquer si des réservations actives utilisent ce jeu
    from app.models.reservation import Reservation, ReservationStatus
    active_reservations = db.query(Reservation).filter(
        Reservation.game_id == game_id,
        Reservation.status.in_([ReservationStatus.WAITING, ReservationStatus.PLAYING]),
        Reservation.is_deleted == False
    ).count()

    if active_reservations > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de supprimer le jeu : {active_reservations} réservation(s) active(s)"
        )

    # Soft delete du jeu
    game.is_deleted = True
    game.deleted_at = datetime.now(timezone.utc)

    # Soft delete des associations arcade-jeu
    arcade_games = db.query(ArcadeGame).filter(
        ArcadeGame.game_id == game_id,
        ArcadeGame.is_deleted == False
    ).all()

    for ag in arcade_games:
        ag.is_deleted = True
        ag.deleted_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "message": f"Jeu '{game.nom}' supprimé avec succès",
        "game_id": game.id,
        "deleted_associations": len(arcade_games)
    }


# === GESTION DES CODES PROMO (arcade_owner) ===
def _owner_arcade_ids(admin: Admin) -> List[int]:
    return [a.id for a in admin.arcades if not a.is_deleted]


def _ensure_owns_arcade(admin: Admin, arcade_id: int) -> None:
    if admin.role == AdminRole.super_admin:
        return
    if arcade_id not in _owner_arcade_ids(admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette borne n'est pas assignée à ce propriétaire"
        )


@router.post("/promo-codes/")
async def create_promo_code(
        promo_data: CreatePromoCodeRequest,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Crée un nouveau code promo, scopé à une borne du propriétaire."""

    _ensure_owns_arcade(current_admin, promo_data.arcade_id)

    if promo_data.valid_from and promo_data.valid_until:
        if promo_data.valid_until <= promo_data.valid_from:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La date d'expiration doit être après la date de début"
            )

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
        arcade_id=promo_data.arcade_id,
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
        "arcade_id": promo_code.arcade_id,
        "is_valid_now": promo_code.is_valid_now(),
        "days_until_expiry": promo_code.days_until_expiry()
    }


@router.put("/promo-codes/{promo_code_id}")
async def update_promo_code(
        promo_code_id: int,
        update_data: UpdatePromoCodeRequest,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Met à jour un code promo existant (propriétaire de l'arcade associée)."""

    promo_code = db.query(PromoCode).filter(
        PromoCode.id == promo_code_id,
        PromoCode.is_deleted == False
    ).first()

    if not promo_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Code promo non trouvé"
        )

    if promo_code.arcade_id is not None:
        _ensure_owns_arcade(current_admin, promo_code.arcade_id)
    elif current_admin.role != AdminRole.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Code promo non scopé à votre borne")

    valid_from = update_data.valid_from if update_data.valid_from is not None else promo_code.valid_from
    valid_until = update_data.valid_until if update_data.valid_until is not None else promo_code.valid_until

    if valid_from and valid_until and valid_until <= valid_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date d'expiration doit être après la date de début"
        )

    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(promo_code, field, value)


@router.put("/promo-codes/{promo_code_id}", responses=PROMO_CODE_NOT_FOUND_RESPONSE)
async def update_promo_code(
    promo_code_id: int,
    update_data: UpdatePromoCodeRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return update_promo_code_service(db, promo_code_id, update_data)


@router.get("/promo-codes/")
async def list_promo_codes(
        include_expired: bool = False,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Liste les codes promo. Pour un arcade_owner, scopés à ses bornes."""

    query = db.query(PromoCode).filter(PromoCode.is_deleted == False)

    if current_admin.role == AdminRole.arcade_owner:
        owned = _owner_arcade_ids(current_admin)
        if not owned:
            return []
        query = query.filter(PromoCode.arcade_id.in_(owned))

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
            "arcade_id": promo.arcade_id,
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
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Active/désactive manuellement un code promo."""

    promo_code = db.query(PromoCode).filter(
        PromoCode.id == promo_code_id,
        PromoCode.is_deleted == False
    ).first()


    if promo_code.arcade_id is not None:
        _ensure_owns_arcade(current_admin, promo_code.arcade_id)
    elif current_admin.role != AdminRole.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Code promo non scopé à votre borne")

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
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Récupère les codes promo qui expirent bientôt."""

    now = datetime.now(timezone.utc)
    future_date = now + timedelta(days=days_ahead)

    query = db.query(PromoCode).filter(
        PromoCode.is_deleted == False,
        PromoCode.is_active == True,
        PromoCode.valid_until.isnot(None),
        PromoCode.valid_until <= future_date,
        PromoCode.valid_until > now
    )

    if current_admin.role == AdminRole.arcade_owner:
        owned = _owner_arcade_ids(current_admin)
        if not owned:
            return {"expiring_codes": [], "total_count": 0, "days_ahead": days_ahead}
        query = query.filter(PromoCode.arcade_id.in_(owned))

    expiring_codes = query.order_by(PromoCode.valid_until).all()

    result = []
    for promo in expiring_codes:
        result.append({
            "id": promo.id,
            "code": promo.code,
            "tickets_reward": promo.tickets_reward,
            "arcade_id": promo.arcade_id,
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
        _: Admin = Depends(get_current_super_admin)
):
    return get_expiring_promo_codes_service(db, days_ahead)


@router.put("/users/tickets", responses=USER_NOT_FOUND_RESPONSE)
async def update_user_tickets(
    update_data: UpdateUserTicketsRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return update_user_tickets_service(db, update_data)


@router.get("/users/deleted")
async def list_deleted_users(
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return list_deleted_users_service(db)


@router.put("/users/{user_id}/restore", responses=USER_NOT_FOUND_RESPONSE)
async def restore_user(
        user_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return restore_user_service(db, user_id)


@router.delete("/users/{user_id}", responses=USER_NOT_FOUND_RESPONSE)
async def soft_delete_user(
        user_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return soft_delete_user_service(db, user_id)


@router.get("/users/{user_id}/deletion-impact", responses=USER_NOT_FOUND_RESPONSE)
async def get_user_deletion_impact(
        user_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return get_user_deletion_impact_service(db, user_id)


@router.put(
    "/users/{user_id}/force-cancel-reservations",
    responses=USER_NOT_FOUND_RESPONSE,
)
async def force_cancel_user_reservations(
        user_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return force_cancel_user_reservations_service(db, user_id)


@router.get("/stats")
async def get_admin_stats(
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_admin)
):
    """Statistiques globales (super_admin) ou scopées à la borne (arcade_owner)."""

    if current_admin.role == AdminRole.arcade_owner:
        from app.models.reservation import Reservation, ReservationStatus
        from app.models.score import Score
        arcade_ids = _owner_arcade_ids(current_admin)
        if not arcade_ids:
            return {
                "arcades": [],
                "active_reservations": 0,
                "playing_reservations": 0,
                "total_scores": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
        arcades = db.query(Arcade).filter(Arcade.id.in_(arcade_ids), Arcade.is_deleted == False).all()
        active_reservations = db.query(Reservation).filter(
            Reservation.arcade_id.in_(arcade_ids),
            Reservation.status == ReservationStatus.WAITING,
            Reservation.is_deleted == False
        ).count()
        playing_reservations = db.query(Reservation).filter(
            Reservation.arcade_id.in_(arcade_ids),
            Reservation.status == ReservationStatus.PLAYING,
            Reservation.is_deleted == False
        ).count()
        total_scores = db.query(Score).filter(
            Score.arcade_id.in_(arcade_ids),
            Score.is_deleted == False
        ).count()
        return {
            "arcades": [{"id": a.id, "nom": a.nom} for a in arcades],
            "active_reservations": active_reservations,
            "playing_reservations": playing_reservations,
            "total_scores": total_scores,
            "timestamp": datetime.utcnow().isoformat()
        }

    active_users = db.query(User).filter(User.is_deleted == False).count()
    total_arcades = db.query(Arcade).filter(Arcade.is_deleted == False).count()
    total_games = db.query(Game).filter(Game.is_deleted == False).count()
    active_promo_codes = db.query(PromoCode).filter(PromoCode.is_deleted == False).count()
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
        _: Admin = Depends(get_current_super_admin)
):
    return soft_delete_arcade_service(db, arcade_id)


@router.get("/arcades/deleted")
async def list_deleted_arcades(
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return list_deleted_arcades_service(db)


@router.put("/arcades/{arcade_id}/restore", responses=ARCADE_NOT_FOUND_RESPONSE)
async def restore_arcade(
        arcade_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
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


# === GESTION DES COMPTES ADMIN ===


@router.get("/admins/")
async def list_admins(
        role: Optional[AdminRole] = None,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Liste les comptes admin. Optionnellement filtrés par rôle."""
    q = db.query(Admin).filter(Admin.is_deleted == False)
    if role is not None:
        q = q.filter(Admin.role == role)
    admins = q.all()
    return [
        {
            "id": a.id,
            "email": a.email,
            "role": a.role.value if hasattr(a.role, "value") else a.role,
            "arcades": [
                {"id": ar.id, "nom": ar.nom}
                for ar in a.arcades if not ar.is_deleted
            ],
            "created_at": a.created_at.isoformat()
        }
        for a in admins
    ]


class InviteArcadeOwnerRequest(BaseModel):
    email: EmailStr
    arcade_id: Optional[int] = None


@router.post("/invitations/", status_code=status.HTTP_201_CREATED)
async def invite_arcade_owner(
        payload: InviteArcadeOwnerRequest,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """
    Invite un propriétaire de borne :
    - Crée son compte Firebase Admin
    - Enregistre l'Admin en base
    - Optionnellement assigne une première borne (peut être fait après depuis la page Propriétaires)
    - Envoie un email d'activation avec lien de création de mot de passe
    """
    arcade = None
    if payload.arcade_id is not None:
        arcade = db.query(Arcade).filter(Arcade.id == payload.arcade_id, Arcade.is_deleted == False).first()
        if not arcade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borne non trouvée")
        if arcade.owner_admin_id is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette borne a déjà un propriétaire")

    existing = db.query(Admin).filter(Admin.email == payload.email, Admin.is_deleted == False).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un compte admin existe déjà pour cet email")

    try:
        firebase_uid = create_firebase_admin_user(payload.email)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Erreur création compte Firebase : {e}")

    admin = Admin(
        firebase_uid=firebase_uid,
        email=payload.email,
        role=AdminRole.arcade_owner,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    if arcade is not None:
        arcade.owner_admin_id = admin.id
        db.commit()

    set_admin_custom_claims(firebase_uid, AdminRole.arcade_owner.value)

    try:
        activation_link = generate_password_reset_link(payload.email)
        send_arcade_owner_invitation(
            to_email=payload.email,
            arcade_name=arcade.nom if arcade else "(à assigner)",
            activation_link=activation_link,
        )
    except Exception as e:
        logger.error("Email d'invitation non envoyé pour %s : %s", payload.email, e)

    return {
        "message": f"Invitation envoyée à {payload.email}",
        "admin_id": admin.id,
        "arcade": arcade.nom if arcade else None,
    }


class InviteSuperAdminRequest(BaseModel):
    email: EmailStr


@router.post("/invitations/super-admin", status_code=status.HTTP_201_CREATED)
async def invite_super_admin(
        payload: InviteSuperAdminRequest,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Invite un nouveau super_admin via email d'activation."""
    existing = db.query(Admin).filter(Admin.email == payload.email, Admin.is_deleted == False).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un compte admin existe déjà pour cet email")

    try:
        firebase_uid = create_firebase_admin_user(payload.email)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Erreur création compte Firebase : {e}")

    admin = Admin(
        firebase_uid=firebase_uid,
        email=payload.email,
        role=AdminRole.super_admin,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    set_admin_custom_claims(firebase_uid, AdminRole.super_admin.value)

    try:
        activation_link = generate_password_reset_link(payload.email)
        send_arcade_owner_invitation(
            to_email=payload.email,
            arcade_name="Équipe RetroNova",
            activation_link=activation_link,
        )
    except Exception as e:
        logger.error("Email d'invitation super_admin non envoyé pour %s : %s", payload.email, e)

    return {
        "message": f"Invitation super_admin envoyée à {payload.email}",
        "admin_id": admin.id,
    }


@router.delete("/admins/{admin_id}", status_code=status.HTTP_200_OK)
async def delete_admin(
        admin_id: int,
        db: Session = Depends(get_db),
        current: Admin = Depends(get_current_super_admin)
):
    """Supprime un compte admin et désassigne ses bornes."""
    admin = db.query(Admin).filter(Admin.id == admin_id, Admin.is_deleted == False).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin non trouvé")
    if admin.id == current.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Impossible de se supprimer soi-même")

    db.query(Arcade).filter(Arcade.owner_admin_id == admin.id).update({Arcade.owner_admin_id: None})

    admin.is_deleted = True
    admin.deleted_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": f"Compte admin {admin.email} supprimé"}


# === GESTION DES PROPRIÉTAIRES (super_admin) ===


@router.get("/owners")
async def list_owners(
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Liste les arcade_owners avec les bornes qui leur sont assignées."""
    owners = db.query(Admin).filter(
        Admin.role == AdminRole.arcade_owner,
        Admin.is_deleted == False
    ).all()
    return [
        {
            "id": owner.id,
            "email": owner.email,
            "created_at": owner.created_at.isoformat(),
            "arcades": [
                {"id": a.id, "nom": a.nom, "localisation": a.localisation}
                for a in owner.arcades if not a.is_deleted
            ],
        }
        for owner in owners
    ]


@router.put("/owners/{admin_id}/arcades/{arcade_id}")
async def assign_arcade_to_owner(
        admin_id: int,
        arcade_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Assigne une borne à un arcade_owner."""
    owner = db.query(Admin).filter(
        Admin.id == admin_id,
        Admin.role == AdminRole.arcade_owner,
        Admin.is_deleted == False
    ).first()
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Propriétaire non trouvé")

    arcade = db.query(Arcade).filter(Arcade.id == arcade_id, Arcade.is_deleted == False).first()
    if not arcade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borne non trouvée")

    if arcade.owner_admin_id is not None and arcade.owner_admin_id != owner.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette borne est déjà assignée à un autre propriétaire")

    arcade.owner_admin_id = owner.id
    db.commit()
    return {"message": f"Borne '{arcade.nom}' assignée à {owner.email}"}


@router.delete("/owners/{admin_id}/arcades/{arcade_id}")
async def unassign_arcade_from_owner(
        admin_id: int,
        arcade_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Désassigne une borne d'un arcade_owner."""
    arcade = db.query(Arcade).filter(
        Arcade.id == arcade_id,
        Arcade.owner_admin_id == admin_id,
        Arcade.is_deleted == False
    ).first()
    if not arcade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignation non trouvée")

    arcade.owner_admin_id = None
    db.commit()
    return {"message": f"Borne '{arcade.nom}' désassignée"}


@router.get("/arcades/unassigned")
async def list_unassigned_arcades(
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Liste les bornes sans propriétaire (pour les assigner)."""
    arcades = db.query(Arcade).filter(
        Arcade.is_deleted == False,
        Arcade.owner_admin_id.is_(None)
    ).order_by(Arcade.nom).all()
    return [
        {"id": a.id, "nom": a.nom, "localisation": a.localisation}
        for a in arcades
    ]


# === DEMANDES DE CRÉATION DE BORNE ===


class CreateArcadeRequestPayload(BaseModel):
    nom: str
    description: Optional[str] = None
    localisation: str
    latitude: float
    longitude: float


class RejectRequestPayload(BaseModel):
    rejection_reason: Optional[str] = None


def _request_to_dict(req: ArcadeCreationRequest) -> dict:
    return {
        "id": req.id,
        "nom": req.nom,
        "description": req.description,
        "localisation": req.localisation,
        "latitude": req.latitude,
        "longitude": req.longitude,
        "status": req.status.value if hasattr(req.status, "value") else req.status,
        "rejection_reason": req.rejection_reason,
        "created_arcade_id": req.created_arcade_id,
        "requester": {
            "id": req.requester.id,
            "email": req.requester.email,
        } if req.requester else None,
        "reviewer": {
            "id": req.reviewer.id,
            "email": req.reviewer.email,
        } if req.reviewer else None,
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


@router.post("/arcade-requests/", status_code=status.HTTP_201_CREATED)
async def submit_arcade_request(
        payload: CreateArcadeRequestPayload,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Soumet une demande de création de borne (arcade_owner)."""
    if current_admin.role != AdminRole.arcade_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seul un arcade_owner peut soumettre une demande. Un super_admin doit créer la borne directement."
        )

    req = ArcadeCreationRequest(
        requested_by_admin_id=current_admin.id,
        nom=payload.nom,
        description=payload.description,
        localisation=payload.localisation,
        latitude=payload.latitude,
        longitude=payload.longitude,
        status=ArcadeRequestStatus.pending,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"message": "Demande envoyée", "request_id": req.id}


@router.get("/arcade-requests/")
async def list_arcade_requests(
        status_filter: Optional[ArcadeRequestStatus] = None,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_arcade_owner)
):
    """Liste les demandes. super_admin voit tout, arcade_owner voit ses propres demandes."""
    q = db.query(ArcadeCreationRequest).filter(ArcadeCreationRequest.is_deleted == False)
    if current_admin.role == AdminRole.arcade_owner:
        q = q.filter(ArcadeCreationRequest.requested_by_admin_id == current_admin.id)
    if status_filter is not None:
        q = q.filter(ArcadeCreationRequest.status == status_filter)
    requests = q.order_by(ArcadeCreationRequest.created_at.desc()).all()
    return [_request_to_dict(r) for r in requests]


@router.get("/arcade-requests/pending-count")
async def pending_arcade_requests_count(
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    """Compteur de demandes en attente (badge sidebar super_admin)."""
    count = db.query(ArcadeCreationRequest).filter(
        ArcadeCreationRequest.is_deleted == False,
        ArcadeCreationRequest.status == ArcadeRequestStatus.pending
    ).count()
    return {"count": count}


@router.post("/arcade-requests/{request_id}/approve")
async def approve_arcade_request(
        request_id: int,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_super_admin)
):
    """Approuve une demande : crée la borne et l'assigne au demandeur."""
    req = db.query(ArcadeCreationRequest).filter(
        ArcadeCreationRequest.id == request_id,
        ArcadeCreationRequest.is_deleted == False
    ).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande non trouvée")
    if req.status != ArcadeRequestStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette demande a déjà été traitée")

    import secrets
    api_key = f"arcade_key_{secrets.token_urlsafe(16)}"
    arcade = Arcade(
        nom=req.nom,
        description=req.description,
        api_key=api_key,
        localisation=req.localisation,
        latitude=req.latitude,
        longitude=req.longitude,
        owner_admin_id=req.requested_by_admin_id,
    )
    db.add(arcade)
    db.flush()

    req.status = ArcadeRequestStatus.approved
    req.created_arcade_id = arcade.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.reviewed_by_admin_id = current_admin.id
    db.commit()
    db.refresh(req)

    return {"message": "Demande approuvée et borne créée", "arcade_id": arcade.id, "request_id": req.id}


@router.post("/arcade-requests/{request_id}/reject")
async def reject_arcade_request(
        request_id: int,
        payload: RejectRequestPayload,
        db: Session = Depends(get_db),
        current_admin: Admin = Depends(get_current_super_admin)
):
    """Rejette une demande (avec motif optionnel)."""
    req = db.query(ArcadeCreationRequest).filter(
        ArcadeCreationRequest.id == request_id,
        ArcadeCreationRequest.is_deleted == False
    ).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande non trouvée")
    if req.status != ArcadeRequestStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette demande a déjà été traitée")

    req.status = ArcadeRequestStatus.rejected
    req.rejection_reason = payload.rejection_reason
    req.reviewed_at = datetime.now(timezone.utc)
    req.reviewed_by_admin_id = current_admin.id
    db.commit()
    db.refresh(req)

    return {"message": "Demande rejetée", "request_id": req.id}


@router.put("/arcades/{arcade_id}/regenerate-api-key")
async def regenerate_arcade_api_key(
        arcade_id: int,
        db: Session = Depends(get_db),
        _: Admin = Depends(get_current_super_admin)
):
    return regenerate_arcade_api_key_service(db, arcade_id)