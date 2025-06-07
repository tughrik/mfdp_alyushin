from app.items import ITEMS_MAPPING


def get_product_info(product_id):
    info = ITEMS_MAPPING.get(product_id, {"category": "Unknown", "emoji": "❓"})
    return f"{info['emoji']} {product_id} ({info['category']})"
