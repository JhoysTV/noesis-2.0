from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings
from .database import Database


def format_money(value: int) -> str:
    return f"RD$ {value:,.0f}"


def _order_lines_text(order: dict) -> str:
    return "\n".join(
        f"  • {item['name']}: {format_money(item['price'])}"
        for item in order["items"]
    )


def _order_lines_html(order: dict) -> str:
    rows = "".join(
        f"""<tr>
          <td style="padding:10px 14px;border-bottom:1px solid #f0eee9;font-weight:600;color:#191714;">{item['name']}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #f0eee9;text-align:right;color:#D3AB2D;font-weight:700;">{format_money(item['price'])}</td>
        </tr>"""
        for item in order["items"]
    )
    return f"""<table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin:16px 0;border:1px solid #e8e6e1;border-radius:6px;overflow:hidden;font-size:14px;">
      <thead style="background-color:#f9f8f6;">
        <tr>
          <th style="padding:10px 14px;text-align:left;font-size:12px;text-transform:uppercase;color:#6b6045;letter-spacing:1px;">Servicio</th>
          <th style="padding:10px 14px;text-align:right;font-size:12px;text-transform:uppercase;color:#6b6045;letter-spacing:1px;">Estimado</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def _wrap_html(title: str, preheader: str, content_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#191714;">
  <div style="display:none;font-size:1px;color:#f4f4f3;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
    {preheader}
  </div>
  <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:#f4f4f3;padding:32px 15px;">
    <tr>
      <td align="center">
        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="max-width:600px;background-color:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #e0dfdc;box-shadow:0 4px 20px rgba(0,0,0,0.05);">
          <!-- Header -->
          <tr>
            <td style="background-color:#191714;padding:28px 32px;text-align:left;border-bottom:3px solid #D3AB2D;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <div style="font-size:18px;font-weight:900;letter-spacing:1.5px;color:#ffffff;text-transform:uppercase;margin:0;">
                      NÓESIS DEL CARIBE
                    </div>
                    <div style="font-size:11px;letter-spacing:2px;color:#B3AA99;text-transform:uppercase;margin-top:4px;">
                      Ingeniería &amp; Arquitectura · Santo Domingo
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Content Body -->
          <tr>
            <td style="padding:32px;line-height:1.6;font-size:15px;color:#33302a;">
              {content_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#191714;padding:24px 32px;text-align:center;color:#B3AA99;font-size:12px;line-height:1.5;border-top:1px solid #282420;">
              <p style="margin:0 0 6px 0;color:#ffffff;font-weight:bold;">Nóesis del Caribe — Estudio de Ingeniería &amp; Arquitectura</p>
              <p style="margin:0 0 6px 0;">Santo Domingo, República Dominicana · WhatsApp: +1 (829) 542-5046</p>
              <p style="margin:0;color:#8c8577;font-size:11px;">Este mensaje fue generado automáticamente para el seguimiento seguro de tu proyecto.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


class EmailService:
    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db

    def _send(self, recipient: str, subject: str, text_body: str, order_id: str, html_body: str | None = None) -> None:
        if not self.settings.smtp_enabled:
            self.db.log_email(order_id, recipient, subject, "skipped", "SMTP no configurado")
            return

        message = EmailMessage()
        message["From"] = self.settings.smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text_body)

        if html_body:
            message.add_alternative(html_body, subtype="html")

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
        c = order["customer"]
        order_id = order["id"]
        token = order.get("clientToken", "")
        portal_url = f"{self.settings.app_base_url}/mi-pedido?token={token}"

        # To client (Text)
        client_text = f"""Hola {c['name']},

Hemos recibido tu solicitud de proyecto correctamente.

Nuestro equipo revisará los detalles y te enviará una cotización personalizada
en un plazo de 24 a 48 horas hábiles.

Resumen de tu solicitud:
  N.º de solicitud: {order_id}
  Tipo de proyecto: {order.get('projectType', '')}
  Área: {order.get('area', '')} m²
  Presupuesto estimado: {order.get('budget', '')}

Servicios solicitados:
{_order_lines_text(order)}

Puedes consultar el estado de tu solicitud en cualquier momento aquí:
{portal_url}

