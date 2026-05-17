from __future__ import annotations

import logging
from pathlib import Path

import requests
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal, QThread

from volter.core.parser import TaobaoParser
from volter.core.translator import translate_zh, translate_list

logger = logging.getLogger(__name__)

IMAGES_DIR = Path.home() / ".volter" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


class ParseWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            parser = TaobaoParser(headless=False)
            try:
                product = parser.parse(self.url)
                if product.error:
                    self.error.emit(product.error)
                    return

                image_path = ""
                if product.image_url:
                    image_path = self._download_image(product.image_url, product.item_id)

                title_ru = translate_zh(product.title_zh) if product.title_zh else ""

                sku_options_ru = []
                sku_names_to_translate = [opt.name for opt in product.sku_options]
                sku_names_ru = translate_list(sku_names_to_translate)

                for i, opt in enumerate(product.sku_options):
                    values_ru = translate_list(opt.values)
                    sku_options_ru.append({"name": sku_names_ru[i], "values": values_ru})

                data = {
                    "item_id": product.item_id,
                    "title_zh": product.title_zh,
                    "title_ru": title_ru,
                    "price_yuan": product.price_yuan,
                    "shop": product.shop,
                    "image_url": product.image_url,
                    "image_path": image_path,
                    "sku_options": sku_options_ru,
                    "full_url": product.full_url,
                    "customer": "",
                    "sku_selected": "",
                    "description": "",
                    "quantity": 1,
                    "status": True,
                }
                self.finished.emit(data)
            finally:
                parser.close()
        except Exception as exc:
            self.error.emit(str(exc))

    @staticmethod
    def _download_image(url: str, item_id: str) -> str:
        try:
            img_url = url
            if "http:" not in img_url and "https:" not in img_url:
                img_url = "https:" + img_url

            resp = requests.get(img_url, timeout=10)
            if resp.status_code == 200:
                path = IMAGES_DIR / f"{item_id}.jpg"
                with open(path, "wb") as f:
                    f.write(resp.content)
                return str(path)
        except Exception as exc:
            logger.warning("Failed to download image: %s", exc)
        return ""


