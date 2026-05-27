from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.ticket import PaymentConfigResponse
from app.services.ticket_service import (
    get_payment_config_service,
    handle_stripe_webhook_service,
)

router = APIRouter()


@router.get("/config", response_model=PaymentConfigResponse)
async def get_payment_config():
    return get_payment_config_service()


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
):
    payload = await request.body()
    return handle_stripe_webhook_service(db, payload, stripe_signature)
