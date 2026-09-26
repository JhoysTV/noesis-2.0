from __future__ import annotations

import hmac
import json
import re
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .catalog import list_catalog
from .config import Settings, get_settings
from .database import Database
from .email_service import EmailService
from .models import (
    AdminLogin,
    CheckoutFromToken,
    CheckoutRequest,
    QuoteCreate,
    StatusUpdate,
    SubmitRequest,
)
from .orders import normalize_order
from .stripe_service import StripeService


settings = get_settings()
db = Database(settings.database_file)
db.init()
email_service = EmailService(settings, db)
stripe_service = StripeService(settings)

UPLOADS_DIR = settings.database_file.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed extensions per upload type
_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
_DELIVERY_EXTS = {".jpg", ".jpeg", ".png", ".pdf", ".dwg", ".zip", ".rar", ".svg", ".ai", ".psd", ".doc", ".docx"}
_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB per file

# ── Rate limiter (in-memory, per IP) ─────────────────────────────────────────

_rate_store: dict[str, list[float]] = defaultdict(list)

def _check_rate(key: str, max_req: int, window: int) -> bool:
    now = time.monotonic()
    hits = [t for t in _rate_store.get(key, []) if now - t < window]
    if hits:
        _rate_store[key] = hits
    else:
        _rate_store.pop(key, None)
    if len(hits) >= max_req:
        return False
    _rate_store.setdefault(key, []).append(now)
    return True

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.client.host or "unknown"

# ── Secure comparisons ────────────────────────────────────────────────────────

def _safe_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())

# ── Filename sanitizer ────────────────────────────────────────────────────────

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-\.]+$")

def _safe_filename(name: str) -> str:
    """Return only the basename and reject path-traversal attempts."""
    base = Path(name).name
    if not _SAFE_NAME.match(base) or ".." in base:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido.")
    return base

# ── File type & size validation ───────────────────────────────────────────────

async def _read_and_validate(upload: UploadFile, allowed_exts: set[str]) -> bytes:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: '{ext}'. "
                   f"Permitidos: {', '.join(sorted(allowed_exts))}",
        )
    content = await upload.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo '{upload.filename}' supera el límite de 50 MB.",
        )
    return content

# ── Scrub sensitive fields from public responses ──────────────────────────────

def _public_order(order: dict) -> dict:
    """Remove internal fields before sending data to unauthenticated clients."""
    return {k: v for k, v in order.items() if k not in ("clientToken",)}

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Noesis del Caribe API", version="2.0.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Security headers middleware ───────────────────────────────────────────────

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache"
    return response

# ── Auth ──────────────────────────────────────────────────────────────────────

def require_admin(authorization: str = Header(default="")) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN no está configurado.")
    expected = f"Bearer {settings.admin_token}"
    if not _safe_eq(authorization, expected):
        raise HTTPException(status_code=401, detail="No autorizado.")

# ── Health & Catalog ──────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "env": settings.app_env}

@app.get("/api/catalog")
def catalog() -> list[dict]:
    return list_catalog()

# ── Admin login ───────────────────────────────────────────────────────────────

@app.post("/api/admin/login")
def admin_login(payload: AdminLogin, request: Request) -> dict:
    ip = _client_ip(request)
    if not _check_rate(f"login:{ip}", max_req=10, window=900):  # 10 / 15 min
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera 15 minutos.")

    if not settings.admin_username or not settings.admin_password or not settings.admin_token:
        raise HTTPException(status_code=503, detail="Panel no configurado en el servidor.")

    user_ok = _safe_eq(payload.username, settings.admin_username)
    pass_ok = _safe_eq(payload.password, settings.admin_password)
    time.sleep(0.3)  # Delay constante para dificultar timing attacks

    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

    return {"token": settings.admin_token}

# ── Public: Submit new request ────────────────────────────────────────────────

