from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal


class OrderSetupScreen(QWidget):
    order_created = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Настройка заказа", alignment=Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Form
        form = QFormLayout()
        form.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Май 2026")
        form.addRow("Название:", self.name_input)

        self.marketplace_input = QLineEdit("taobao")
        self.marketplace_input.setReadOnly(True)
        form.addRow("Маркетплейс:", self.marketplace_input)

        layout.addLayout(form)

        # Participants
        participant_layout = QVBoxLayout()
        participant_layout.addWidget(QLabel("Участники:"))

        self.participant_input = QLineEdit()
        self.participant_input.setPlaceholderText("Введите имя и нажмите Enter")
        self.participant_input.returnPressed.connect(self._add_participant)

        add_btn = QPushButton("Добавить")
        add_btn.setFixedWidth(100)
        add_btn.clicked.connect(self._add_participant)

        input_row = QHBoxLayout()
        input_row.addWidget(self.participant_input)
        input_row.addWidget(add_btn)
        participant_layout.addLayout(input_row)

        self.participant_list = QListWidget()
        self.participant_list.setFixedHeight(150)
        participant_layout.addWidget(self.participant_list)

        layout.addLayout(participant_layout)

        # Create button
        self.create_btn = QPushButton("Создать заказ")
        self.create_btn.setFixedHeight(45)
        self.create_btn.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #4CAF50; color: white;")
        self.create_btn.clicked.connect(self._create_order)
        layout.addWidget(self.create_btn)

        layout.addStretch()

    def _add_participant(self) -> None:
        name = self.participant_input.text().strip()
        if name:
            self.participant_list.addItem(name)
            self.participant_input.clear()

    def _create_order(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            name = f"Заказ_{self.participant_list.count()}"

        participants = [
            self.participant_list.item(i).text()
            for i in range(self.participant_list.count())
        ]

        order_data = {
            "name": name,
            "marketplace": "taobao",
            "participants": participants,
        }
        self.order_created.emit(order_data)
