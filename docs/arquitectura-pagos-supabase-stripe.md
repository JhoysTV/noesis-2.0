# Arquitectura objetivo: pedidos, Stripe, Supabase y correos

El sitio actual es un prototipo estático. La implementación en navegador usa `localStorage` para demostrar el flujo completo descrito en el alcance: catálogo con precio, carrito, pedido borrador, pago simulado y confirmación de correos.

## Decisión de flujo

Se adopta el enfoque de **pedido borrador antes del pago**:

1. El cliente selecciona módulos del catálogo.
2. Completa datos de contacto y requisitos.
3. La app crea un pedido con estado `borrador`.
4. El backend crea una sesión de Stripe Checkout ligada al `order_id`.
5. Stripe confirma el pago por webhook.
6. El backend marca el pedido como `pagado`.
7. El backend envía correos al cliente y al arquitecto.

## Entidades mínimas

- `catalog_items`: nombre, descripción, categoría, precio, estado activo.
- `orders`: cliente, contacto, requisitos, total, estado, referencia Stripe.
- `order_lines`: `order_id`, `catalog_item_id`, nombre congelado, precio congelado.
- `payment_events`: `stripe_event_id`, tipo, payload resumido, estado de procesamiento.
- `email_logs`: destinatario, asunto, tipo, estado de envío.

## Endpoints sugeridos

- `GET /catalog`: lista pública de servicios activos.
- `POST /orders`: crea pedido borrador con líneas y datos de contacto.
- `POST /payments/checkout-session`: recibe el pedido borrador, valida precios contra catálogo, persiste la orden y crea sesión Stripe.
- `POST /webhooks/stripe`: valida firma, procesa eventos idempotentemente y marca pagos.
- `GET /admin/orders`: listado para el arquitecto.
- `PATCH /admin/orders/{id}`: cambio de estado operativo.

## Reglas de seguridad

- Las claves secretas de Stripe, Supabase service role y correo viven solo en el backend Python.
- El webhook debe validar `Stripe-Signature` y registrar `stripe_event_id` para idempotencia.
- El total cobrado se calcula en backend desde precios persistidos, no desde el cliente.
- Las políticas RLS de Supabase deben permitir lectura pública solo del catálogo activo.
- Los pedidos completos se consultan desde API autenticada o con RLS de administrador.

## Mapeo del prototipo actual

- `js/orders.js`: simula catálogo, carrito, pedidos, referencia Stripe y correos.
- `js/form.js`: crea el pedido borrador desde datos del cliente.
- `js/payment.js`: simula la confirmación de pago y el webhook.
- `#admin`: simula el panel de pedidos del arquitecto.
