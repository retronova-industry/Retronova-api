from typing import Annotated, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserSearchResponse, UserUpdate
from app.services.user_service import (
    delete_my_account_service,
    get_my_profile_service,
    search_users_service,
    update_my_profile_service,
)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: Annotated[User, Depends(get_current_user)]
):
    return get_my_profile_service(current_user)


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    user_update: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return update_my_profile_service(db, current_user, user_update)


@router.delete("/me")
async def delete_my_account(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return delete_my_account_service(db, current_user)


@router.get("/search", response_model=List[UserSearchResponse])
async def search_users(
    q: Annotated[str, Query(min_length=2, description="Terme de recherche (pseudo, nom, prénom)")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(le=50)] = 10,
):
    return search_users_service(db, current_user, q, limit)