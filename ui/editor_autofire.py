"""Editor widget for configuring AutoFire bindings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.types import AutoFireBinding, generate_id


@dataclass
class AutoFireInput:
    id: str
    trigger_key: str
    output_key: str
    interval_ms: int
    pass_through: bool


class AutoFireEditor(QGroupBox):
    bindingSelected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("AutoFire")
        self._build_ui()
        self._bindings: List[AutoFireBinding] = []

    # UI ----------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Trigger", "Output", "Interval (ms)", "Pass-through"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.trigger_edit = QLineEdit()
        self.trigger_edit.setPlaceholderText("Press or type key (e)")
        form.addRow("Trigger", self.trigger_edit)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Press or type key (r)")
        form.addRow("Output", self.output_edit)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1000)
        self.interval_spin.setValue(50)
        form.addRow("Interval (ms)", self.interval_spin)

        self.pass_check = QCheckBox("Allow trigger key to pass through")
        form.addRow("Pass-through", self.pass_check)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.save_button = QPushButton("Add / Update")
        button_row.addWidget(self.save_button)
        self.remove_button = QPushButton("Remove")
        button_row.addWidget(self.remove_button)
        button_row.addStretch()
        layout.addLayout(button_row)

    # Data --------------------------------------------------------------------
    def set_bindings(self, bindings: List[AutoFireBinding]) -> None:
        self._bindings = list(bindings)
        self._refresh_table()
        if self.table.rowCount():
            self.table.selectRow(0)
        else:
            self.clear_fields()

    def bindings(self) -> List[AutoFireBinding]:
        return list(self._bindings)

    def selected_binding(self) -> Optional[AutoFireBinding]:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        row = rows[0].row()
        if 0 <= row < len(self._bindings):
            return self._bindings[row]
        return None

    def collect_input(self) -> AutoFireInput:
        binding = self.selected_binding()
        binding_id = binding.id if binding else generate_id()
        trigger = self.trigger_edit.text().strip().lower()
        output = self.output_edit.text().strip().lower()
        interval = self.interval_spin.value()
        pass_through = self.pass_check.isChecked()
        return AutoFireInput(
            id=binding_id,
            trigger_key=trigger,
            output_key=output,
            interval_ms=interval,
            pass_through=pass_through,
        )

    def update_binding(self, data: AutoFireInput) -> AutoFireBinding:
        binding = AutoFireBinding(
            id=data.id,
            trigger_key=data.trigger_key,
            output_key=data.output_key,
            interval_ms=data.interval_ms,
            pass_through_trigger=data.pass_through,
            mode="whileHeld",
        )
        existing = next((b for b in self._bindings if b.id == binding.id), None)
        if existing:
            index = self._bindings.index(existing)
            self._bindings[index] = binding
        else:
            self._bindings.append(binding)
        self._refresh_table()
        self._select_binding(binding.id)
        return binding

    def remove_selected(self) -> Optional[AutoFireBinding]:
        binding = self.selected_binding()
        if binding:
            self._bindings = [b for b in self._bindings if b.id != binding.id]
            self._refresh_table()
            if self._bindings:
                self._select_binding(self._bindings[0].id)
            else:
                self.clear_fields()
        return binding

    def load_binding_into_form(self, binding: AutoFireBinding) -> None:
        self.trigger_edit.setText(binding.trigger_key.upper())
        self.output_edit.setText(binding.output_key.upper())
        self.interval_spin.setValue(binding.interval_ms)
        self.pass_check.setChecked(binding.pass_through_trigger)

    def clear_fields(self) -> None:
        self.trigger_edit.clear()
        self.output_edit.clear()
        self.interval_spin.setValue(50)
        self.pass_check.setChecked(False)

    # Internal -----------------------------------------------------------------
    def _refresh_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._bindings))
        for row, binding in enumerate(self._bindings):
            self.table.setItem(row, 0, QTableWidgetItem(binding.trigger_key.upper()))
            self.table.setItem(row, 1, QTableWidgetItem(binding.output_key.upper()))
            self.table.setItem(row, 2, QTableWidgetItem(str(binding.interval_ms)))
            self.table.setItem(row, 3, QTableWidgetItem("ON" if binding.pass_through_trigger else "OFF"))
            for column in range(4):
                item = self.table.item(row, column)
                if item:
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
        self.table.blockSignals(False)

    def _on_selection_changed(self) -> None:
        binding = self.selected_binding()
        if binding:
            self.load_binding_into_form(binding)
            self.bindingSelected.emit(binding.id)

    def _select_binding(self, binding_id: str) -> None:
        for row, binding in enumerate(self._bindings):
            if binding.id == binding_id:
                self.table.selectRow(row)
                break