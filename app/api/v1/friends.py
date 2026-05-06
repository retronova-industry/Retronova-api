from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.friend import FriendRequestCreate, FriendshipResponse
from app.schemas.user import UserSearchResponse
from app.services.friend_service import (
    accept_friend_request_service,
    get_friend_requests_service,
    get_my_friends_service,
    reject_friend_request_service,
    remove_friend_service,
    send_friend_request_service,
)

router = APIRouter()


@router.get("/", response_model=List[UserSearchResponse])
async def get_my_friends(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return get_my_friends_service(db, current_user)


@router.get("/requests", response_model=List[FriendshipResponse])
async def get_friend_requests(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return get_friend_requests_service(db, current_user)


@router.post("/request")
async def send_friend_request(
    request_data: FriendRequestCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return send_friend_request_service(db, current_user, request_data)


@router.put("/request/{friendship_id}/accept")
async def accept_friend_request(
    friendship_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return accept_friend_request_service(db, current_user, friendship_id)


@router.put("/request/{friendship_id}/reject")
async def reject_friend_request(
    friendship_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return reject_friend_request_service(db, current_user, friendship_id)


@router.delete("/{user_id}")
async def remove_friend(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return remove_friend_service(db, current_user, user_id)