class AddProductScreen(QWidget):
    product_parsed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._order_data: dict = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Добавить товар", alignment=Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        self.order_label = QLabel("Заказ не создан")
        self.order_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.order_label)

        url_layout = QVBoxLayout()
        url_layout.addWidget(QLabel("Ссылка на товар Taobao:"))

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://item.taobao.com/item.htm?id=...")
        url_row.addWidget(self.url_input)

        self.parse_btn = QPushButton("Парсить")
        self.parse_btn.setFixedWidth(120)
        self.parse_btn.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #2196F3; color: white;")
        self.parse_btn.clicked.connect(self._start_parse)
        url_row.addWidget(self.parse_btn)

        url_layout.addLayout(url_row)
        layout.addLayout(url_layout)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.product_group = QGroupBox("Результат парсинга")
        product_layout = QVBoxLayout(self.product_group)

        self.product_info = QLabel("Товар ещё не добавлен")
        self.product_info.setWordWrap(True)
        self.product_info.setStyleSheet("padding: 8px;")
        product_layout.addWidget(self.product_info)

        self._sku_combos: list[QComboBox] = []
        self._sku_labels: list[QLabel] = []
        self._sku_container = QWidget()
        self._sku_layout = QVBoxLayout(self._sku_container)
        self._sku_layout.setContentsMargins(0, 0, 0, 0)
        self._sku_layout.setSpacing(8)
        product_layout.addWidget(self._sku_container)

        customer_row = QHBoxLayout()
        customer_row.addWidget(QLabel("Участник:"))
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(200)
        customer_row.addWidget(self.customer_combo)
        customer_row.addStretch()
        product_layout.addLayout(customer_row)

        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("Описание:"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Авто из SKU, можно редактировать")
        self.desc_input.setStyleSheet("background-color: #fff9c4; padding: 4px;")
        desc_layout.addWidget(self.desc_input)
        product_layout.addLayout(desc_layout)

        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("Кол-во:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 999)
        self.qty_spin.setValue(1)
        self.qty_spin.setFixedWidth(80)
        qty_layout.addWidget(self.qty_spin)
        qty_layout.addStretch()
        product_layout.addLayout(qty_layout)

        self.status_check = QCheckBox("Есть в наличии")
        self.status_check.setChecked(True)
        self.status_check.setStyleSheet("font-size: 14px;")
        product_layout.addWidget(self.status_check)

        self.add_btn = QPushButton("Добавить в заказ")
        self.add_btn.setFixedHeight(40)
        self.add_btn.setStyleSheet("font-size: 14px; background-color: #4CAF50; color: white;")
        self.add_btn.clicked.connect(self._add_to_order)
        self.add_btn.setEnabled(False)
        product_layout.addWidget(self.add_btn)

        layout.addWidget(self.product_group)

        layout.addWidget(QLabel("Товары в заказе:"))
        self.product_list = QListWidget()
        self.product_list.setFixedHeight(150)
        layout.addWidget(self.product_list)

        layout.addStretch()

        self._last_product: dict | None = None
        self._worker: ParseWorker | None = None

    def set_order(self, order_data: dict) -> None:
        self._order_data = order_data
        self.order_label.setText(f"Заказ: {order_data['name']}")
        self.order_label.setStyleSheet("color: #333; font-weight: bold;")

        self.customer_combo.clear()
        for p in order_data.get("participants", []):
            self.customer_combo.addItem(p)

    def _start_parse(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Ошибка", "Введите ссылку на товар")
            return

        self.parse_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Парсинг и перевод...")

        self._worker = ParseWorker(url)
        self._worker.finished.connect(self._on_parse_finished)
        self._worker.error.connect(self._on_parse_error)
        self._worker.start()

    def _on_parse_finished(self, data: dict) -> None:
        self.parse_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.status_label.setText("Готово!")

        self._last_product = data

        self._clear_sku_combos()

        sku_options = data.get("sku_options", [])
        if sku_options:
            for opt in sku_options:
                label = QLabel(opt["name"] + ":")
                label.setStyleSheet("font-weight: bold;")
                combo = QComboBox()
                combo.setMinimumWidth(200)
                for val in opt.get("values", []):
                    combo.addItem(val)
                combo.currentTextChanged.connect(self._update_sku_selection)
                self._sku_layout.addWidget(label)
                self._sku_layout.addWidget(combo)
                self._sku_labels.append(label)
                self._sku_combos.append(combo)
        else:
            self._sku_combos = []

        self._update_sku_selection()

        self.product_info.setText(
            f"<b>RU:</b> {data['title_ru']}<br>"
            f"<b>ZH:</b> {data['title_zh']}<br>"
            f"Цена: ¥{data['price_yuan']}<br>"
            f"Магазин: {data['shop']}"
        )
        self.add_btn.setEnabled(True)

    def _on_parse_error(self, error: str) -> None:
        self.parse_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.status_label.setText(f"Ошибка: {error}")
        QMessageBox.critical(self, "Ошибка парсинга", error)

    def _clear_sku_combos(self) -> None:
        for label in self._sku_labels:
            label.deleteLater()
        for combo in self._sku_combos:
            combo.deleteLater()
        self._sku_labels.clear()
        self._sku_combos.clear()

    def _update_sku_selection(self) -> None:
        if not self._sku_combos:
            self.desc_input.setText("")
            return
        parts = [combo.currentText() for combo in self._sku_combos if combo.count() > 0]
        combined = ", ".join(parts)
        self.desc_input.setText(combined)

    def _add_to_order(self) -> None:
        if not self._last_product:
            return

        sku_parts = [combo.currentText() for combo in self._sku_combos if combo.count() > 0]
        self._last_product["customer"] = self.customer_combo.currentText()
        self._last_product["sku_selected"] = ", ".join(sku_parts)
        self._last_product["description"] = self.desc_input.text().strip()
        self._last_product["quantity"] = self.qty_spin.value()
        self._last_product["status"] = self.status_check.isChecked()

        self.product_parsed.emit(self._last_product)

        title = self._last_product.get("title_ru", "") or self._last_product["title_zh"]
        status_str = "✓" if self._last_product["status"] else "✗"
        item_text = f"{status_str} {title[:40]}... — ¥{self._last_product['price_yuan']} × {self._last_product['quantity']} ({self._last_product['customer']})"
        self.product_list.addItem(item_text)

        self.url_input.clear()
        self.desc_input.clear()
        self.qty_spin.setValue(1)
        self.status_check.setChecked(True)
        self._clear_sku_combos()
        self.product_info.setText("Товар ещё не добавлен")
        self.add_btn.setEnabled(False)
        self._last_product = None
        self.status_label.setText("")
