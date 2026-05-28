from pydantic import BaseModel
from app.models.friend import FriendshipStatus
from app.schemas.user import UserSearchResponse


class FriendRequestCreate(BaseModel):
    user_id: int


class FriendshipResponse(BaseModel):
    id: int
    status: FriendshipStatus
    requester: UserSearchResponse
    requested: UserSearchResponse

    class Config:
        from_attributes = True