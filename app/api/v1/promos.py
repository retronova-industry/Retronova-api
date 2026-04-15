from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.messages import INVALID_PROMO_CODE
from app.models.user import User
from app.models.promo import PromoCode, PromoUse
from app.api.deps import get_current_user
from app.schemas.promo import (
    AvailablePromoCodeResponse,
    PromoHistoryItemResponse,
    UsePromoCodeRequest,
    UsePromoCodeResponse,
)

router = APIRouter()

@router.post("/use", response_model=UsePromoCodeResponse)
async def use_promo_code(
        promo_data: UsePromoCodeRequest,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Utilise un code promo pour obtenir des tickets."""

    # Rechercher le code promo
    promo_code = db.query(PromoCode).filter(
        PromoCode.code == promo_data.code.upper().strip(),
        PromoCode.is_deleted == False
    ).first()

    if not promo_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=INVALID_PROMO_CODE
        )

    # Vérifier la validité du code (dates + activation)
    if not promo_code.is_valid_now():
        if promo_code.is_expired():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce code promo a expiré"
            )
        elif not promo_code.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce code promo n'est plus actif"
            )
        else:
            # Code pas encore valide (valid_from dans le futur)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce code promo n'est pas encore valide"
            )

    # Vérifier si l'utilisateur a déjà utilisé ce code
    if promo_code.is_single_use_per_user:
        existing_use = db.query(PromoUse).filter(
            PromoUse.user_id == current_user.id,
            PromoUse.promo_code_id == promo_code.id,
            PromoUse.is_deleted == False
        ).first()

        if existing_use:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous avez déjà utilisé ce code promo"
            )

    # Vérifier la limite globale d'utilisation
    if promo_code.usage_limit and promo_code.current_uses >= promo_code.usage_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce code promo a atteint sa limite d'utilisation"
        )

    # Vérifier si c'est un code à usage unique global
    if promo_code.is_single_use_global and promo_code.current_uses > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce code promo a déjà été utilisé"
        )

    # Utiliser le code promo
    promo_use = PromoUse(
        user_id=current_user.id,
        promo_code_id=promo_code.id,
        tickets_received=promo_code.tickets_reward
    )

    # Créditer les tickets à l'utilisateur
    current_user.tickets_balance += promo_code.tickets_reward

    # Incrémenter le compteur d'utilisations
    promo_code.current_uses += 1

    db.add(promo_use)
    db.commit()

    return UsePromoCodeResponse(
        tickets_received=promo_code.tickets_reward,
        new_balance=current_user.tickets_balance,
        message=f"Code promo utilisé avec succès ! Vous avez reçu {promo_code.tickets_reward} tickets."
    )


@router.get("/history", response_model=list[PromoHistoryItemResponse])
async def get_promo_history(
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère l'historique des codes promo utilisés par l'utilisateur."""

    promo_uses = db.query(PromoUse).join(
        PromoCode, PromoUse.promo_code_id == PromoCode.id
    ).filter(
        PromoUse.user_id == current_user.id,
        PromoUse.is_deleted == False
    ).order_by(PromoUse.created_at.desc()).all()

    history = []
    for promo_use in promo_uses:
        history.append({
            "id": promo_use.id,
            "code": promo_use.promo_code.code,
            "tickets_received": promo_use.tickets_received,
            "used_at": promo_use.created_at.isoformat()
        })

    return history


@router.get("/available", response_model=list[AvailablePromoCodeResponse])
async def get_available_promo_codes(
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère les codes promo disponibles pour l'utilisateur (non sensible)."""

    # Cette route pourrait être utilisée pour afficher des codes publics
    # ou des indices sur les codes disponibles
    now = datetime.now(timezone.utc)

    available_codes = db.query(PromoCode).filter(
        PromoCode.is_deleted == False,
        PromoCode.is_active == True,
        # Codes actuellement valides
        (PromoCode.valid_from.is_(None) | (PromoCode.valid_from <= now)),
        (PromoCode.valid_until.is_(None) | (PromoCode.valid_until > now)),
        # Codes qui ont encore des utilisations disponibles
        (PromoCode.usage_limit.is_(None) | (PromoCode.current_uses < PromoCode.usage_limit))
    ).all()

    # Filtrer ceux déjà utilisés par l'utilisateur si single_use_per_user
    result = []
    for code in available_codes:
        if code.is_single_use_per_user:
            existing_use = db.query(PromoUse).filter(
                PromoUse.user_id == current_user.id,
                PromoUse.promo_code_id == code.id,
                PromoUse.is_deleted == False
            ).first()

            if existing_use:
                continue  # Skip ce code, déjà utilisé

        # Ne pas révéler le code exact, juste des infos générales
        result.append({
            "id": code.id,
            "tickets_reward": code.tickets_reward,
            "usage_limit": code.usage_limit,
            "current_uses": code.current_uses,
            "valid_until": code.valid_until.isoformat() if code.valid_until else None,
            "days_until_expiry": code.days_until_expiry()
        })

    return result