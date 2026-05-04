from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings
from .database import Database


def format_money(value: int) -> str:
    return f"RD$ {value:,.0f}"


def order_text(order: dict, audience: str) -> str:
    lines = "\n".join(f"- {item['name']}: {format_money(item['price'])}" for item in order["items"])
    customer = order["customer"]
    return f"""Pedido {order['id']} confirmado

Cliente: {customer['name']}
Correo: {customer['email']}
Teléfono: {customer.get('phone', '')}
Tipo de proyecto: {order.get('projectType', '')}
Área: {order.get('area', '')} m²
Presupuesto declarado: {order.get('budget', '')}

Servicios:
{lines}

Total: {format_money(order['total'])}

Requisitos:
{order.get('requirements', '')}

Este mensaje fue generado para {audience}.
"""


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
        except Exception as exc:  # noqa: BLE001 - preserve delivery failure in logs.
            self.db.log_email(order_id, recipient, subject, "error", str(exc))

    def send_order_paid(self, order: dict) -> None:
        customer_email = order["customer"]["email"]
        self._send(
            customer_email,
            f"Confirmación de pedido {order['id']}",
            order_text(order, "el cliente"),
            order["id"],
        )
        self._send(
            self.settings.studio_email,
            f"Nueva orden pagada {order['id']}",
            order_text(order, "el estudio"),
            order["id"],
        )
