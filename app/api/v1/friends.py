from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Annotated, List
from app.core.database import get_db
from app.core.messages import ALREADY_FRIENDS, FRIEND_REQUEST_ALREADY_EXISTS, USER_NOT_FOUND
from app.models.user import User
from app.models.friend import Friendship, FriendshipStatus
from app.schemas.user import UserSearchResponse
from app.api.deps import get_current_user
from app.schemas.friend import FriendRequestCreate, FriendshipResponse

router = APIRouter()

@router.get("/", response_model=List[UserSearchResponse])
async def get_my_friends(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère la liste des amis acceptés."""

    friendships = db.query(Friendship).filter(
        and_(
            or_(
                Friendship.requester_id == current_user.id,
                Friendship.requested_id == current_user.id
            ),
            Friendship.status == FriendshipStatus.ACCEPTED,
            Friendship.is_deleted == False
        )
    ).all()

    friends = []
    for friendship in friendships:
        friend = friendship.requested if friendship.requester_id == current_user.id else friendship.requester
        friends.append(friend)

    return friends


@router.get("/requests", response_model=List[FriendshipResponse])
async def get_friend_requests(
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère les demandes d'amis reçues en attente."""

    requests = db.query(Friendship).filter(
        and_(
            Friendship.requested_id == current_user.id,
            Friendship.status == FriendshipStatus.PENDING,
            Friendship.is_deleted == False
        )
    ).all()

    return requests


@router.post("/request")
async def send_friend_request(
        request_data: FriendRequestCreate,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Envoie une demande d'ami."""

    if request_data.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas vous ajouter vous-même"
        )

    # Vérifier que l'utilisateur cible existe
    target_user = db.query(User).filter(
        User.id == request_data.user_id,
        User.is_deleted == False
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND
        )

    # Vérifier qu'il n'y a pas déjà une relation
    existing_friendship = db.query(Friendship).filter(
        or_(
            and_(
                Friendship.requester_id == current_user.id,
                Friendship.requested_id == request_data.user_id
            ),
            and_(
                Friendship.requester_id == request_data.user_id,
                Friendship.requested_id == current_user.id
            )
        ),
        Friendship.is_deleted == False
    ).first()

    if existing_friendship:
        if existing_friendship.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ALREADY_FRIENDS
            )
        elif existing_friendship.status == FriendshipStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=FRIEND_REQUEST_ALREADY_EXISTS
            )

    # Créer la demande d'ami
    friendship = Friendship(
        requester_id=current_user.id,
        requested_id=request_data.user_id
    )
    db.add(friendship)
    db.commit()

    return {"message": "Demande d'ami envoyée"}


@router.put("/request/{friendship_id}/accept")
async def accept_friend_request(
        friendship_id: int,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Accepte une demande d'ami."""

    friendship = db.query(Friendship).filter(
        Friendship.id == friendship_id,
        Friendship.requested_id == current_user.id,
        Friendship.status == FriendshipStatus.PENDING,
        Friendship.is_deleted == False
    ).first()

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande d'ami non trouvée"
        )

    friendship.status = FriendshipStatus.ACCEPTED
    db.commit()

    return {"message": "Demande d'ami acceptée"}


@router.put("/request/{friendship_id}/reject")
async def reject_friend_request(
        friendship_id: int,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Rejette une demande d'ami."""

    friendship = db.query(Friendship).filter(
        Friendship.id == friendship_id,
        Friendship.requested_id == current_user.id,
        Friendship.status == FriendshipStatus.PENDING,
        Friendship.is_deleted == False
    ).first()

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande d'ami non trouvée"
        )

    friendship.status = FriendshipStatus.REJECTED
    db.commit()

    return {"message": "Demande d'ami rejetée"}


@router.delete("/{user_id}")
async def remove_friend(
        user_id: int,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Retire un ami de sa liste."""

    friendship = db.query(Friendship).filter(
        or_(
            and_(
                Friendship.requester_id == current_user.id,
                Friendship.requested_id == user_id
            ),
            and_(
                Friendship.requester_id == user_id,
                Friendship.requested_id == current_user.id
            )
        ),
        Friendship.status == FriendshipStatus.ACCEPTED,
        Friendship.is_deleted == False
    ).first()

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amitié non trouvée"
        )

    # Soft delete
    friendship.is_deleted = True
    db.commit()

    return {"message": "Ami retiré de votre liste"}