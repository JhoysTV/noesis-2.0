from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from .catalog import get_catalog_item
from .models import DraftOrder


def normalize_order(draft: DraftOrder) -> dict:
    validated_items = []
    for line in draft.items:
        catalog_item = get_catalog_item(line.id)
        if not catalog_item:
            raise HTTPException(status_code=400, detail=f"Servicio desconocido: {line.id}")
        validated_items.append(
            {
                "id": catalog_item["id"],
                "name": catalog_item["name"],
                "price": int(catalog_item["price"]),
            }
        )

    total = sum(item["price"] for item in validated_items)
    if draft.total and draft.total != total:
        raise HTTPException(status_code=400, detail="El total del pedido no coincide con el catálogo.")

    return {
        "id": draft.id or f"NOE-{uuid4().hex[:8].upper()}",
        "status": "borrador",
        "paymentProvider": "stripe",
        "stripeSessionId": None,
        "stripePaymentIntent": None,
        "emailNotifications": [],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "paidAt": None,
        "customer": draft.customer.model_dump(),
        "projectType": draft.projectType,
        "area": draft.area,
        "requirements": draft.requirements,
        "budget": draft.budget,
        "items": validated_items,
        "total": total,
    }
