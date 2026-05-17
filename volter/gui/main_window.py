from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from volter.gui.order_setup import OrderSetupScreen
from volter.gui.add_product import AddProductScreen
from volter.gui.weight_tracker import WeightTrackerScreen
from volter.gui.excel_export import ExcelExportScreen


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Volter — Taobao Parser")
        self.resize(900, 600)

        self.order_setup = OrderSetupScreen()
        self.add_product = AddProductScreen()
        self.weight_tracker = WeightTrackerScreen()
        self.excel_export = ExcelExportScreen()

        self._products: list[dict] = []

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.order_setup)
        self.stack.addWidget(self.add_product)
        self.stack.addWidget(self.excel_export)
        self.stack.addWidget(self.weight_tracker)
        main_layout.addWidget(self.stack, 4)

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.StyledPanel)
        sidebar.setFixedWidth(200)
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 20, 12, 20)

        title = QLabel("Volter", alignment=Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title)

        self.btn_setup = QPushButton("1. Настройка заказа")
        self.btn_setup.setFixedHeight(40)
        self.btn_setup.setCheckable(True)
        self.btn_setup.setChecked(True)
        layout.addWidget(self.btn_setup)

        self.btn_add = QPushButton("2. Добавить товар")
        self.btn_add.setFixedHeight(40)
        self.btn_add.setCheckable(True)
        layout.addWidget(self.btn_add)

        self.btn_export = QPushButton("3. Excel")
        self.btn_export.setFixedHeight(40)
        self.btn_export.setCheckable(True)
        layout.addWidget(self.btn_export)

        self.btn_weight = QPushButton("4. Вес и расчёт")
        self.btn_weight.setFixedHeight(40)
        self.btn_weight.setCheckable(True)
        layout.addWidget(self.btn_weight)

        layout.addStretch()

        self.btn_setup.clicked.connect(lambda: self._switch(0, self.btn_setup))
        self.btn_add.clicked.connect(lambda: self._switch(1, self.btn_add))
        self.btn_export.clicked.connect(lambda: self._switch(2, self.btn_export))
        self.btn_weight.clicked.connect(lambda: self._switch(3, self.btn_weight))

        return sidebar

    def _switch(self, index: int, btn: QPushButton) -> None:
        for b in (self.btn_setup, self.btn_add, self.btn_export, self.btn_weight):
            b.setChecked(False)
        btn.setChecked(True)
        self.stack.setCurrentIndex(index)

        if index == 2:
            self.excel_export._refresh_table()
            self.excel_export._refresh_weight_table()
        elif index == 3:
            try:
                rate = float(self.excel_export.rate_input.text())
            except ValueError:
                rate = 7.2
            self.weight_tracker.set_products(self._products, rate)

    def _connect_signals(self) -> None:
        self.order_setup.order_created.connect(self._on_order_created)
        self.add_product.product_parsed.connect(self._on_product_parsed)
        self.weight_tracker.weights_updated.connect(self._on_weights_updated)
        self.excel_export.go_to_setup.connect(lambda: self._switch(0, self.btn_setup))

    def _on_order_created(self, order_data: dict) -> None:
        self.add_product.set_order(order_data)
        self.weight_tracker.set_order(order_data)
        self.excel_export.set_order(order_data)
        self._switch(1, self.btn_add)

    def _on_product_parsed(self, product_data: dict) -> None:
        self._products.append(product_data)
        self.excel_export.add_product(product_data)

    def _on_weights_updated(self, weights: dict) -> None:
        self.excel_export.set_weights(weights)
