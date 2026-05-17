from __future__ import annotations

import time
from dataclasses import dataclass, field

from volter.models.product import Product


@dataclass
class Order:
    order_id: str = ""
    name: str = ""
    marketplace: str = "taobao"
    participants: list[str] = field(default_factory=list)
    products: list[Product] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    packaging_weight_g: float = 0.0
    shipping_rate_usd: float = 0.0
    status: str = "created"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.order_id:
            self.order_id = str(int(time.time() * 1000))
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    def add_product(self, product: Product, customer: str = "") -> None:
        if not customer and not product.customer:
            customer = "Не указан"
        if customer:
            product.customer = customer
            if customer not in self.participants:
                self.participants.append(customer)
        self.products.append(product)

    def remove_product(self, item_id: str) -> None:
        self.products = [p for p in self.products if p.item_id != item_id]

    def get_products_by_customer(self, name: str) -> list[Product]:
        return [p for p in self.products if p.customer == name]

    def get_customer_totals(self) -> dict[str, dict]:
        totals: dict[str, dict] = {}
        for p in self.products:
            name = p.customer or "Не указан"
            if name not in totals:
                totals[name] = {
                    "products": 0,
                    "weight": 0.0,
                    "product_cost": 0.0,
                    "shipping": 0.0,
                    "total": 0.0,
                }
            totals[name]["products"] += 1
            totals[name]["weight"] += p.weight_kg
            totals[name]["product_cost"] += p.price_yuan

        for name, t in totals.items():
            t["shipping"] = t["weight"] * self.shipping_rate_usd
            t["total"] = t["product_cost"] + t["shipping"]

        return totals

    def set_shipping_rate(self, rate: float) -> None:
        self.shipping_rate_usd = rate

    def calculate_shipping(self) -> dict[str, float]:
        shipping: dict[str, float] = {}
        for p in self.products:
            shipping[p.item_id] = p.weight_kg * self.shipping_rate_usd
        return shipping

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "name": self.name,
            "marketplace": self.marketplace,
            "participants": self.participants,
            "weights": self.weights,
            "packaging_weight_g": self.packaging_weight_g,
            "shipping_rate_usd": self.shipping_rate_usd,
            "products": [
                {
                    "item_id": p.item_id,
                    "title_zh": p.title_zh,
                    "title_ru": p.title_ru,
                    "price_yuan": p.price_yuan,
                    "shop": p.shop,
                    "image_url": p.image_url,
                    "image_path": p.image_path,
                    "sku_options": [
                        {"name": s.name, "values": s.values}
                        for s in p.sku_options
                    ],
                    "full_url": p.full_url,
                    "error": p.error,
                    "customer": p.customer,
                    "weight_kg": p.weight_kg,
                    "sku_selected": p.sku_selected,
                    "description": p.description,
                    "quantity": p.quantity,
                    "status": p.status,
                }
                for p in self.products
            ],
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Order:
        from volter.models.product import SkuOption

        products = []
        for pd in data.get("products", []):
            sku_opts = [
                SkuOption(name=s["name"], values=s["values"])
                for s in pd.get("sku_options", [])
            ]
            products.append(Product(
                item_id=pd.get("item_id", ""),
                title_zh=pd.get("title_zh", ""),
                title_ru=pd.get("title_ru", ""),
                price_yuan=pd.get("price_yuan", 0.0),
                shop=pd.get("shop", ""),
                image_url=pd.get("image_url", ""),
                image_path=pd.get("image_path", ""),
                sku_options=sku_opts,
                full_url=pd.get("full_url", ""),
                error=pd.get("error", ""),
                customer=pd.get("customer", ""),
                weight_kg=pd.get("weight_kg", 0.0),
                sku_selected=pd.get("sku_selected", ""),
                description=pd.get("description", ""),
                quantity=pd.get("quantity", 1),
                status=pd.get("status", True),
            ))

        return cls(
            order_id=data.get("order_id", ""),
            name=data.get("name", ""),
            marketplace=data.get("marketplace", "taobao"),
            participants=data.get("participants", []),
            weights=data.get("weights", {}),
            packaging_weight_g=data.get("packaging_weight_g", 0.0),
            shipping_rate_usd=data.get("shipping_rate_usd", 0.0),
            products=products,
            status=data.get("status", "created"),
            created_at=data.get("created_at", ""),
        )
