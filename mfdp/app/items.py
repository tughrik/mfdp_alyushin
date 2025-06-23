import pandas as pd
from typing import Dict

ITEMS_MAPPING: Dict[int, Dict[str, str]] = {}


def load_items_mapping(path: str = "data/dict_items.xls"):
    global ITEMS_MAPPING
    df = pd.read_excel(path)
    for _, row in df.iterrows():
        product_id = int(row["PRODUCT_ID"])
        category = row["DEPARTMENT"]
        emoji = row["EMODZI"]
        ITEMS_MAPPING[product_id] = {"category": category, "emoji": emoji}
    print(f"Загружено {len(ITEMS_MAPPING)} товаров из справочника")
