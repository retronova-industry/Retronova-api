from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.messages import (
    ALREADY_FRIENDS,
    FRIEND_REQUEST_ALREADY_EXISTS,
    USER_NOT_FOUND
)
from app.models.user import User
from app.models.friend import Friendship, FriendshipStatus
from app.schemas.friend import FriendRequestCreate


def get_my_friends_service(db: Session, current_user: User) -> list[User]:
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
        friend = (
            friendship.requested
            if friendship.requester_id == current_user.id
            else friendship.requester
        )
        friends.append(friend)

    return friends


def get_friend_requests_service(db: Session, current_user: User) -> list[Friendship]:
    """Récupère les demandes d'amis reçues en attente."""

    requests = db.query(Friendship).filter(
        and_(
            Friendship.requested_id == current_user.id,
            Friendship.status == FriendshipStatus.PENDING,
            Friendship.is_deleted == False
        )
    ).all()

    return requests


def send_friend_request_service(
    db: Session,
    current_user: User,
    request_data: FriendRequestCreate
) -> dict:
    """Envoie une demande d'ami."""

    if request_data.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas vous ajouter vous-même"
        )

    target_user = db.query(User).filter(
        User.id == request_data.user_id,
        User.is_deleted == False
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND
        )

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
        if existing_friendship.status == FriendshipStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=FRIEND_REQUEST_ALREADY_EXISTS
            )

    friendship = Friendship(
        requester_id=current_user.id,
        requested_id=request_data.user_id
    )
    db.add(friendship)
    db.commit()

    return {"message": "Demande d'ami envoyée"}


def accept_friend_request_service(
    db: Session,
    current_user: User,
    friendship_id: int
) -> dict:
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


def reject_friend_request_service(
    db: Session,
    current_user: User,
    friendship_id: int
) -> dict:
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


def remove_friend_service(
    db: Session,
    current_user: User,
    user_id: int
) -> dict:
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

    friendship.is_deleted = True
    db.commit()

    return {"message": "Ami retiré de votre liste"}