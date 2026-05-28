from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.messages import INVALID_PROMO_CODE
from app.models.promo import PromoCode, PromoUse
from app.models.user import User
from app.schemas.promo import (
    AvailablePromoCodeResponse,
    PromoHistoryItemResponse,
    UsePromoCodeRequest,
    UsePromoCodeResponse,
)


class PromoService:
    def __init__(self, db: Session):
        self.db = db

    def use_promo_code(self, current_user: User, promo_data: UsePromoCodeRequest) -> UsePromoCodeResponse:
        promo_code = self.db.query(PromoCode).filter(
            PromoCode.code == promo_data.code.upper().strip(),
            PromoCode.is_deleted == False
        ).first()

        if not promo_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=INVALID_PROMO_CODE
            )

        if not promo_code.is_valid_now():
            if promo_code.is_expired():
                raise HTTPException(status_code=400, detail="Ce code promo a expiré")
            elif not promo_code.is_active:
                raise HTTPException(status_code=400, detail="Ce code promo n'est plus actif")
            else:
                raise HTTPException(status_code=400, detail="Ce code promo n'est pas encore valide")

        if promo_code.is_single_use_per_user:
            existing_use = self.db.query(PromoUse).filter(
                PromoUse.user_id == current_user.id,
                PromoUse.promo_code_id == promo_code.id,
                PromoUse.is_deleted == False
            ).first()

            if existing_use:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vous avez déjà utilisé ce code promo"
                )

        if promo_code.usage_limit and promo_code.current_uses >= promo_code.usage_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce code promo a atteint sa limite d'utilisation"
            )

        if promo_code.is_single_use_global and promo_code.current_uses > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce code promo a déjà été utilisé"
            )

        promo_use = PromoUse(
            user_id=current_user.id,
            promo_code_id=promo_code.id,
            tickets_received=promo_code.tickets_reward
        )

        current_user.tickets_balance += promo_code.tickets_reward
        promo_code.current_uses += 1

        self.db.add(promo_use)
        self.db.commit()

        return UsePromoCodeResponse(
            tickets_received=promo_code.tickets_reward,
            new_balance=current_user.tickets_balance,
            message=f"Code promo utilisé avec succès ! Vous avez reçu {promo_code.tickets_reward} tickets."
        )

    def get_promo_history(self, current_user: User):
        promo_uses = self.db.query(PromoUse).join(
            PromoCode, PromoUse.promo_code_id == PromoCode.id
        ).filter(
            PromoUse.user_id == current_user.id,
            PromoUse.is_deleted == False
        ).order_by(
            PromoUse.created_at.desc(),
            PromoUse.id.desc()
        ).all()

        return [
            PromoHistoryItemResponse(
                id=promo_use.id,
                code=promo_use.promo_code.code,
                tickets_received=promo_use.tickets_received,
                used_at=promo_use.created_at.isoformat()
            )
            for promo_use in promo_uses
        ]

    def get_available_promo_codes(self, current_user: User):
        now = datetime.now(timezone.utc)

        available_codes = self.db.query(PromoCode).filter(
            PromoCode.is_deleted == False,
            PromoCode.is_active == True,
            (PromoCode.valid_from.is_(None) | (PromoCode.valid_from <= now)),
            (PromoCode.valid_until.is_(None) | (PromoCode.valid_until > now)),
            (PromoCode.usage_limit.is_(None) | (PromoCode.current_uses < PromoCode.usage_limit))
        ).all()

        result = []
        for code in available_codes:
            if code.is_single_use_per_user:
                existing_use = self.db.query(PromoUse).filter(
                    PromoUse.user_id == current_user.id,
                    PromoUse.promo_code_id == code.id,
                    PromoUse.is_deleted == False
                ).first()

                if existing_use:
                    continue

            result.append(
                AvailablePromoCodeResponse(
                    id=code.id,
                    tickets_reward=code.tickets_reward,
                    usage_limit=code.usage_limit,
                    current_uses=code.current_uses,
                    valid_until=code.valid_until.isoformat() if code.valid_until else None,
                    days_until_expiry=code.days_until_expiry()
                )
            )

        return result