Si tienes preguntas, responde este correo o escríbenos por WhatsApp al +1 (829) 542-5046.

— Equipo Nóesis del Caribe
"""
        # To client (HTML)
        client_html_content = f"""
        <h2 style="margin:0 0 16px;color:#191714;font-size:22px;font-weight:800;">¡Hola {c['name']}!</h2>
        <p style="margin:0 0 16px;color:#4D4637;font-size:15px;">Hemos recibido la solicitud para tu proyecto <strong>{order.get('projectType', '')}</strong>.</p>
        <p style="margin:0 0 20px;color:#4D4637;font-size:15px;">Nuestro equipo de arquitectura e ingeniería está revisando los requerimientos, planos y fotografías para estructurar una propuesta técnica y económica personalizada en <strong>24 a 48 horas hábiles</strong>.</p>

        <div style="background-color:#f9f8f6;border-radius:6px;padding:18px;border-left:4px solid #D3AB2D;margin-bottom:20px;">
          <table width="100%" border="0" cellpadding="2" cellspacing="0" style="font-size:14px;color:#4D4637;">
            <tr><td><strong>N.º Solicitud:</strong></td><td style="color:#191714;font-family:monospace;font-weight:bold;">{order_id}</td></tr>
            <tr><td><strong>Tipo de Proyecto:</strong></td><td>{order.get('projectType', '')}</td></tr>
            <tr><td><strong>Área aproximada:</strong></td><td>{order.get('area', '—')} m²</td></tr>
            <tr><td><strong>Presupuesto declarado:</strong></td><td>{order.get('budget', '—')}</td></tr>
          </table>
        </div>

        <p style="margin:0 0 8px;font-weight:700;color:#191714;font-size:14px;text-transform:uppercase;letter-spacing:0.5px;">Módulos Seleccionados:</p>
        {_order_lines_html(order)}

        <div style="text-align:center;margin:32px 0 24px;">
          <a href="{portal_url}" style="background-color:#D3AB2D;color:#191714;padding:14px 28px;font-size:14px;font-weight:800;text-decoration:none;border-radius:4px;display:inline-block;letter-spacing:0.5px;text-transform:uppercase;">Ver estado de mi solicitud</a>
        </div>
        <p style="margin:0;color:#8c8577;font-size:13px;text-align:center;">Guarda este enlace para consultar actualizaciones en tiempo real sobre tu proyecto.</p>
        """
        client_html = _wrap_html(f"Solicitud recibida — {order_id}", f"Hemos recibido tu solicitud de proyecto {order_id}", client_html_content)
        self._send(c["email"], f"Solicitud recibida — {order_id}", client_text, order_id, client_html)

        # To studio
        photos_text = (
            "\n".join(f"  • {p['originalName']} ({p['sizeBytes'] // 1024} KB)" for p in photos)
            if photos
            else "  (Sin fotos adjuntas)"
        )
        photos_html = (
            "".join(f"<li>{p['originalName']} ({p['sizeBytes'] // 1024} KB)</li>" for p in photos)
            if photos
            else "<li><em>Sin fotografías adjuntas</em></li>"
        )
        studio_text = f"""Nueva solicitud de proyecto recibida.

  Solicitud: {order_id}
  Cliente: {c['name']}
  Correo: {c['email']}
  Teléfono: {c.get('phone', '—')}
  Contacto preferido: {c.get('contactPreference', '—')}

  Tipo de proyecto: {order.get('projectType', '')}
  Área: {order.get('area', '')} m²
  Presupuesto declarado: {order.get('budget', '')}

Servicios:
{_order_lines_text(order)}

Descripción:
{order.get('requirements', '(Sin descripción)')}

Fotografías adjuntas:
{photos_text}

Notas sobre fotos:
{order.get('photoNotes', '(Sin notas)')}

