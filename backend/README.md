# Backend de producción

API FastAPI para el sitio de Nóesis del Caribe. Sirve el frontend estático y expone endpoints para catálogo, Stripe Checkout, webhooks, pedidos y correos transaccionales.

## Instalación

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con las credenciales reales.

## Ejecutar

```powershell
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Abre `http://127.0.0.1:8000/`.

## Endpoints

- `GET /api/health`
- `GET /api/catalog`
- `POST /api/payments/checkout-session`
- `POST /api/webhooks/stripe`
- `GET /api/admin/orders`

## Stripe

Configura en Stripe un webhook hacia:

```text
https://tu-dominio.com/api/webhooks/stripe
```

Evento requerido:

```text
checkout.session.completed
```

## Seguridad

- No pongas claves secretas en `js/config.js`.
- Usa HTTPS en producción.
- Cambia `ADMIN_TOKEN`.
- Configura `ALLOWED_ORIGINS` con el dominio real.
- El backend recalcula precios desde `backend/app/catalog.py`; no confía en el total enviado por el navegador.
