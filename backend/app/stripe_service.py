from __future__ import annotations

from fastapi import HTTPException

from .config import Settings


class StripeService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stripe = None
        if settings.stripe_secret_key:
            try:
                import stripe  # type: ignore

                stripe.api_key = settings.stripe_secret_key
                self._stripe = stripe
            except ImportError as exc:
                raise RuntimeError("Instala dependencias: pip install -r requirements.txt") from exc

    def ensure_configured(self) -> None:
        if not self.settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY no está configurada.")
        if not self._stripe:
            raise HTTPException(status_code=503, detail="Stripe SDK no disponible.")

    def create_checkout_session(self, order: dict) -> dict:
        self.ensure_configured()
        success_url = f"{self.settings.app_base_url}/index.html?checkout=success&order={order['id']}"
        cancel_url = f"{self.settings.app_base_url}/index.html?checkout=cancelled&order={order['id']}"
        session = self._stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=order["customer"]["email"],
            client_reference_id=order["id"],
            metadata={"order_id": order["id"]},
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": self.settings.stripe_currency,
                        "unit_amount": int(item["price"]) * 100,
                        "product_data": {
                            "name": item["name"],
                            "metadata": {"catalog_item_id": item["id"]},
                        },
                    },
                }
                for item in order["items"]
            ],
        )
        return {"id": session.id, "url": session.url}

    def construct_event(self, payload: bytes, signature: str):
        self.ensure_configured()
        if not self.settings.stripe_webhook_secret:
            raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET no está configurado.")
        try:
            return self._stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=self.settings.stripe_webhook_secret,
            )
        except Exception as exc:  # noqa: BLE001 - Stripe raises several SDK-specific errors.
            raise HTTPException(status_code=400, detail="Firma de webhook inválida.") from exc
