from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Annotated, List

from app.core.security import verify_arcade_key
from app.core.database import get_db
from app.schemas.arcade import ArcadeResponse, QueueItemResponse
from app.services.arcades_service import ArcadeService

router = APIRouter()


@router.get("/", response_model=List[ArcadeResponse])
async def get_arcades(
    db: Annotated[Session, Depends(get_db)]
):
    service = ArcadeService(db)
    return service.get_all_arcades()


@router.get("/{arcade_id}", response_model=ArcadeResponse)
async def get_arcade(
    arcade_id: int,
    db: Annotated[Session, Depends(get_db)]
):
    service = ArcadeService(db)
    return service.get_arcade_details(arcade_id)


@router.get("/{arcade_id}/queue", response_model=List[QueueItemResponse])
async def get_arcade_queue(
    arcade_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(verify_arcade_key)]
):
    service = ArcadeService(db)
    return service.get_arcade_queue(arcade_id)


@router.get("/{arcade_id}/config")
async def get_arcade_config(
    arcade_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(verify_arcade_key)]
):
    service = ArcadeService(db)
    return service.get_arcade_config(arcade_id)