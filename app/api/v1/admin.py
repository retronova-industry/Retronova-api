from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.core.messages import (
    ARCADE_NOT_FOUND,
    GAME_NOT_FOUND,
    PROMO_CODE_NOT_FOUND,
    USER_NOT_FOUND,
)
from app.schemas.admin import (
    ArcadeGameAssignmentRequest,
    CreateArcadeRequest,
    CreateGameRequest,
    CreatePromoCodeRequest,
    UpdatePromoCodeRequest,
    UpdateUserTicketsRequest,
)
from app.services.admin_service import (
    assign_game_to_arcade_service,
    create_arcade_service,
    create_game_service,
    create_promo_code_service,
    force_cancel_user_reservations_service,
    get_admin_stats_service,
    get_expiring_promo_codes_service,
    get_user_deletion_impact_service,
    list_deleted_arcades_service,
    list_deleted_users_service,
    list_promo_codes_service,
    regenerate_arcade_api_key_service,
    restore_arcade_service,
    restore_user_service,
    soft_delete_arcade_service,
    soft_delete_game_service,
    soft_delete_user_service,
    toggle_promo_code_active_service,
    update_arcade_service,
    update_promo_code_service,
    update_user_tickets_service,
)

router = APIRouter(
    dependencies=[Depends(get_current_admin)]
)

ARCADE_NOT_FOUND_RESPONSE = {
    404: {"description": ARCADE_NOT_FOUND}
}

GAME_NOT_FOUND_RESPONSE = {
    404: {"description": GAME_NOT_FOUND}
}

PROMO_CODE_NOT_FOUND_RESPONSE = {
    404: {"description": PROMO_CODE_NOT_FOUND}
}

USER_NOT_FOUND_RESPONSE = {
    404: {"description": USER_NOT_FOUND}
}


@router.post("/arcades/")
async def create_arcade(
    arcade_data: CreateArcadeRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return create_arcade_service(db, arcade_data)


@router.put("/arcades/{arcade_id}", responses=ARCADE_NOT_FOUND_RESPONSE)
async def update_arcade(
    arcade_id: int,
    arcade_data: CreateArcadeRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return update_arcade_service(db, arcade_id, arcade_data)


@router.put(
    "/arcades/{arcade_id}/games",
    responses={
        **ARCADE_NOT_FOUND_RESPONSE,
        **GAME_NOT_FOUND_RESPONSE,
    },
)
async def assign_game_to_arcade(
    arcade_id: int,
    assignment: ArcadeGameAssignmentRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return assign_game_to_arcade_service(db, arcade_id, assignment)


@router.post("/games/")
async def create_game(
    game_data: CreateGameRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return create_game_service(db, game_data)


@router.delete("/games/{game_id}")
async def soft_delete_game(
    game_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return soft_delete_game_service(db, game_id)


@router.post("/promo-codes/")
async def create_promo_code(
    promo_data: CreatePromoCodeRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return create_promo_code_service(db, promo_data)


@router.put("/promo-codes/{promo_code_id}", responses=PROMO_CODE_NOT_FOUND_RESPONSE)
async def update_promo_code(
    promo_code_id: int,
    update_data: UpdatePromoCodeRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return update_promo_code_service(db, promo_code_id, update_data)


@router.get("/promo-codes/")
async def list_promo_codes(
    db: Annotated[Session, Depends(get_db)],
    include_expired: bool = False,
):
    return list_promo_codes_service(db, include_expired)


@router.post(
    "/promo-codes/{promo_code_id}/toggle-active",
    responses=PROMO_CODE_NOT_FOUND_RESPONSE,
)
async def toggle_promo_code_active(
    promo_code_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return toggle_promo_code_active_service(db, promo_code_id)


@router.get("/promo-codes/expiring-soon")
async def get_expiring_promo_codes(
    db: Annotated[Session, Depends(get_db)],
    days_ahead: Annotated[int, Query(ge=1)] = 7,
):
    return get_expiring_promo_codes_service(db, days_ahead)


@router.put("/users/tickets", responses=USER_NOT_FOUND_RESPONSE)
async def update_user_tickets(
    update_data: UpdateUserTicketsRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return update_user_tickets_service(db, update_data)


@router.get("/users/deleted")
async def list_deleted_users(
    db: Annotated[Session, Depends(get_db)],
):
    return list_deleted_users_service(db)


@router.put("/users/{user_id}/restore", responses=USER_NOT_FOUND_RESPONSE)
async def restore_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return restore_user_service(db, user_id)


@router.delete("/users/{user_id}", responses=USER_NOT_FOUND_RESPONSE)
async def soft_delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return soft_delete_user_service(db, user_id)


@router.get("/users/{user_id}/deletion-impact", responses=USER_NOT_FOUND_RESPONSE)
async def get_user_deletion_impact(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return get_user_deletion_impact_service(db, user_id)


@router.put(
    "/users/{user_id}/force-cancel-reservations",
    responses=USER_NOT_FOUND_RESPONSE,
)
async def force_cancel_user_reservations(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return force_cancel_user_reservations_service(db, user_id)


@router.get("/stats")
async def get_admin_stats(
    db: Annotated[Session, Depends(get_db)],
):
    return get_admin_stats_service(db)


@router.delete("/arcades/{arcade_id}", responses=ARCADE_NOT_FOUND_RESPONSE)
async def soft_delete_arcade(
    arcade_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return soft_delete_arcade_service(db, arcade_id)


@router.get("/arcades/deleted")
async def list_deleted_arcades(
    db: Annotated[Session, Depends(get_db)],
):
    return list_deleted_arcades_service(db)


@router.put("/arcades/{arcade_id}/restore", responses=ARCADE_NOT_FOUND_RESPONSE)
async def restore_arcade(
    arcade_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return restore_arcade_service(db, arcade_id)


@router.put(
    "/arcades/{arcade_id}/regenerate-api-key",
    responses=ARCADE_NOT_FOUND_RESPONSE,
)
async def regenerate_arcade_api_key(
    arcade_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    return regenerate_arcade_api_key_service(db, arcade_id)