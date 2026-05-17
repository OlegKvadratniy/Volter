from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkuOption:
    name: str
    values: list[str] = field(default_factory=list)


@dataclass
class Product:
    item_id: str = ""
    title_zh: str = ""
    title_ru: str = ""
    price_yuan: float = 0.0
    shop: str = ""
    image_url: str = ""
    image_path: str = ""
    sku_options: list[SkuOption] = field(default_factory=list)
    full_url: str = ""
    error: str = ""
    customer: str = ""
    weight_kg: float = 0.0
    sku_selected: str = ""
    description: str = ""
    quantity: int = 1
    status: bool = True