Accede al panel para revisar y enviar cotización:
{self.settings.app_base_url}/admin
"""
        studio_html_content = f"""
        <h2 style="margin:0 0 16px;color:#191714;font-size:20px;">Nueva Solicitud: {order_id}</h2>
        <div style="background-color:#f9f8f6;border-radius:6px;padding:16px;margin-bottom:20px;font-size:14px;color:#4D4637;">
          <p style="margin:0 0 6px;"><strong>Cliente:</strong> {c['name']} (&lt;{c['email']}&gt;)</p>
          <p style="margin:0 0 6px;"><strong>Teléfono:</strong> {c.get('phone', '—')} · Prefiere: {c.get('contactPreference', '—')}</p>
          <p style="margin:0 0 6px;"><strong>Proyecto:</strong> {order.get('projectType', '')} ({order.get('area', '—')} m²)</p>
          <p style="margin:0;"><strong>Presupuesto:</strong> {order.get('budget', '—')}</p>
        </div>

        <p style="margin:0 0 8px;font-weight:700;">Servicios solicitados:</p>
        {_order_lines_html(order)}

        <p style="margin:16px 0 6px;font-weight:700;">Requisitos del cliente:</p>
        <p style="background:#ffffff;border:1px solid #e0dfdc;padding:12px;border-radius:4px;color:#4D4637;font-size:14px;margin:0 0 16px;">{order.get('requirements', '(Sin descripción)')}</p>

        <p style="margin:0 0 6px;font-weight:700;">Archivos fotográficos:</p>
        <ul style="color:#4D4637;font-size:14px;margin:0 0 24px;padding-left:20px;">{photos_html}</ul>

        <div style="text-align:center;">
          <a href="{self.settings.app_base_url}/admin" style="background-color:#191714;color:#D3AB2D;padding:12px 24px;font-size:13px;font-weight:bold;text-decoration:none;border-radius:4px;display:inline-block;text-transform:uppercase;">Ir al panel de administración</a>
        </div>
        """
        studio_html = _wrap_html(f"Nueva solicitud — {order_id}", f"Nueva solicitud de {c['name']} ({order_id})", studio_html_content)
        self._send(
            self.settings.studio_email,
            f"Nueva solicitud — {order_id} — {c['name']}",
            studio_text,
            order_id,
            studio_html,
        )

    # ── Quote sent to client ─────────────────────────────────────

    def send_quote_to_client(self, order: dict) -> None:
        c = order["customer"]
        order_id = order["id"]
        token = order.get("clientToken", "")
        portal_url = f"{self.settings.app_base_url}/mi-pedido?token={token}"
        quote = order.get("quote", {})
        total_price = quote.get("total", order.get("total", 0))

        deadline_text = (
            f"\n  Plazo estimado de entrega: {quote.get('deadlineDays')} días hábiles"
            if quote.get("deadlineDays")
            else ""
        )

        text_body = f"""Hola {c['name']},

Tu cotización de Nóesis del Caribe está lista.

══ COTIZACIÓN {order_id} ══════════════════════

  Total a pagar: {format_money(total_price)}
  Tipo de proyecto: {order.get('projectType', '')}{deadline_text}

Alcance incluido:
{quote.get('scope', '(Ver detalles en el portal)')}

Notas del arquitecto:
{quote.get('notes', '—')}

══════════════════════════════════════════════

Para aceptar la cotización y realizar tu pago seguro, accede aquí:
{portal_url}

Si tienes preguntas, responde este correo o contáctanos por WhatsApp.

