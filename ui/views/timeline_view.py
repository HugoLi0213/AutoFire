"""Custom view for the timeline table."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QMimeData, QModelIndex, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QTableView

from ui.models.timeline_model import TimelineModel


class TimelineView(QTableView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)

    def startDrag(self, supported_actions: Qt.DropActions) -> None:  # type: ignore[override]
        indexes = self.selectedIndexes()
        if not indexes:
            return
        drag = QDrag(self)
        mime = QMimeData()
        rows = sorted({index.row() for index in indexes})
        mime.setData("application/x-timeline-rows", bytes(",".join(map(str, rows)), "utf-8"))
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasFormat("application/x-timeline-rows"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasFormat("application/x-timeline-rows"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        model = self.model()
        if not isinstance(model, TimelineModel):
            super().dropEvent(event)
            return
        if event.mimeData().hasFormat("application/x-timeline-rows"):
            data_bytes = event.mimeData().data("application/x-timeline-rows").data()
            rows_data = data_bytes.decode()
            rows = [int(r) for r in rows_data.split(",") if r]
            target_index = self.indexAt(event.position().toPoint())
            target_row = target_index.row() if target_index.isValid() else len(model.events())
            model.reorder_rows(rows, target_row)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def selected_rows(self) -> List[int]:
        return sorted({index.row() for index in self.selectedIndexes()})