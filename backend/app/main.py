from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .catalog import list_catalog
from .config import Settings, get_settings
from .database import Database
from .email_service import EmailService
from .models import CheckoutRequest
from .orders import normalize_order
from .stripe_service import StripeService


settings = get_settings()
db = Database(settings.database_file)
db.init()
email_service = EmailService(settings, db)
stripe_service = StripeService(settings)

app = FastAPI(title="Noesis del Caribe API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


def require_admin(authorization: str = Header(default="")) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN no está configurado.")
    expected = f"Bearer {settings.admin_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="No autorizado.")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "env": settings.app_env}


@app.get("/api/catalog")
def catalog() -> list[dict]:
    return list_catalog()


@app.post("/api/payments/checkout-session")
def create_checkout_session(payload: CheckoutRequest) -> dict:
    stripe_service.ensure_configured()
    order = normalize_order(payload.order)
    db.upsert_order(order)
    checkout = stripe_service.create_checkout_session(order)
    db.set_checkout_session(order["id"], checkout["id"])
    return {"orderId": order["id"], "sessionId": checkout["id"], "url": checkout["url"]}


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(default="", alias="Stripe-Signature")) -> dict:
    payload = await request.body()
    event = stripe_service.construct_event(payload, stripe_signature)
    event_id = event["id"]
    event_type = event["type"]

    if db.event_seen(event_id):
        return {"received": True, "duplicate": True}

    db.record_event(event_id, event_type, payload.decode("utf-8", errors="replace"))

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id") or session.get("client_reference_id")
        if not order_id:
            raise HTTPException(status_code=400, detail="Webhook sin order_id.")
        paid_order = db.mark_paid(order_id, session.get("id"), session.get("payment_intent"))
        if paid_order:
            email_service.send_order_paid(paid_order)

    return {"received": True}


@app.get("/api/admin/orders", dependencies=[Depends(require_admin)])
def admin_orders() -> list[dict]:
    return db.list_orders()


@app.post("/api/dev/mark-paid/{order_id}", dependencies=[Depends(require_admin)])
def dev_mark_paid(order_id: str) -> dict:
    if settings.app_env == "production":
        raise HTTPException(status_code=403, detail="Endpoint disponible solo fuera de producción.")
    paid_order = db.mark_paid(order_id, None, None)
    if not paid_order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    email_service.send_order_paid(paid_order)
    return paid_order


ROOT = settings.root_dir

app.mount("/css", StaticFiles(directory=ROOT / "css"), name="css")
app.mount("/js", StaticFiles(directory=ROOT / "js"), name="js")
app.mount("/pages", StaticFiles(directory=ROOT / "pages"), name="pages")
app.mount("/docs", StaticFiles(directory=ROOT / "docs"), name="docs")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/index.html")
def index_html() -> FileResponse:
    return FileResponse(ROOT / "index.html")
