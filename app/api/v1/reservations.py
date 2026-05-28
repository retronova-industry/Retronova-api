from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import verify_arcade_key
from app.core.database import get_db
from app.models.user import User
from app.schemas.reservation import (
    CreateReservationRequest,
    ReservationResponse,
    UpdateReservationStatusRequest,
)
from app.services.reservation_service import (
    cancel_reservation_service,
    create_reservation_service,
    get_my_reservations_service,
    get_reservation_service,
    get_reservation_status_service,
    update_reservation_status_service,
)

router = APIRouter()


@router.post("/", response_model=ReservationResponse)
async def create_reservation(
    reservation_data: CreateReservationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return create_reservation_service(db, current_user, reservation_data)


@router.get("/", response_model=List[ReservationResponse])
async def get_my_reservations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return get_my_reservations_service(db, current_user)


@router.get("/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return get_reservation_service(db, current_user, reservation_id)


@router.delete("/{reservation_id}")
async def cancel_reservation(
    reservation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return cancel_reservation_service(db, current_user, reservation_id)


@router.put("/{reservation_id}/status")
async def update_reservation_status(
    reservation_id: int,
    status_data: UpdateReservationStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(verify_arcade_key)]
):
    return update_reservation_status_service(db, reservation_id, status_data)


@router.get("/{reservation_id}/status")
async def get_reservation_status(
    reservation_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(verify_arcade_key)]
):
    return get_reservation_status_service(db, reservation_id)