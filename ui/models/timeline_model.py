"""Qt model representing macro events in a tabular timeline."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from core.types import KeyEvent, MacroEvent, MouseEvent

COLUMN_HEADERS = [
    "#",
    "Type",
    "Device",
    "Action",
    "Key/Button",
    "X",
    "Y",
    "Delta",
    "Delay (ms)",
]


class TimelineModel(QAbstractTableModel):
    def __init__(self, events: Optional[List[MacroEvent]] = None, parent=None) -> None:
        super().__init__(parent)
        self._events: List[MacroEvent] = events if events is not None else []

    # Qt overrides -----------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._events)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(COLUMN_HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid() or not (0 <= index.row() < len(self._events)):
            return None
        row = index.row()
        event = self._events[row]
        column = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._data_for_column(event, column, row)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMN_HEADERS[section]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(section + 1)
        return None

    def flags(self, index: QModelIndex):  # type: ignore[override]
        base = super().flags(index)
        if index.column() == 8 and index.isValid():
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole):  # type: ignore[override]
        if role != Qt.EditRole or index.column() != 8:
            return False
        try:
            delay = int(value)
        except (TypeError, ValueError):
            return False
        if delay < 0:
            return False
        event = self._events[index.row()]
        event.delay_ms = delay
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        return True

    # Helpers ----------------------------------------------------------------------
    def events(self) -> List[MacroEvent]:
        return list(self._events)

    def set_events(self, events: List[MacroEvent]) -> None:
        self.beginResetModel()
        self._events = events
        self.endResetModel()

    def insert_event(self, position: int, event: MacroEvent) -> None:
        self.beginInsertRows(QModelIndex(), position, position)
        self._events.insert(position, event)
        self.endInsertRows()

    def remove_rows(self, rows: List[int]) -> None:
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self._events):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._events[row]
                self.endRemoveRows()

    def move_row(self, source: int, target: int) -> None:
        if source == target or not (0 <= source < len(self._events)):
            return
        target = max(0, min(target, len(self._events) - 1))
        if not self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), target + (1 if target > source else 0)):
            return
        event = self._events.pop(source)
        self._events.insert(target, event)
        self.endMoveRows()

    def reorder_rows(self, rows: List[int], target: int) -> None:
        if not rows or not self._events:
            return
        unique_rows = sorted({row for row in rows if 0 <= row < len(self._events)})
        if not unique_rows:
            return
        selection = [self._events[row] for row in unique_rows]
        original_target = max(0, min(target, len(self._events)))
        self.beginResetModel()
        for row in reversed(unique_rows):
            del self._events[row]
        adjusted_target = original_target
        for row in unique_rows:
            if row < original_target:
                adjusted_target -= 1
        adjusted_target = max(0, min(adjusted_target, len(self._events)))
        for offset, event in enumerate(selection):
            self._events.insert(adjusted_target + offset, event)
        self.endResetModel()

    def normalize_delays(self, value: int) -> None:
        for event in self._events[1:]:
            event.delay_ms = value
        if self._events:
            self._events[0].delay_ms = 0
        top_left = self.index(0, 8)
        bottom_right = self.index(max(0, len(self._events) - 1), 8)
        self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.EditRole])

    def scale_delays(self, factor: float) -> None:
        for event in self._events:
            event.delay_ms = max(0, int(round(event.delay_ms * factor)))
        if self._events:
            self._events[0].delay_ms = 0
        top_left = self.index(0, 8)
        bottom_right = self.index(max(0, len(self._events) - 1), 8)
        self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.EditRole])

    def _data_for_column(self, event: MacroEvent, column: int, row: int):
        if column == 0:
            return row + 1
        if column == 1:
            return event.__class__.__name__
        if column == 2:
            return "Keyboard" if isinstance(event, KeyEvent) else "Mouse"
        if column == 3:
            if isinstance(event, KeyEvent):
                return event.action.value
            if isinstance(event, MouseEvent):
                return event.action.value
        if column == 4:
            if isinstance(event, KeyEvent):
                return event.key
            if isinstance(event, MouseEvent):
                return event.button or ""
        if column == 5:
            if isinstance(event, MouseEvent) and event.x is not None:
                return event.x
            return ""
        if column == 6:
            if isinstance(event, MouseEvent) and event.y is not None:
                return event.y
            return ""
        if column == 7:
            if isinstance(event, MouseEvent) and event.delta is not None:
                return event.delta
            return ""
        if column == 8:
            return event.delay_ms
        return ""