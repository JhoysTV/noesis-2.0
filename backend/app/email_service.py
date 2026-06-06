from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings
from .database import Database


def format_money(value: int) -> str:
    return f"RD$ {value:,.0f}"


def _order_lines(order: dict) -> str:
    return "\n".join(
        f"  • {item['name']}: {format_money(item['price'])}"
        for item in order["items"]
    )


class EmailService:
    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db

    def _send(self, recipient: str, subject: str, body: str, order_id: str) -> None:
        if not self.settings.smtp_enabled:
            self.db.log_email(order_id, recipient, subject, "skipped", "SMTP no configurado")
            return

        message = EmailMessage()
        message["From"] = self.settings.smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
                if self.settings.smtp_use_tls:
                    smtp.starttls()
                if self.settings.smtp_username:
                    smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)
            self.db.log_email(order_id, recipient, subject, "sent")
        except Exception as exc:  # noqa: BLE001
            self.db.log_email(order_id, recipient, subject, "error", str(exc))

    # ── New request received ─────────────────────────────────────

    def send_request_received(self, order: dict, photos: list[dict]) -> None:
        """Email to client (confirmation) + to studio (new lead notification)."""
        c = order["customer"]
        order_id = order["id"]
        token = order.get("clientToken", "")
        portal_url = f"{self.settings.app_base_url}/mi-pedido?token={token}"

        # To client
        client_body = f"""Hola {c['name']},

Hemos recibido tu solicitud de proyecto correctamente.

Nuestro equipo revisará los detalles y te enviará una cotización personalizada
en un plazo de 24 a 48 horas hábiles.

Resumen de tu solicitud:
  N.º de solicitud: {order_id}
  Tipo de proyecto: {order.get('projectType', '')}
  Área: {order.get('area', '')} m²
  Presupuesto estimado: {order.get('budget', '')}

Servicios solicitados:
{_order_lines(order)}

Puedes consultar el estado de tu solicitud en cualquier momento aquí:
{portal_url}

Si tienes preguntas, responde este correo o escríbenos por WhatsApp.

— Equipo Nóesis del Caribe
"""
        self._send(c["email"], f"Solicitud recibida — {order_id}", client_body, order_id)

        # To studio
        photos_text = (
            "\n".join(f"  • {p['originalName']} ({p['sizeBytes'] // 1024} KB)" for p in photos)
            if photos
            else "  (Sin fotos adjuntas)"
        )
        studio_body = f"""Nueva solicitud de proyecto recibida.

  Solicitud: {order_id}
  Cliente: {c['name']}
  Correo: {c['email']}
  Teléfono: {c.get('phone', '—')}
  Contacto preferido: {c.get('contactPreference', '—')}

  Tipo de proyecto: {order.get('projectType', '')}
  Área: {order.get('area', '')} m²
  Presupuesto declarado: {order.get('budget', '')}

Servicios:
{_order_lines(order)}

Descripción:
{order.get('requirements', '(Sin descripción)')}

Fotografías adjuntas:
{photos_text}

Notas sobre fotos:
{order.get('photoNotes', '(Sin notas)')}

Accede al panel para revisar y enviar cotización:
{self.settings.app_base_url}/admin
"""
        self._send(
            self.settings.studio_email,
            f"Nueva solicitud — {order_id} — {c['name']}",
            studio_body,
            order_id,
        )

    # ── Quote sent to client ─────────────────────────────────────

    def send_quote_to_client(self, order: dict) -> None:
        c = order["customer"]
        order_id = order["id"]
        token = order.get("clientToken", "")
        portal_url = f"{self.settings.app_base_url}/mi-pedido?token={token}"
        quote = order.get("quote", {})

        deadline_text = (
            f"\n  Plazo estimado de entrega: {quote.get('deadlineDays')} días hábiles"
            if quote.get("deadlineDays")
            else ""
        )

        body = f"""Hola {c['name']},

Tu cotización de Nóesis del Caribe está lista.

══ COTIZACIÓN {order_id} ══════════════════════

  Total a pagar: {format_money(quote.get('total', order.get('total', 0)))}
  Tipo de proyecto: {order.get('projectType', '')}{deadline_text}

Alcance incluido:
{quote.get('scope', '(Ver detalles en el portal)')}

Notas del arquitecto:
{quote.get('notes', '—')}

══════════════════════════════════════════════

Para aceptar la cotización y realizar tu pago, accede aquí:
{portal_url}

El enlace es personal y seguro. El pago se procesa a través de Stripe.

Si tienes preguntas, responde este correo o contáctanos directamente.

— Equipo Nóesis del Caribe
"""
        self._send(
            c["email"],
            f"Tu cotización está lista — {order_id} — {format_money(quote.get('total', 0))}",
            body,
            order_id,
        )

    # ── Payment confirmed ────────────────────────────────────────

    def send_order_paid(self, order: dict) -> None:
        c = order["customer"]
        order_id = order["id"]
        token = order.get("clientToken", "")
        portal_url = f"{self.settings.app_base_url}/mi-pedido?token={token}" if token else self.settings.app_base_url

        client_body = f"""Hola {c['name']},

Confirmamos la recepción de tu pago. ¡Gracias por confiar en Nóesis del Caribe!

  Pedido: {order_id}
  Total pagado: {format_money(order['total'])}

Nuestro equipo comenzará a trabajar en tu diseño de inmediato.
Te notificaremos cuando los diseños estén listos para descarga.

Puedes seguir el estado de tu proyecto aquí:
{portal_url}

— Equipo Nóesis del Caribe
"""
        self._send(
            c["email"],
            f"Pago confirmado — {order_id}",
            client_body,
            order_id,
        )

        studio_body = f"""Pago confirmado para el pedido {order_id}.

  Cliente: {c['name']} <{c['email']}>
  Total: {format_money(order['total'])}
  Proyecto: {order.get('projectType', '')}

Accede al panel para gestionar la entrega:
{self.settings.app_base_url}/admin
"""
        self._send(
            self.settings.studio_email,
            f"Pago confirmado — {order_id}",
            studio_body,
            order_id,
        )

    # ── Designs delivered ────────────────────────────────────────

    def send_design_delivered(self, order: dict, files: list[dict], notes: str = "") -> None:
        c = order["customer"]
        order_id = order["id"]
        token = order.get("clientToken", "")
        portal_url = f"{self.settings.app_base_url}/mi-pedido?token={token}"

        files_text = "\n".join(
            f"  • {f['originalName']}" for f in files
        ) or "  (Ver en el portal)"

        body = f"""Hola {c['name']},

¡Excelentes noticias! Tus diseños están listos para descarga.

  Pedido: {order_id}
  Proyecto: {order.get('projectType', '')}

Archivos disponibles:
{files_text}

{f"Nota del arquitecto:{chr(10)}{notes}{chr(10)}" if notes else ""}
Descarga tus diseños en:
{portal_url}

El enlace es personal y seguro. Los archivos estarán disponibles durante 90 días.

Si necesitas revisiones o tienes alguna consulta, responde este correo.

— Equipo Nóesis del Caribe
"""
        self._send(
            c["email"],
            f"Tus diseños están listos — {order_id}",
            body,
            order_id,
        )