— Equipo Nóesis del Caribe
"""
        html_content = f"""
        <h2 style="margin:0 0 14px;color:#191714;font-size:22px;font-weight:800;">Tu cotización está lista</h2>
        <p style="margin:0 0 20px;color:#4D4637;font-size:15px;">Hemos formulado la propuesta para tu proyecto <strong>{order.get('projectType', '')}</strong>.</p>

        <div style="background-color:#191714;color:#ffffff;border-radius:8px;padding:24px;text-align:center;margin-bottom:24px;border:1px solid #D3AB2D;">
          <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#B3AA99;">Presupuesto Total del Proyecto</div>
          <div style="font-size:32px;font-weight:900;color:#D3AB2D;margin:8px 0;">{format_money(total_price)}</div>
          <div style="font-size:13px;color:#ffffff;opacity:0.85;">Plazo estimado de desarrollo: <strong>{quote.get('deadlineDays', '10-15')} días hábiles</strong></div>
        </div>

        <div style="background-color:#f9f8f6;border-radius:6px;padding:18px;margin-bottom:20px;font-size:14px;color:#4D4637;">
          <h4 style="margin:0 0 8px;color:#191714;font-size:14px;text-transform:uppercase;letter-spacing:0.5px;">Alcance y Entregables Incluidos:</h4>
          <p style="margin:0 0 14px;line-height:1.6;">{quote.get('scope', 'Desarrollo de anteproyecto, planos ejecutivos y visualizaciones acordadas.')}</p>

          <h4 style="margin:0 0 8px;color:#191714;font-size:14px;text-transform:uppercase;letter-spacing:0.5px;">Observaciones del Estudio:</h4>
          <p style="margin:0;line-height:1.6;">{quote.get('notes', 'Quedamos a su disposición para coordinar detalles previos al inicio.')}</p>
        </div>

        <div style="text-align:center;margin:32px 0 20px;">
          <a href="{portal_url}" style="background-color:#D3AB2D;color:#191714;padding:14px 28px;font-size:14px;font-weight:800;text-decoration:none;border-radius:4px;display:inline-block;letter-spacing:0.5px;text-transform:uppercase;">Revisar y Pagar Cotización</a>
        </div>
        <p style="margin:0;color:#8c8577;font-size:12px;text-align:center;">El pago se procesa de forma segura a través de Stripe o transferencia bancaria.</p>
        """
        html_body = _wrap_html(f"Cotización lista — {order_id}", f"Tu cotización de {format_money(total_price)} está disponible", html_content)

        self._send(
            c["email"],
            f"Tu cotización está lista — {order_id} — {format_money(total_price)}",
            text_body,
            order_id,
            html_body,
        )

    # ── Payment confirmed ────────────────────────────────────────

    def send_order_paid(self, order: dict) -> None:
        c = order["customer"]
        order_id = order["id"]
        token = order.get("clientToken", "")
        portal_url = f"{self.settings.app_base_url}/mi-pedido?token={token}" if token else self.settings.app_base_url

        text_body = f"""Hola {c['name']},

Confirmamos la recepción de tu pago. ¡Gracias por confiar en Nóesis del Caribe!

  Pedido: {order_id}
  Total pagado: {format_money(order['total'])}

Nuestro equipo comenzará a trabajar en tu diseño de inmediato.
Te notificaremos cuando los diseños estén listos para descarga.

Puedes seguir el estado de tu proyecto aquí:
{portal_url}

— Equipo Nóesis del Caribe
"""
        html_content = f"""
        <div style="text-align:center;margin-bottom:24px;">
          <span style="display:inline-block;background-color:#e6f4ea;color:#137333;font-size:14px;font-weight:bold;padding:6px 14px;border-radius:20px;text-transform:uppercase;letter-spacing:1px;">✓ Pago Acreditado Exitosamente</span>
        </div>
        <h2 style="margin:0 0 14px;color:#191714;font-size:22px;font-weight:800;text-align:center;">¡Comenzamos tu proyecto!</h2>
        <p style="margin:0 0 20px;color:#4D4637;font-size:15px;text-align:center;">Hemos confirmado el pago de <strong>{format_money(order['total'])}</strong> para el pedido <strong>{order_id}</strong>.</p>

        <div style="background-color:#f9f8f6;border-radius:6px;padding:20px;margin-bottom:24px;border:1px solid #e0dfdc;">
          <p style="margin:0 0 10px;font-size:14px;color:#4D4637;">El equipo de arquitectos e ingenieros de Nóesis del Caribe ha iniciado formalmente la fase proyectual de tu espacio.</p>
          <p style="margin:0;font-size:14px;color:#4D4637;">Te notificaremos por correo electrónico cada avance y te enviaremos el enlace directo para descargar los planos y renders una vez completados.</p>
        </div>

        <div style="text-align:center;margin:32px 0 20px;">
          <a href="{portal_url}" style="background-color:#191714;color:#D3AB2D;padding:14px 28px;font-size:14px;font-weight:800;text-decoration:none;border-radius:4px;display:inline-block;letter-spacing:0.5px;text-transform:uppercase;">Seguir progreso del proyecto</a>
        </div>
        """
        html_body = _wrap_html(f"Pago confirmado — {order_id}", f"Confirmamos tu pago para el pedido {order_id}", html_content)

        self._send(
            c["email"],
            f"Pago confirmado — {order_id}",
            text_body,
            order_id,
            html_body,
        )

        # Studio notification
        studio_text = f"""Pago confirmado para el pedido {order_id}.

  Cliente: {c['name']} <{c['email']}>
  Total: {format_money(order['total'])}
  Proyecto: {order.get('projectType', '')}

