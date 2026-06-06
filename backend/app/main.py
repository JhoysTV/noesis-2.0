from __future__ import annotations

import json
import secrets
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .catalog import list_catalog
from .config import Settings, get_settings
from .database import Database
from .email_service import EmailService
from .models import CheckoutFromToken, CheckoutRequest, QuoteCreate, StatusUpdate, SubmitRequest
from .orders import normalize_order
from .stripe_service import StripeService


settings = get_settings()
db = Database(settings.database_file)
db.init()
email_service = EmailService(settings, db)
stripe_service = StripeService(settings)

UPLOADS_DIR = settings.database_file.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Noesis del Caribe API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Auth helpers ─────────────────────────────────────────────────────────────

def require_admin(authorization: str = Header(default="")) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN no está configurado.")
    expected = f"Bearer {settings.admin_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="No autorizado.")


# ── Health & Catalog ─────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "env": settings.app_env}


@app.get("/api/catalog")
def catalog() -> list[dict]:
    return list_catalog()


# ── Public: Submit new request ───────────────────────────────────────────────

@app.post("/api/orders/submit")
async def submit_order(
    order_data: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> dict:
    """
    Client submits a new project request with optional reference photos.
    Creates order with status 'recibido' and notifies the studio.
    """
    try:
        payload = SubmitRequest.model_validate_json(order_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    order_id = f"NOE-{uuid.uuid4().hex[:8].upper()}"
    client_token = secrets.token_urlsafe(24)

    order = {
        "id": order_id,
        "status": "recibido",
        "clientToken": client_token,
        "createdAt": _utcnow(),
        "paidAt": None,
        "stripeSessionId": None,
        "stripePaymentIntent": None,
        "customer": payload.customer.model_dump(),
        "projectType": payload.projectType,
        "area": payload.area,
        "requirements": payload.requirements,
        "budget": payload.budget,
        "photoNotes": payload.photoNotes,
        "items": [item.model_dump() for item in payload.items],
        "total": payload.total,
    }

    db.upsert_order(order)

    # Persist uploaded reference photos
    saved_photos: list[dict] = []
    for upload in files:
        if upload.filename:
            ext = Path(upload.filename).suffix.lower()
            stored = f"{order_id}_{uuid.uuid4().hex[:8]}{ext}"
            dest = UPLOADS_DIR / stored
            content = await upload.read()
            dest.write_bytes(content)
            record = db.save_upload(order_id, "client_photo", upload.filename, stored, len(content))
            saved_photos.append(record)

    # Email notifications
    email_service.send_request_received(order, saved_photos)

    return {
        "orderId": order_id,
        "clientToken": client_token,
        "message": "Solicitud recibida. Te enviaremos la cotización por correo en 24–48 horas.",
    }


# ── Public: Client order status ───────────────────────────────────────────────

@app.get("/api/order/{token}")
def get_order_by_token(token: str) -> dict:
    """Client accesses their order status using a secure token from the email."""
    order = db.find_order_by_token(token)
    if not order:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    order_id = order["id"]
    uploads = db.list_uploads(order_id, "delivery")
    quote = db.get_latest_quote(order_id)

    return {
        "order": order,
        "quote": quote,
        "deliveryFiles": uploads,
    }


# ── Public: Stripe checkout from client token ─────────────────────────────────

@app.post("/api/order/checkout")
def checkout_from_token(payload: CheckoutFromToken) -> dict:
    """Client initiates Stripe payment using their secure token."""
    stripe_service.ensure_configured()
    order = db.find_order_by_token(payload.token)
    if not order:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if order["status"] not in ("cotizado",):
        raise HTTPException(status_code=400, detail="El pedido no está en estado de pago.")

    checkout = stripe_service.create_checkout_session(order, client_token=payload.token)
    db.set_checkout_session(order["id"], checkout["id"])
    return {"sessionId": checkout["id"], "url": checkout["url"]}


# ── Stripe checkout (legacy — direct from cart) ───────────────────────────────

@app.post("/api/payments/checkout-session")
def create_checkout_session(payload: CheckoutRequest) -> dict:
    stripe_service.ensure_configured()
    order = normalize_order(payload.order)
    db.upsert_order(order)
    checkout = stripe_service.create_checkout_session(order)
    db.set_checkout_session(order["id"], checkout["id"])
    return {"orderId": order["id"], "sessionId": checkout["id"], "url": checkout["url"]}


# ── Stripe webhook ────────────────────────────────────────────────────────────

@app.post("/api/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
) -> dict:
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


# ── Admin: List orders ────────────────────────────────────────────────────────

@app.get("/api/admin/orders", dependencies=[Depends(require_admin)])
def admin_orders() -> list[dict]:
    orders = db.list_orders()
    result = []
    for order in orders:
        order_id = order["id"]
        order["uploads"] = db.list_uploads(order_id)
        order["latestQuote"] = db.get_latest_quote(order_id)
        result.append(order)
    return result


# ── Admin: Get single order ───────────────────────────────────────────────────

@app.get("/api/admin/orders/{order_id}", dependencies=[Depends(require_admin)])
def admin_get_order(order_id: str) -> dict:
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    order["uploads"] = db.list_uploads(order_id)
    order["latestQuote"] = db.get_latest_quote(order_id)
    return order


# ── Admin: Send quote ─────────────────────────────────────────────────────────

@app.post("/api/admin/orders/{order_id}/quote", dependencies=[Depends(require_admin)])
def admin_send_quote(order_id: str, payload: QuoteCreate) -> dict:
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if order["status"] not in ("recibido", "cotizado"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede cotizar un pedido en estado '{order['status']}'.",
        )

    updated = db.save_quote(
        order_id,
        payload.total,
        payload.notes,
        payload.scope,
        payload.deadlineDays,
    )
    db.mark_quote_sent(order_id)
    email_service.send_quote_to_client(updated)
    return updated


# ── Admin: Update order status ────────────────────────────────────────────────

@app.patch("/api/admin/orders/{order_id}/status", dependencies=[Depends(require_admin)])
def admin_update_status(order_id: str, payload: StatusUpdate) -> dict:
    allowed = {"recibido", "cotizado", "pagado", "en_curso", "entregado", "cancelado"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Estado inválido: {payload.status}")
    updated = db.update_status(order_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    return updated


# ── Admin: Upload delivery files ──────────────────────────────────────────────

@app.post("/api/admin/orders/{order_id}/deliver", dependencies=[Depends(require_admin)])
async def admin_deliver(
    order_id: str,
    files: list[UploadFile] = File(...),
    notes: str = Form(default=""),
) -> dict:
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if order["status"] not in ("pagado", "en_curso", "entregado"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede entregar en estado '{order['status']}'.",
        )

    saved: list[dict] = []
    for upload in files:
        if upload.filename:
            ext = Path(upload.filename).suffix.lower()
            stored = f"{order_id}_design_{uuid.uuid4().hex[:8]}{ext}"
            dest = UPLOADS_DIR / stored
            content = await upload.read()
            dest.write_bytes(content)
            record = db.save_upload(order_id, "delivery", upload.filename, stored, len(content))
            saved.append(record)

    updated = db.update_status(order_id, "entregado")
    email_service.send_design_delivered(updated, saved, notes)
    return {"status": "entregado", "filesDelivered": saved}


# ── Dev: Mark paid ────────────────────────────────────────────────────────────

@app.post("/api/dev/mark-paid/{order_id}", dependencies=[Depends(require_admin)])
def dev_mark_paid(order_id: str) -> dict:
    if settings.app_env == "production":
        raise HTTPException(status_code=403, detail="Endpoint disponible solo fuera de producción.")
    paid_order = db.mark_paid(order_id, None, None)
    if not paid_order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    email_service.send_order_paid(paid_order)
    return paid_order


# ── Upload file serving ───────────────────────────────────────────────────────

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


# ── Static frontend assets ────────────────────────────────────────────────────

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


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(ROOT / "pages" / "admin.html")


@app.get("/mi-pedido")
def client_order_page() -> FileResponse:
    return FileResponse(ROOT / "pages" / "mi-pedido.html")


# ── Utility ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    from datetime import timezone
    return __import__("datetime").datetime.now(timezone.utc).isoformat()
