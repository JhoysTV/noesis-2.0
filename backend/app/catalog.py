CATALOG_ITEMS = {
    "arquitectonico": {
        "id": "arquitectonico",
        "name": "Diseño Arquitectónico",
        "price": 65000,
        "description": "Planos, concepto arquitectónico y documentación base.",
    },
    "interiores": {
        "id": "interiores",
        "name": "Diseño de Interiores",
        "price": 35000,
        "description": "Distribución, estilo, materiales y propuesta interior.",
    },
    "estructural": {
        "id": "estructural",
        "name": "Ingeniería Estructural",
        "price": 48000,
        "description": "Cálculos y memorias estructurales.",
    },
    "renders": {
        "id": "renders",
        "name": "Renders & Visualización",
        "price": 12000,
        "description": "Imágenes fotorrealistas y visualización 3D.",
    },
    "supervision": {
        "id": "supervision",
        "name": "Supervisión de Obras",
        "price": 42000,
        "description": "Dirección y control de calidad de obra.",
    },
    "consultoria": {
        "id": "consultoria",
        "name": "Consultoría & Asesoría",
        "price": 8500,
        "description": "Orientación técnica, permisos y presupuesto.",
    },
}


def list_catalog() -> list[dict]:
    return list(CATALOG_ITEMS.values())


def get_catalog_item(item_id: str) -> dict | None:
    return CATALOG_ITEMS.get(item_id)