Accede al panel para gestionar la entrega:
{self.settings.app_base_url}/admin
"""
        studio_html = _wrap_html(
            f"Pago confirmado — {order_id}",
            f"Pago confirmado de {format_money(order['total'])}",
            f"""
            <h3 style="margin:0 0 12px;color:#137333;">Pago recibido: {order_id}</h3>
            <p style="margin:0 0 8px;"><strong>Cliente:</strong> {c['name']} ({c['email']})</p>
            <p style="margin:0 0 8px;"><strong>Total:</strong> {format_money(order['total'])}</p>
            <p style="margin:0 0 20px;"><strong>Proyecto:</strong> {order.get('projectType', '')}</p>
            <a href="{self.settings.app_base_url}/admin" style="background:#191714;color:#D3AB2D;padding:10px 20px;text-decoration:none;font-size:13px;font-weight:bold;border-radius:4px;display:inline-block;">Abrir Panel de Pedidos</a>
            """
        )
        self._send(
            self.settings.studio_email,
            f"Pago confirmado — {order_id}",
            studio_text,
            order_id,
            studio_html,
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

        files_html = "".join(
            f"""<li style="padding:6px 0;border-bottom:1px solid #f0eee9;color:#191714;font-weight:600;">📄 {f['originalName']} <span style="color:#8c8577;font-weight:normal;font-size:12px;">({f.get('sizeBytes', 0) // 1024} KB)</span></li>"""
            for f in files
        ) or "<li>(Archivos disponibles en el portal)</li>"

        text_body = f"""Hola {c['name']},

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
        html_content = f"""
        <div style="text-align:center;margin-bottom:20px;">
          <span style="display:inline-block;background-color:#e6f4ea;color:#137333;font-size:13px;font-weight:bold;padding:6px 14px;border-radius:20px;text-transform:uppercase;letter-spacing:1px;">🎉 ¡Entrega Final Lista!</span>
        </div>
        <h2 style="margin:0 0 14px;color:#191714;font-size:22px;font-weight:800;text-align:center;">Tus diseños arquitectónicos están listos</h2>
        <p style="margin:0 0 20px;color:#4D4637;font-size:15px;text-align:center;">Hemos culminado los planos, especificaciones y renders para el proyecto <strong>{order.get('projectType', '')}</strong>.</p>

        <div style="background-color:#f9f8f6;border-radius:6px;padding:20px;margin-bottom:24px;border:1px solid #e0dfdc;">
          <h4 style="margin:0 0 12px;color:#191714;font-size:13px;text-transform:uppercase;letter-spacing:1px;">Archivos disponibles para descarga:</h4>
          <ul style="list-style:none;padding:0;margin:0 0 16px;font-size:14px;">
            {files_html}
          </ul>
          {f'<div style="background:#ffffff;border-left:3px solid #D3AB2D;padding:12px;border-radius:4px;font-size:13px;color:#4D4637;"><strong>Nota del arquitecto:</strong> {notes}</div>' if notes else ''}
        </div>

        <div style="text-align:center;margin:32px 0 20px;">
          <a href="{portal_url}" style="background-color:#D3AB2D;color:#191714;padding:14px 28px;font-size:14px;font-weight:800;text-decoration:none;border-radius:4px;display:inline-block;letter-spacing:0.5px;text-transform:uppercase;">Descargar Archivos en el Portal</a>
        </div>
        <p style="margin:0;color:#8c8577;font-size:12px;text-align:center;">El enlace es personal e inviolable. Cuentas con tus 2 rondas de revisiones incluidas si deseas realizar ajustes.</p>
        """
        html_body = _wrap_html(f"Tus diseños están listos — {order_id}", f"Descarga tus diseños del proyecto {order_id}", html_content)

        self._send(
            c["email"],
            f"Tus diseños están listos — {order_id}",
            text_body,
            order_id,
            html_body,
        )
