from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.promo import (
    AvailablePromoCodeResponse,
    PromoHistoryItemResponse,
    UsePromoCodeRequest,
    UsePromoCodeResponse,
)
from app.services.promo_service import PromoService

router = APIRouter()


@router.post("/use", response_model=UsePromoCodeResponse)
async def use_promo_code(
    promo_data: UsePromoCodeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    service = PromoService(db)
    return service.use_promo_code(current_user, promo_data)


@router.get("/history", response_model=list[PromoHistoryItemResponse])
async def get_promo_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    service = PromoService(db)
    return service.get_promo_history(current_user)


@router.get("/available", response_model=list[AvailablePromoCodeResponse])
async def get_available_promo_codes(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    service = PromoService(db)
    return service.get_available_promo_codes(current_user)