@app.post("/api/orders/submit")
async def submit_order(
    request: Request,
    order_data: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> dict:
    ip = _client_ip(request)
    if not _check_rate(f"submit:{ip}", max_req=5, window=3600):  # 5 / hour
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Intenta más tarde.")

    try:
        payload = SubmitRequest.model_validate_json(order_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    order_id = f"NOE-{uuid.uuid4().hex[:8].upper()}"
    client_token = secrets.token_urlsafe(32)

    order = {
        "id": order_id,
        "status": "recibido",
        "clientToken": client_token,
        "createdAt": datetime.now(timezone.utc).isoformat(),
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

    saved_photos: list[dict] = []
    for upload in files:
        if not upload.filename:
            continue
        content = await _read_and_validate(upload, _PHOTO_EXTS)
        ext = Path(upload.filename).suffix.lower()
        stored = f"{order_id}_{uuid.uuid4().hex[:8]}{ext}"
        (UPLOADS_DIR / stored).write_bytes(content)
        saved_photos.append(db.save_upload(order_id, "client_photo", upload.filename, stored, len(content)))

    email_service.send_request_received(order, saved_photos)

    return {
        "orderId": order_id,
        "clientToken": client_token,
        "message": "Solicitud recibida. Te enviaremos la cotización por correo en 24–48 horas.",
    }

# ── Public: Client order status ───────────────────────────────────────────────

@app.get("/api/order/{token}")
def get_order_by_token(token: str) -> dict:
    order = db.find_order_by_token(token)
    if not order:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    order_id = order["id"]
    uploads = db.list_uploads(order_id, "delivery")
    quote = db.get_latest_quote(order_id)

    return {
        "order": _public_order(order),   # clientToken never sent to browser
        "quote": quote,
        "deliveryFiles": uploads,
    }

# ── Public: Protected file download ──────────────────────────────────────────

@app.get("/api/files/{stored_name}")
def get_file(
    stored_name: str,
    t: str | None = None,           # client token query param
    ak: str | None = None,          # admin key query param
    authorization: str = Header(default=""),
) -> FileResponse:
    safe_name = _safe_filename(stored_name)
    file_path = UPLOADS_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    # Admin access via Bearer header or query param
    if settings.admin_token:
        bearer_ok = _safe_eq(authorization, f"Bearer {settings.admin_token}")
        ak_ok = bool(ak) and _safe_eq(ak, settings.admin_token)
        if bearer_ok or ak_ok:
            return FileResponse(file_path, filename=safe_name)

    # Client access: token must belong to an order that owns this file
    if t:
        order = db.find_order_by_token(t)
        if order:
            allowed = db.list_uploads(order["id"])
            if any(u["storedName"] == safe_name for u in allowed):
                return FileResponse(file_path, filename=safe_name)

    raise HTTPException(status_code=403, detail="Acceso no autorizado.")

# ── Public: Stripe checkout from client token ─────────────────────────────────

@app.post("/api/order/checkout")
def checkout_from_token(payload: CheckoutFromToken) -> dict:
    stripe_service.ensure_configured()
    order = db.find_order_by_token(payload.token)
    if not order:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if order["status"] not in ("cotizado",):
        raise HTTPException(status_code=400, detail="El pedido no está en estado de pago.")
    checkout = stripe_service.create_checkout_session(order, client_token=payload.token)
    db.set_checkout_session(order["id"], checkout["id"])
    return {"sessionId": checkout["id"], "url": checkout["url"]}

# ── Legacy: Stripe checkout from cart ────────────────────────────────────────

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
    updated = db.save_quote(order_id, payload.total, payload.notes, payload.scope, payload.deadlineDays)
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
        if not upload.filename:
            continue
        content = await _read_and_validate(upload, _DELIVERY_EXTS)
        ext = Path(upload.filename).suffix.lower()
        stored = f"{order_id}_design_{uuid.uuid4().hex[:8]}{ext}"
        (UPLOADS_DIR / stored).write_bytes(content)
        saved.append(db.save_upload(order_id, "delivery", upload.filename, stored, len(content)))

    updated = db.update_status(order_id, "entregado")
    email_service.send_design_delivered(updated, saved, notes)
    return {"status": "entregado", "filesDelivered": saved}

# ── Dev: Mark paid (non-production only) ─────────────────────────────────────

@app.post("/api/dev/mark-paid/{order_id}", dependencies=[Depends(require_admin)])
def dev_mark_paid(order_id: str) -> dict:
    if settings.app_env == "production":
        raise HTTPException(status_code=403, detail="Endpoint disponible solo fuera de producción.")
    paid_order = db.mark_paid(order_id, None, None)
    if not paid_order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    email_service.send_order_paid(paid_order)
    return paid_order

# ── Static frontend assets ────────────────────────────────────────────────────

ROOT = settings.root_dir

app.mount("/css", StaticFiles(directory=ROOT / "css"), name="css")
app.mount("/js", StaticFiles(directory=ROOT / "js"), name="js")
app.mount("/pages", StaticFiles(directory=ROOT / "pages"), name="pages")
app.mount("/docs", StaticFiles(directory=ROOT / "docs"), name="docs")

# NOTE: /uploads is NOT mounted publicly — files are served via /api/files/{name}


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

@app.get("/terminos")
def terminos_page() -> FileResponse:
    return FileResponse(ROOT / "pages" / "terminos.html")

@app.get("/blog")
def blog_page() -> FileResponse:
    return FileResponse(ROOT / "pages" / "blog.html")

@app.get("/careers")
def careers_page() -> FileResponse:
    return FileResponse(ROOT / "pages" / "careers.html")

@app.get("/robots.txt")
def robots_txt() -> FileResponse:
    return FileResponse(ROOT / "robots.txt", media_type="text/plain")

@app.get("/sitemap.xml")
def sitemap_xml() -> FileResponse:
    return FileResponse(ROOT / "sitemap.xml", media_type="application/xml")
