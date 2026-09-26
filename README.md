# Nóesis del Caribe — Portafolio, pedidos y pagos

Proyecto listo para despliegue con frontend estático y backend FastAPI. Incluye catálogo de servicios, formulario de requisitos, creación de pedido, Stripe Checkout, webhook firmado, persistencia SQLite y correos transaccionales por SMTP.

## Ejecutar en local

```powershell
py -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Abrir:

```text
http://127.0.0.1:8000/
```

## Configuración requerida

Edita `.env` antes de producción:

- `APP_BASE_URL`: dominio real con HTTPS.
- `ALLOWED_ORIGINS`: dominio real.
- `STRIPE_SECRET_KEY`: clave secreta de Stripe.
- `STRIPE_WEBHOOK_SECRET`: secreto del webhook Stripe.
- `ADMIN_TOKEN`: token largo para endpoints admin.
- `SMTP_*`: credenciales SMTP para correos.
- `STUDIO_EMAIL`: correo del arquitecto/estudio.

El frontend usa rutas relativas en [config.js](js/config.js), por lo que no expone claves secretas.

## Flujo productivo

1. Cliente selecciona servicios del catálogo.
2. Completa datos y requisitos.
3. Frontend envía el pedido a `/api/payments/checkout-session`.
4. Backend recalcula precios desde catálogo propio.
5. Backend crea sesión de Stripe Checkout.
6. Stripe redirige al cliente para pagar.
7. Stripe llama `/api/webhooks/stripe`.
8. Backend marca el pedido como `pagado`.
9. Backend envía correos al cliente y al estudio.

## Endpoints

- `GET /` — Portal principal
- `GET /terminos` — Términos contractuales y política de privacidad (Leyes 65-00 y 172-13)
- `GET /blog` — Criterios de diseño y artículos arquitectónicos
- `GET /careers` — Portal de talento y postulación
- `GET /admin` — Panel de administración de pedidos y cotizaciones
- `GET /mi-pedido` — Portal del cliente con token seguro
- `GET /robots.txt` & `GET /sitemap.xml` — SEO y rastreo
- `GET /api/health`
- `GET /api/catalog`
- `POST /api/orders/submit`
- `GET /api/order/{token}`
- `POST /api/payments/checkout-session`
- `POST /api/webhooks/stripe`
- `GET /api/admin/orders`

## Pruebas automatizadas

Ejecutar la suite completa de pruebas unitarias y de integración:

```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
```

## Despliegue con Docker

```powershell
docker build -t noesis .
docker run --env-file .env -p 8000:8000 noesis
```

## Stripe

Webhook requerido:

```text
https://tu-dominio.com/api/webhooks/stripe
```

Evento:

```text
checkout.session.completed
```

## Datos

Por defecto usa SQLite en `backend/data/noesis.sqlite3`. Para migrar a Supabase/PostgreSQL, usa el esquema base en [supabase-schema.sql](docs/supabase-schema.sql) y adapta el repositorio de datos.

## Verificación realizada

- Compilación Python limpia de `backend/`.
- Suite de pruebas automatizadas con 8 pruebas (`unittest` / `TestClient`).
- Corrección de sintaxis SQL en actualización de cotizaciones.
- Soporte dual de correos transaccionales: HTML responsive con branding Nóesis y texto plano alternativo.
- Enrutamiento limpio para `/terminos`, `/blog`, `/careers`, `/robots.txt` y `/sitemap.xml`.

