import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.config import settings
from openclaw_api.deps import get_current_customer_id, get_db
from openclaw_api.models import Customer
from openclaw_api.schemas import BillingPortalResponse

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/portal-session", response_model=BillingPortalResponse)
async def create_portal_session(
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Customer has no billing account")

    stripe.api_key = settings.stripe_secret_key
    session = stripe.billing_portal.Session.create(
        customer=customer.stripe_customer_id,
        return_url=settings.cors_origins.split(",")[0],
    )

    return BillingPortalResponse(url=session.url)


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        stripe.api_key = settings.stripe_secret_key
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Event received successfully; processing handled by billing-worker
    return {"status": "ok", "type": event["type"]}
