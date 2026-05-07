CATALOG_ITEMS = {
    "arquitectonico": {
        "id": "arquitectonico",
        "name": "Diseño Arquitectónico",
        "price": 65000,
        "description": "Concepto, distribución, planos base y lineamientos arquitectónicos en modalidad remota.",
    },
    "interiores": {
        "id": "interiores",
        "name": "Diseño de Interiores",
        "price": 35000,
        "description": "Distribución, estilo, paleta, materiales, mobiliario y visualización en modalidad remota.",
    },
}


def list_catalog() -> list[dict]:
    return list(CATALOG_ITEMS.values())


def get_catalog_item(item_id: str) -> dict | None:
    return CATALOG_ITEMS.get(item_id)
