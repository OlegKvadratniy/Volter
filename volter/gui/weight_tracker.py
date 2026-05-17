from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal


class WeightDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добавить вес")
        self.setFixedSize(250, 130)

        layout = QFormLayout(self)

        self.grams_input = QLineEdit()
        self.grams_input.setPlaceholderText("Граммы")
        self.grams_input.returnPressed.connect(self.accept)
        layout.addRow("Вес (г):", self.grams_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_grams(self) -> int:
        try:
            return int(self.grams_input.text())
        except ValueError:
            return 0


class WeightTrackerScreen(QWidget):
    weights_updated = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._order_data: dict = {}
        self._weights: dict[str, float] = {}
        self._packaging_weight_g: float = 0.0
        self._shipping_rate_usd: float = 0.0
        self._products: list[dict] = []
        self._yuan_rate: float = 7.2
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Вес и расчёт", alignment=Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        self.order_label = QLabel("Заказ не создан")
        self.order_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.order_label)

        settings_group = QWidget()
        settings_layout = QHBoxLayout(settings_group)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        pkg_layout = QHBoxLayout()
        pkg_layout.addWidget(QLabel("Вес упаковки (г):"))
        self.pkg_input = QLineEdit("0")
        self.pkg_input.setFixedWidth(80)
        self.pkg_input.editingFinished.connect(self._on_settings_changed)
        pkg_layout.addWidget(self.pkg_input)
        pkg_layout.addStretch()
        settings_layout.addLayout(pkg_layout)

        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("Тариф доставки ($/кг):"))
        self.rate_input = QLineEdit("0")
        self.rate_input.setFixedWidth(80)
        self.rate_input.editingFinished.connect(self._on_settings_changed)
        rate_layout.addWidget(self.rate_input)
        rate_layout.addStretch()
        settings_layout.addLayout(rate_layout)

        layout.addWidget(settings_group)

        self.participants_layout = QVBoxLayout()
        self.participants_layout.setSpacing(12)
        layout.addLayout(self.participants_layout)

        self.total_label = QLabel("Итого: 0 кг | Доставка: $0.00")
        self.total_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 12px; background-color: #e3f2fd; border-radius: 4px;")
        self.total_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.total_label)

        layout.addStretch()

    def set_order(self, order_data: dict) -> None:
        self._order_data = order_data
        self._weights = order_data.get("weights", {}).copy()
        self._packaging_weight_g = order_data.get("packaging_weight_g", 0.0)
        self._shipping_rate_usd = order_data.get("shipping_rate_usd", 0.0)
        self.pkg_input.setText(str(int(self._packaging_weight_g)))
        self.rate_input.setText(str(self._shipping_rate_usd))
        self.order_label.setText(f"Заказ: {order_data['name']}")
        self.order_label.setStyleSheet("color: #333; font-weight: bold;")
        self._refresh()

    def set_products(self, products: list[dict], yuan_rate: float) -> None:
        self._products = products
        self._yuan_rate = yuan_rate
        self._refresh()

    def _on_settings_changed(self) -> None:
        try:
            self._packaging_weight_g = float(self.pkg_input.text())
        except ValueError:
            self._packaging_weight_g = 0.0
        try:
            self._shipping_rate_usd = float(self.rate_input.text())
        except ValueError:
            self._shipping_rate_usd = 0.0
        self._refresh()
        self._emit_weights()

    def _calc_customer_cost(self, name: str) -> float:
        total = 0.0
        for p in self._products:
            if p.get("customer") == name:
                qty = p.get("quantity", 1)
                total += p["price_yuan"] * qty
        return round(total / self._yuan_rate, 2) if self._yuan_rate > 0 else 0.0

    def _refresh(self) -> None:
        while self.participants_layout.count():
            item = self.participants_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        participants = self._order_data.get("participants", [])
        for name in participants:
            row = self._create_participant_row(name)
            self.participants_layout.addWidget(row)

        self._update_total()

    def _create_participant_row(self, name: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        name_label.setFixedWidth(120)
        layout.addWidget(name_label)

        personal_kg = self._weights.get(name, 0.0)
        participants = self._order_data.get("participants", [])
        pkg_share = self._packaging_weight_g / 1000.0 / len(participants) if participants else 0.0
        total_kg = personal_kg + pkg_share
        delivery = total_kg * self._shipping_rate_usd
        goods_cost = self._calc_customer_cost(name)
        grand_total = goods_cost + delivery

        info_label = QLabel(f"{personal_kg:.1f} кг | Товары: ${goods_cost:.2f} | Доставка: ${delivery:.2f}")
        info_label.setStyleSheet("font-size: 14px; color: #1976D2;")
        layout.addWidget(info_label)

        total_label = QLabel(f"Итого: ${grand_total:.2f}")
        total_label.setStyleSheet("font-size: 15px; color: #e65100; font-weight: bold;")
        total_label.setFixedWidth(120)
        layout.addWidget(total_label)

        add_btn = QPushButton("＋")
        add_btn.setFixedWidth(40)
        add_btn.setStyleSheet("font-size: 18px; font-weight: bold; background-color: #4CAF50; color: white;")
        add_btn.clicked.connect(lambda: self._add_weight(name))
        layout.addWidget(add_btn)

        layout.addStretch()

        return row

    def _add_weight(self, name: str) -> None:
        dialog = WeightDialog(self)
        dialog.grams_input.setFocus()
        if dialog.exec() == QDialog.Accepted:
            grams = dialog.get_grams()
            if grams > 0:
                current = self._weights.get(name, 0.0)
                new_weight = current + grams / 1000.0
                self._weights[name] = new_weight
                self._refresh()
                self._emit_weights()

    def _update_total(self) -> None:
        participants = self._order_data.get("participants", [])
        personal_total = sum(self._weights.values())
        pkg_share = self._packaging_weight_g / 1000.0 / len(participants) if participants else 0.0
        pkg_total = pkg_share * len(participants)
        grand_weight = personal_total + pkg_total
        delivery_total = grand_weight * self._shipping_rate_usd

        total_goods = 0.0
        for name in participants:
            total_goods += self._calc_customer_cost(name)

        self.total_label.setText(f"Итого: {grand_weight:.2f} кг | Товары: ${total_goods:.2f} | Доставка: ${delivery_total:.2f} | Все: ${total_goods + delivery_total:.2f}")

    def _emit_weights(self) -> None:
        self.weights_updated.emit({
            "weights": self._weights,
            "packaging_weight_g": self._packaging_weight_g,
            "shipping_rate_usd": self._shipping_rate_usd,
        })

    def get_weights(self) -> dict[str, float]:
        return self._weights

    def get_packaging_weight_g(self) -> float:
        return self._packaging_weight_g

    def get_shipping_rate_usd(self) -> float:
        return self._shipping_rate_usd
