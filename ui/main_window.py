"""Main window for the macro application using PySide6."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

import keyboard
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.actions import SystemActionExecutor
from core.bindings import BindingRegistry
from core.bindings_autofire import AutoFireBindingRegistry
from core.player import MacroPlayer
from core.recorder import MacroRecorder, RecorderConfig
from core.storage import StorageError, load_state, save_state
from core.types import (
    AppState,
    Binding,
    BindingType,
    DelayStrategy,
    Macro,
    PlaybackMode,
    PlaybackOptions,
    Profile,
    AutoFireBinding,
    generate_id,
    find_profile,
)
from ui.models.timeline_model import TimelineModel
from ui.views.timeline_view import TimelineView
from ui.editor_autofire import AutoFireEditor

logger = logging.getLogger(__name__)

SYSTEM_ACTION_IDS = [
    ("volume_up", "Volume Up"),
    ("volume_down", "Volume Down"),
    ("volume_mute", "Mute"),
    ("minimize_window", "Minimize Window"),
    ("restore_window", "Restore Window"),
]

DELAY_PRESETS = [10, 25, 50, 100]


class MainWindow(QMainWindow):
    def __init__(self, state_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("Macro Studio")
        self.resize(1400, 900)
        self.state_path = state_path
        self.state = self._load_or_create_state(state_path)
        self._normalize_state()
        self.recorder = MacroRecorder()
        self.player = MacroPlayer(state_callback=self._on_player_state)
        self.system_actions = SystemActionExecutor()
        self.binding_registry = BindingRegistry(
            player=self.player,
            system_actions=self.system_actions,
            macro_resolver=self._resolve_macro,
            on_error=self._set_status,
        )
        self.autofire_registry = AutoFireBindingRegistry(
            keyboard_module=keyboard,
            now=time.monotonic,
            sleep=time.sleep,
            status_callback=self._set_autofire_status,
            error_callback=self._on_autofire_error,
            register_emergency=False,
        )

        self.timeline_model = TimelineModel()
        self.timeline_view = TimelineView()
        self.timeline_view.setModel(self.timeline_model)
        if self.timeline_view.selectionModel() is not None:
            self.timeline_view.selectionModel().selectionChanged.connect(self._on_timeline_selection)
        self.timeline_model.modelReset.connect(self._on_model_reset)
        self.timeline_model.dataChanged.connect(self._on_timeline_data_changed)

        self._emergency_hotkey_id = keyboard.add_hotkey(
            "ctrl+alt+esc", self._on_emergency_stop, suppress=False
        )

        self._build_ui()
        self._refresh_profiles()
        self._refresh_bindings_table()
        self._refresh_autofire_editor()
        self._update_transport_from_macro(self._current_macro())

    # UI construction -------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(8, 8, 8, 8)
        central_layout.setSpacing(6)

        self._build_header(central_layout)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(1, 1)
        central_layout.addWidget(splitter)

        self.status_label = QLabel("Ready")
        central_layout.addWidget(self.status_label)
        self.setCentralWidget(central)

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QHBoxLayout()
        header.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        header.addWidget(self.profile_combo)

        self.new_profile_button = QPushButton("New Profile")
        self.new_profile_button.clicked.connect(self._create_profile)
        header.addWidget(self.new_profile_button)
        self.duplicate_profile_button = QPushButton("Duplicate")
        self.duplicate_profile_button.clicked.connect(self._duplicate_profile)
        header.addWidget(self.duplicate_profile_button)
        self.delete_profile_button = QPushButton("Delete")
        self.delete_profile_button.clicked.connect(self._delete_profile)
        header.addWidget(self.delete_profile_button)

        header.addSpacing(20)
        header.addWidget(QLabel("Delay Presets:"))
        for preset in DELAY_PRESETS:
            button = QPushButton(f"{preset} ms")
            button.clicked.connect(lambda _, value=preset: self._apply_delay_preset(value))
            header.addWidget(button)
        actual_button = QPushButton("Actual")
        actual_button.clicked.connect(self._use_actual_delay)
        header.addWidget(actual_button)

        header.addSpacing(20)
        header.addWidget(QLabel("Scale %:"))
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(50, 200)
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        header.addWidget(self.scale_slider)
        self.scale_label = QLabel("100%")
        header.addWidget(self.scale_label)

        header.addSpacing(20)
        self.emergency_label = QLabel("Emergency Ready")
        header.addWidget(self.emergency_label)
        header.addStretch()
        layout.addLayout(header)

    def _build_left_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Macros"))
        self.macro_list = QListWidget()
        self.macro_list.currentRowChanged.connect(self._on_macro_selected)
        layout.addWidget(self.macro_list)

        macro_buttons = QHBoxLayout()
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._add_macro)
        macro_buttons.addWidget(add_button)
        dup_button = QPushButton("Duplicate")
        dup_button.clicked.connect(self._duplicate_macro)
        macro_buttons.addWidget(dup_button)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self._delete_macro)
        macro_buttons.addWidget(delete_button)
        layout.addLayout(macro_buttons)

        rename_layout = QHBoxLayout()
        rename_layout.addWidget(QLabel("Name:"))
        self.macro_name_edit = QLineEdit()
        self.macro_name_edit.editingFinished.connect(self._rename_macro)
        rename_layout.addWidget(self.macro_name_edit)
        layout.addLayout(rename_layout)

        blocklist_layout = QHBoxLayout()
        blocklist_layout.addWidget(QLabel("Blocklist:"))
        self.blocklist_edit = QLineEdit()
        self.blocklist_edit.editingFinished.connect(self._update_blocklist)
        blocklist_layout.addWidget(self.blocklist_edit)
        layout.addLayout(blocklist_layout)

        return container

    def _build_center_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.timeline_view)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Timeline Tools:"))
        insert_key_down = QPushButton("Insert Key Down")
        insert_key_down.clicked.connect(lambda: self._insert_key_event("down"))
        toolbar.addWidget(insert_key_down)
        insert_key_up = QPushButton("Insert Key Up")
        insert_key_up.clicked.connect(lambda: self._insert_key_event("up"))
        toolbar.addWidget(insert_key_up)
        insert_click = QPushButton("Insert Click")
        insert_click.clicked.connect(self._insert_mouse_click)
        toolbar.addWidget(insert_click)
        insert_move = QPushButton("Insert Move")
        insert_move.clicked.connect(self._insert_mouse_move)
        toolbar.addWidget(insert_move)
        insert_wheel = QPushButton("Insert Wheel")
        insert_wheel.clicked.connect(self._insert_mouse_wheel)
        toolbar.addWidget(insert_wheel)
        normalize_button = QPushButton("Normalize")
        normalize_button.clicked.connect(self._prompt_normalize)
        toolbar.addWidget(normalize_button)
        layout.addLayout(toolbar)

        transport = QHBoxLayout()
        self.record_button = QPushButton("Record")
        self.record_button.clicked.connect(self._start_recording)
        transport.addWidget(self.record_button)

        self.stop_record_button = QPushButton("Stop Rec")
        self.stop_record_button.clicked.connect(self._stop_recording)
        transport.addWidget(self.stop_record_button)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self._play_macro)
        transport.addWidget(self.play_button)

        self.stop_play_button = QPushButton("Stop")
        self.stop_play_button.clicked.connect(self._stop_playback)
        transport.addWidget(self.stop_play_button)

        transport.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        for mode in PlaybackMode:
            self.mode_combo.addItem(mode.name, mode)
        transport.addWidget(self.mode_combo)

        transport.addWidget(QLabel("Repeat:"))
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(1, 999)
        transport.addWidget(self.repeat_spin)

        transport.addWidget(QLabel("Speed:"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setDecimals(2)
        self.speed_spin.setRange(0.1, 3.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.0)
        transport.addWidget(self.speed_spin)

        self.include_keyboard_check = QCheckBox("Keyboard")
        self.include_keyboard_check.setChecked(True)
        transport.addWidget(self.include_keyboard_check)
        self.include_mouse_check = QCheckBox("Mouse")
        self.include_mouse_check.setChecked(True)
        transport.addWidget(self.include_mouse_check)

        transport.addStretch()
        layout.addLayout(transport)
        return container

    def _build_right_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        properties_group = QGroupBox("Event Properties")
        prop_layout = QFormLayout(properties_group)
        self.prop_type = QLabel("-")
        prop_layout.addRow("Type", self.prop_type)
        self.prop_action = QLabel("-")
        prop_layout.addRow("Action", self.prop_action)
        self.prop_key = QLabel("-")
        prop_layout.addRow("Key/Button", self.prop_key)
        self.prop_position = QLabel("-")
        prop_layout.addRow("Position", self.prop_position)
        self.prop_delay = QLabel("-")
        prop_layout.addRow("Delay", self.prop_delay)
        layout.addWidget(properties_group)

        bindings_group = QGroupBox("Bindings")
        bindings_layout = QVBoxLayout(bindings_group)

        self.binding_table = QTableWidget(0, 4)
        self.binding_table.setHorizontalHeaderLabels(["Hotkey", "Type", "Target", "Mode"])
        self.binding_table.verticalHeader().setVisible(False)
        self.binding_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.binding_table.itemSelectionChanged.connect(self._on_binding_selected)
        bindings_layout.addWidget(self.binding_table)

        form = QFormLayout()
        self.binding_hotkey_edit = QLineEdit()
        form.addRow("Hotkey", self.binding_hotkey_edit)

        self.binding_type_combo = QComboBox()
        for btype in BindingType:
            self.binding_type_combo.addItem(btype.name.title(), btype)
        self.binding_type_combo.currentIndexChanged.connect(self._on_binding_type_changed)
        form.addRow("Type", self.binding_type_combo)

        self.binding_target_combo = QComboBox()
        form.addRow("Target", self.binding_target_combo)

        self.binding_payload_edit = QLineEdit()
        form.addRow("Text/Path", self.binding_payload_edit)

        self.binding_mode_combo = QComboBox()
        for mode in PlaybackMode:
            self.binding_mode_combo.addItem(mode.name, mode)
        form.addRow("Mode", self.binding_mode_combo)

        self.binding_repeat_spin = QSpinBox()
        self.binding_repeat_spin.setRange(1, 999)
        form.addRow("Repeat", self.binding_repeat_spin)

        self.binding_speed_spin = QDoubleSpinBox()
        self.binding_speed_spin.setDecimals(2)
        self.binding_speed_spin.setRange(0.1, 3.0)
        self.binding_speed_spin.setValue(1.0)
        form.addRow("Speed", self.binding_speed_spin)

        self.binding_suppress_check = QCheckBox("Suppress original key")
        self.binding_suppress_check.setChecked(True)
        form.addRow("Suppress", self.binding_suppress_check)

        bindings_layout.addLayout(form)

        button_row = QHBoxLayout()
        add_binding = QPushButton("Add/Update")
        add_binding.clicked.connect(self._save_binding)
        button_row.addWidget(add_binding)
        remove_binding = QPushButton("Remove")
        remove_binding.clicked.connect(self._remove_binding)
        button_row.addWidget(remove_binding)
        bindings_layout.addLayout(button_row)

        layout.addWidget(bindings_group)

        self.autofire_editor = AutoFireEditor()
        self.autofire_editor.save_button.clicked.connect(self._save_autofire_binding)
        self.autofire_editor.remove_button.clicked.connect(self._remove_autofire_binding)
        layout.addWidget(self.autofire_editor)

        self.autofire_status_label = QLabel("AutoFire: idle")
        layout.addWidget(self.autofire_status_label)

        layout.addStretch()
        return container

    # Profile + macro management --------------------------------------------------
    def _load_or_create_state(self, path: Path) -> AppState:
        if path.exists():
            try:
                return load_state(path)
            except StorageError as exc:
                QMessageBox.warning(self, "Load Failed", str(exc))
        default_profile = Profile(id=generate_id(), name="Default Profile")
        state = AppState(profiles=[default_profile], active_profile_id=default_profile.id)
        return state

    def _normalize_state(self) -> None:
        for profile in self.state.profiles:
            for binding in profile.bindings:
                binding.binding_type = self._coerce_binding_type(binding.binding_type)
                if not isinstance(binding.playback, PlaybackOptions):
                    payload = binding.playback if isinstance(binding.playback, dict) else {}
                    binding.playback = PlaybackOptions.from_dict(payload)
                binding.playback.mode = self._coerce_playback_mode(binding.playback.mode)
                binding.playback.delay_strategy = self._coerce_delay_strategy(binding.playback.delay_strategy)
            for macro in profile.macros:
                macro.playback.mode = self._coerce_playback_mode(macro.playback.mode)
                macro.playback.delay_strategy = self._coerce_delay_strategy(macro.playback.delay_strategy)
            normalized_autofire: list[AutoFireBinding] = []
            for binding in profile.auto_fire_bindings:
                if isinstance(binding, AutoFireBinding):
                    normalized_autofire.append(binding)
                elif isinstance(binding, dict):
                    normalized_autofire.append(AutoFireBinding.from_dict(binding))
            profile.auto_fire_bindings = normalized_autofire

    def _current_profile(self) -> Profile:
        return find_profile(self.state, self.state.active_profile_id)

    def _current_macro(self) -> Macro:
        profile = self._current_profile()
        if not profile.macros:
            macro = Macro(id=generate_id(), name="Macro 1")
            profile.macros.append(macro)
        index = max(0, self.macro_list.currentRow())
        if index >= len(profile.macros):
            index = 0
            self.macro_list.setCurrentRow(index)
        return profile.macros[index]

    # Slots -----------------------------------------------------------------------
    def _on_profile_changed(self) -> None:
        index = self.profile_combo.currentIndex()
        if index < 0 or index >= len(self.state.profiles):
            return
        self.state.active_profile_id = self.state.profiles[index].id
        self._refresh_profiles()
        self._refresh_bindings_table()
        self._set_status("Profile switched")

    def _refresh_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in self.state.profiles:
            self.profile_combo.addItem(profile.name, profile.id)
        active_id = self.state.active_profile_id
        active_index = next((i for i, p in enumerate(self.state.profiles) if p.id == active_id), 0)
        self.profile_combo.setCurrentIndex(active_index)
        self.profile_combo.blockSignals(False)
        self._refresh_macro_list()
        self.blocklist_edit.setText(", ".join(self._current_profile().blocklist))
        self.binding_registry.apply_bindings(self._current_profile().bindings)
        self._refresh_autofire_editor()

    def _refresh_macro_list(self) -> None:
        profile = self._current_profile()
        self.macro_list.blockSignals(True)
        previous_id = None
        current_item = self.macro_list.currentItem()
        if current_item is not None:
            previous_id = current_item.data(Qt.UserRole)
        self.macro_list.clear()
        for macro in profile.macros:
            item = QListWidgetItem(macro.name)
            item.setData(Qt.UserRole, macro.id)
            self.macro_list.addItem(item)
        if profile.macros:
            next_index = 0
            if previous_id:
                next_index = next(
                    (i for i, macro in enumerate(profile.macros) if macro.id == previous_id),
                    0,
                )
            self.macro_list.setCurrentRow(next_index)
        self.macro_list.blockSignals(False)
        self._load_macro_into_timeline(self._current_macro())

    def _load_macro_into_timeline(self, macro: Macro) -> None:
        self.timeline_model.set_events(macro.events)
        self.macro_name_edit.setText(macro.name)
        self._update_transport_from_macro(macro)
        if macro.events:
            self.timeline_view.selectRow(0)
        else:
            self.timeline_view.clearSelection()

    def _update_transport_from_macro(self, macro: Macro) -> None:
        playback = macro.playback
        mode_index = self.mode_combo.findData(playback.mode)
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)
        self.repeat_spin.setValue(playback.repeat_count)
        self.speed_spin.setValue(playback.speed_multiplier)

    def _on_macro_selected(self, row: int) -> None:
        profile = self._current_profile()
        if 0 <= row < len(profile.macros):
            macro = profile.macros[row]
            self._load_macro_into_timeline(macro)
            self._set_status(f"Macro '{macro.name}' selected")

    def _rename_macro(self) -> None:
        macro = self._current_macro()
        new_name = self.macro_name_edit.text().strip() or "Untitled"
        macro.name = new_name
        self._refresh_macro_list()

    def _add_macro(self) -> None:
        profile = self._current_profile()
        macro = Macro(id=generate_id(), name=f"Macro {len(profile.macros)+1}")
        profile.macros.append(macro)
        self._refresh_macro_list()
        index = next((i for i, item in enumerate(profile.macros) if item.id == macro.id), len(profile.macros) - 1)
        self.macro_list.setCurrentRow(index)
        self._refresh_bindings_table()
        self._set_status("Macro added")

    def _duplicate_macro(self) -> None:
        macro = self._current_macro()
        clone = Macro.from_dict(macro.to_dict())
        clone.id = generate_id()
        clone.name = f"{macro.name} Copy"
        profile = self._current_profile()
        profile.macros.append(clone)
        self._refresh_macro_list()
        index = next((i for i, item in enumerate(profile.macros) if item.id == clone.id), len(profile.macros) - 1)
        self.macro_list.setCurrentRow(index)
        self._refresh_bindings_table()
        self._set_status("Macro duplicated")

    def _delete_macro(self) -> None:
        profile = self._current_profile()
        row = self.macro_list.currentRow()
        if 0 <= row < len(profile.macros):
            del profile.macros[row]
            if not profile.macros:
                profile.macros.append(Macro(id=generate_id(), name="Macro 1"))
            self._refresh_macro_list()
            self._refresh_bindings_table()
            self._set_status("Macro deleted")

    def _create_profile(self) -> None:
        profile = Profile(id=generate_id(), name=f"Profile {len(self.state.profiles)+1}")
        profile.macros.append(Macro(id=generate_id(), name="Macro 1"))
        self.state.profiles.append(profile)
        self.state.active_profile_id = profile.id
        self._refresh_profiles()
        self._set_status("Profile created")

    def _duplicate_profile(self) -> None:
        profile = self._current_profile()
        clone = Profile(
            id=generate_id(),
            name=f"{profile.name} Copy",
            macros=[Macro.from_dict(macro.to_dict()) for macro in profile.macros],
            bindings=[Binding.from_dict(binding.to_dict()) for binding in profile.bindings],
            auto_fire_bindings=[AutoFireBinding.from_dict(b.to_dict()) for b in profile.auto_fire_bindings],
            blocklist=list(profile.blocklist),
        )
        self.state.profiles.append(clone)
        self.state.active_profile_id = clone.id
        self._refresh_profiles()
        self._set_status("Profile duplicated")

    def _delete_profile(self) -> None:
        if len(self.state.profiles) <= 1:
            QMessageBox.information(self, "Profiles", "At least one profile must exist.")
            return
        profile = self._current_profile()
        self.state.profiles = [p for p in self.state.profiles if p.id != profile.id]
        self.state.active_profile_id = self.state.profiles[0].id
        self._refresh_profiles()
        self._set_status("Profile deleted")

    # Blocklist -------------------------------------------------------------------
    def _update_blocklist(self) -> None:
        entries = [token.strip().lower() for token in self.blocklist_edit.text().split(",") if token.strip()]
        self._current_profile().blocklist = entries
        self._set_status("Blocklist updated")

    # Recording -------------------------------------------------------------------
    def _start_recording(self) -> None:
        if self.recorder.is_recording():
            return
        config = RecorderConfig(
            include_keyboard=self.include_keyboard_check.isChecked(),
            include_mouse=self.include_mouse_check.isChecked(),
            blocklist=self._current_profile().blocklist,
        )
        try:
            self.recorder.start(config)
            self._set_status("Recording... Press Stop Rec when finished.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Recorder", str(exc))

    def _stop_recording(self) -> None:
        if not self.recorder.is_recording():
            return
        try:
            events = self.recorder.stop()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Recorder", str(exc))
            return
        macro = self._current_macro()
        macro.events = events
        self.timeline_model.set_events(macro.events)
        macro.playback.delay_strategy = DelayStrategy.ACTUAL
        macro.playback.fixed_delay_ms = None
        if macro.events:
            self.timeline_view.selectRow(0)
        self._set_status(f"Recorded {len(events)} events")

    # Playback --------------------------------------------------------------------
    def _play_macro(self) -> None:
        macro = self._current_macro()
        playback = macro.playback
        playback.mode = self._coerce_playback_mode(self.mode_combo.currentData())
        playback.repeat_count = self.repeat_spin.value()
        playback.speed_multiplier = self.speed_spin.value()
        if playback.mode == PlaybackMode.WHILE_HELD:
            QMessageBox.information(
                self,
                "Playback",
                "While-Held mode needs to be triggered from a hotkey binding. Choose another mode to preview from the UI.",
            )
            return
        try:
            self.player.play(macro, playback, trigger_hotkey=None)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Playback", str(exc))

    def _stop_playback(self) -> None:
        self.player.stop()
        self._set_status("Stop requested")

    def _on_player_state(self, state: str) -> None:
        self.emergency_label.setText(f"Player: {state}")
        if state == "error":
            self._set_status("Playback failed")
        elif state == "finished":
            self._set_status("Playback finished")
        elif state == "started":
            self._set_status("Playback started")

    def _on_emergency_stop(self) -> None:
        self.player.stop()
        self._set_status("Emergency stop engaged")

    # Timeline tools --------------------------------------------------------------
    def _apply_delay_preset(self, value: int) -> None:
        self.timeline_model.normalize_delays(value)
        macro = self._current_macro()
        macro.playback.delay_strategy = DelayStrategy.FIXED
        macro.playback.fixed_delay_ms = value
        self._set_status(f"Delays normalized to {value} ms")

    def _use_actual_delay(self) -> None:
        macro = self._current_macro()
        macro.playback.delay_strategy = DelayStrategy.ACTUAL
        macro.playback.fixed_delay_ms = None
        self._set_status("Using recorded delays")

    def _on_scale_changed(self) -> None:
        value = self.scale_slider.value()
        factor = value / 100.0
        self.scale_label.setText(f"{value}%")
        self.timeline_model.scale_delays(factor)
        self._set_status(f"Delays scaled by {value}%")

    def _insert_key_event(self, action: str) -> None:
        from core.types import KeyAction, KeyEvent, EventKind

        macro = self._current_macro()
        new_event = KeyEvent(
            id=generate_id(),
            kind=EventKind.KEY,
            delay_ms=10,
            timestamp_ns=0,
            key="space",
            scan_code=None,
            action=KeyAction(action),
        )
        macro.events.append(new_event)
        self.timeline_model.set_events(macro.events)
        self.timeline_view.selectRow(len(macro.events) - 1)

    def _insert_mouse_click(self) -> None:
        from core.types import MouseAction, MouseEvent, EventKind

        macro = self._current_macro()
        new_event = MouseEvent(
            id=generate_id(),
            kind=EventKind.MOUSE,
            delay_ms=10,
            timestamp_ns=0,
            action=MouseAction.DOWN,
            button="left",
            x=0,
            y=0,
            delta=None,
        )
        macro.events.append(new_event)
        self.timeline_model.set_events(macro.events)
        self.timeline_view.selectRow(len(macro.events) - 1)

    def _insert_mouse_move(self) -> None:
        from core.types import MouseAction, MouseEvent, EventKind

        macro = self._current_macro()
        new_event = MouseEvent(
            id=generate_id(),
            kind=EventKind.MOUSE,
            delay_ms=10,
            timestamp_ns=0,
            action=MouseAction.MOVE,
            button=None,
            x=100,
            y=100,
            delta=None,
        )
        macro.events.append(new_event)
        self.timeline_model.set_events(macro.events)
        self.timeline_view.selectRow(len(macro.events) - 1)

    def _insert_mouse_wheel(self) -> None:
        from core.types import MouseAction, MouseEvent, EventKind

        macro = self._current_macro()
        new_event = MouseEvent(
            id=generate_id(),
            kind=EventKind.MOUSE,
            delay_ms=10,
            timestamp_ns=0,
            action=MouseAction.WHEEL,
            button=None,
            x=0,
            y=0,
            delta=1,
        )
        macro.events.append(new_event)
        self.timeline_model.set_events(macro.events)
        self.timeline_view.selectRow(len(macro.events) - 1)

    def _prompt_normalize(self) -> None:
        self._apply_delay_preset(25)

    # Binding manager -------------------------------------------------------------
    def _refresh_bindings_table(self) -> None:
        profile = self._current_profile()
        bindings = profile.bindings
        self.binding_table.setRowCount(len(bindings))
        for row, binding in enumerate(bindings):
            btype = self._coerce_binding_type(binding.binding_type)
            binding.binding_type = btype
            playback = binding.playback
            if not isinstance(playback, PlaybackOptions):
                payload = playback if isinstance(playback, dict) else {}
                playback = PlaybackOptions.from_dict(payload)
                binding.playback = playback
            playback.mode = self._coerce_playback_mode(playback.mode)
            playback.delay_strategy = self._coerce_delay_strategy(playback.delay_strategy)
            self.binding_table.setItem(row, 0, QTableWidgetItem(binding.hotkey))
            self.binding_table.setItem(row, 1, QTableWidgetItem(btype.name.title()))
            target = binding.target_id or ""
            if btype == BindingType.TEXT:
                target = "Text"
            elif btype == BindingType.PROGRAM:
                target = binding.payload or ""
            self.binding_table.setItem(row, 2, QTableWidgetItem(target))
            self.binding_table.setItem(row, 3, QTableWidgetItem(playback.mode.name.title()))
        self.binding_registry.apply_bindings(bindings)
        self._populate_binding_targets()
        self._apply_autofire_bindings()

    # AutoFire manager ----------------------------------------------------------
    def _refresh_autofire_editor(self) -> None:
        profile = self._current_profile()
        self.autofire_editor.set_bindings(list(profile.auto_fire_bindings))
        self._apply_autofire_bindings()

    def _apply_autofire_bindings(self) -> None:
        profile = self._current_profile()
        mapping = {binding.trigger_key: binding for binding in profile.auto_fire_bindings}
        try:
            self.autofire_registry.apply_bindings(mapping)
        except ValueError as exc:
            QMessageBox.warning(self, "AutoFire", str(exc))
        if not mapping:
            self._set_autofire_status("AutoFire: idle")

    def _save_autofire_binding(self) -> None:
        data = self.autofire_editor.collect_input()
        if not data.trigger_key:
            QMessageBox.warning(self, "AutoFire", "Trigger key is required")
            return
        if not data.output_key:
            QMessageBox.warning(self, "AutoFire", "Output key is required")
            return
        profile = self._current_profile()
        conflict = next(
            (b for b in profile.auto_fire_bindings if b.trigger_key == data.trigger_key and b.id != data.id),
            None,
        )
        if conflict:
            QMessageBox.warning(
                self,
                "AutoFire",
                f"Trigger '{data.trigger_key.upper()}' is already used by another AutoFire binding.",
            )
            return
        try:
            binding = self.autofire_editor.update_binding(data)
        except ValueError as exc:
            QMessageBox.warning(self, "AutoFire", str(exc))
            return
        profile.auto_fire_bindings = self.autofire_editor.bindings()
        self._apply_autofire_bindings()
        self._set_status(f"AutoFire binding saved: {binding.trigger_key.upper()} -> {binding.output_key.upper()}")

    def _remove_autofire_binding(self) -> None:
        removed = self.autofire_editor.remove_selected()
        if removed is None:
            return
        profile = self._current_profile()
        profile.auto_fire_bindings = self.autofire_editor.bindings()
        self._apply_autofire_bindings()
        self._set_status("AutoFire binding removed")

    def _set_autofire_status(self, message: str) -> None:
        text = message or "AutoFire: idle"
        if hasattr(self, "autofire_status_label"):
            self.autofire_status_label.setText(text)

    def _on_autofire_error(self, message: str) -> None:
        self._set_status(message)
        QMessageBox.warning(self, "AutoFire", message)

    def _on_binding_selected(self) -> None:
        rows = self.binding_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        binding = self._current_profile().bindings[row]
        btype = self._coerce_binding_type(binding.binding_type)
        binding.binding_type = btype
        playback = binding.playback
        if not isinstance(playback, PlaybackOptions):
            payload = playback if isinstance(playback, dict) else {}
            playback = PlaybackOptions.from_dict(payload)
            binding.playback = playback
        playback.mode = self._coerce_playback_mode(playback.mode)
        playback.delay_strategy = self._coerce_delay_strategy(playback.delay_strategy)
        self.binding_hotkey_edit.setText(binding.hotkey)
        index = self.binding_type_combo.findData(btype)
        if index < 0:
            index = 0
        self.binding_type_combo.setCurrentIndex(index)
        self._populate_binding_targets()
        if btype == BindingType.MACRO and binding.target_id:
            target_index = self.binding_target_combo.findData(binding.target_id)
            self.binding_target_combo.setCurrentIndex(target_index)
        elif btype == BindingType.SYSTEM and binding.target_id:
            target_index = self.binding_target_combo.findData(binding.target_id)
            self.binding_target_combo.setCurrentIndex(target_index)
        elif btype in (BindingType.TEXT, BindingType.PROGRAM):
            self.binding_payload_edit.setText(binding.payload or "")
        mode_index = self.binding_mode_combo.findData(playback.mode)
        if mode_index < 0:
            mode_index = 0
        self.binding_mode_combo.setCurrentIndex(mode_index)
        self.binding_repeat_spin.setValue(playback.repeat_count)
        self.binding_speed_spin.setValue(playback.speed_multiplier)
        self.binding_suppress_check.setChecked(binding.suppress)

    def _populate_binding_targets(self) -> None:
        btype = self._coerce_binding_type(self.binding_type_combo.currentData())
        self.binding_target_combo.blockSignals(True)
        self.binding_target_combo.clear()
        if btype == BindingType.MACRO:
            for macro in self._current_profile().macros:
                self.binding_target_combo.addItem(macro.name, macro.id)
            self.binding_target_combo.setEnabled(True)
            self.binding_payload_edit.clear()
            self.binding_payload_edit.setEnabled(False)
        elif btype == BindingType.SYSTEM:
            for action_id, label in SYSTEM_ACTION_IDS:
                self.binding_target_combo.addItem(label, action_id)
            self.binding_target_combo.setEnabled(True)
            self.binding_payload_edit.setEnabled(True)
        else:
            self.binding_target_combo.setEnabled(False)
            self.binding_payload_edit.setEnabled(True)
        if self.binding_target_combo.count():
            self.binding_target_combo.setCurrentIndex(0)
        self.binding_target_combo.blockSignals(False)

    def _on_binding_type_changed(self) -> None:
        self._populate_binding_targets()

    def _save_binding(self) -> None:
        hotkey = self.binding_hotkey_edit.text().strip().lower()
        if not hotkey:
            QMessageBox.warning(self, "Binding", "Hotkey is required")
            return
        if "fn" in hotkey:
            QMessageBox.warning(self, "Binding", "Fn key cannot be captured")
            return
        btype = self._coerce_binding_type(self.binding_type_combo.currentData())
        target_id: Optional[str] = None
        payload: Optional[str] = None
        if btype == BindingType.MACRO:
            target_id = self.binding_target_combo.currentData()
        elif btype == BindingType.SYSTEM:
            target_id = self.binding_target_combo.currentData()
            payload = self.binding_payload_edit.text().strip() or None
        elif btype == BindingType.TEXT:
            payload = self.binding_payload_edit.text()
            if not payload:
                QMessageBox.warning(self, "Binding", "Enter the text to send for a Text binding")
                return
        elif btype == BindingType.PROGRAM:
            payload = self.binding_payload_edit.text().strip()
            if not payload:
                QMessageBox.warning(self, "Binding", "Enter the program path to launch")
                return
        mode = self._coerce_playback_mode(self.binding_mode_combo.currentData())
        playback = PlaybackOptions(
            mode=mode,
            repeat_count=self.binding_repeat_spin.value(),
            speed_multiplier=self.binding_speed_spin.value(),
        )
        profile = self._current_profile()
        existing = next((b for b in profile.bindings if b.hotkey == hotkey), None)
        binding_id = existing.id if existing else generate_id()
        binding = Binding(
            id=binding_id,
            hotkey=hotkey,
            binding_type=btype,
            target_id=target_id,
            payload=payload,
            playback=playback,
            suppress=self.binding_suppress_check.isChecked(),
        )
        if existing:
            profile.bindings[profile.bindings.index(existing)] = binding
        else:
            profile.bindings.append(binding)
        self._refresh_bindings_table()
        self._set_status("Binding saved")

    def _remove_binding(self) -> None:
        rows = self.binding_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        profile = self._current_profile()
        del profile.bindings[row]
        self._refresh_bindings_table()
        self._set_status("Binding removed")

    # Helpers ---------------------------------------------------------------------
    @staticmethod
    def _coerce_binding_type(raw: Any) -> BindingType:
        if isinstance(raw, BindingType):
            return raw
        try:
            return BindingType(str(raw))
        except Exception:  # noqa: BLE001
            return BindingType.MACRO

    @staticmethod
    def _coerce_playback_mode(raw: Any) -> PlaybackMode:
        if isinstance(raw, PlaybackMode):
            return raw
        try:
            return PlaybackMode(str(raw))
        except Exception:  # noqa: BLE001
            return PlaybackMode.ONCE

    @staticmethod
    def _coerce_delay_strategy(raw: Any) -> DelayStrategy:
        if isinstance(raw, DelayStrategy):
            return raw
        try:
            return DelayStrategy(str(raw))
        except Exception:  # noqa: BLE001
            return DelayStrategy.ACTUAL

    def _on_model_reset(self) -> None:
        self._clear_event_properties()

    def _on_timeline_data_changed(self, *_) -> None:
        self._on_timeline_selection()

    def _on_timeline_selection(self, *_args, **_kwargs) -> None:
        selection = self.timeline_view.selectionModel()
        if selection is None:
            self._clear_event_properties()
            return
        indexes = selection.selectedRows()
        if not indexes:
            self._clear_event_properties()
            return
        row = indexes[0].row()
        macro = self._current_macro()
        if 0 <= row < len(macro.events):
            self._display_event_properties(macro.events[row])
        else:
            self._clear_event_properties()

    def _display_event_properties(self, event) -> None:
        from core.types import KeyEvent, MouseEvent

        if isinstance(event, KeyEvent):
            self.prop_type.setText("Key Event")
            self.prop_action.setText(event.action.value)
            self.prop_key.setText(event.key)
            self.prop_position.setText("-")
            self.prop_delay.setText(f"{event.delay_ms} ms")
        elif isinstance(event, MouseEvent):
            self.prop_type.setText("Mouse Event")
            self.prop_action.setText(event.action.value)
            self.prop_key.setText(event.button or "")
            coords = "-"
            if event.x is not None and event.y is not None:
                coords = f"({event.x}, {event.y})"
            self.prop_position.setText(coords)
            delta = event.delta if event.delta is not None else "-"
            self.prop_delay.setText(f"{event.delay_ms} ms | Δ {delta}")
        else:
            self._clear_event_properties()

    def _clear_event_properties(self) -> None:
        self.prop_type.setText("-")
        self.prop_action.setText("-")
        self.prop_key.setText("-")
        self.prop_position.setText("-")
        self.prop_delay.setText("-")

    def _resolve_macro(self, macro_id: str) -> Optional[Macro]:
        profile = self._current_profile()
        for macro in profile.macros:
            if macro.id == macro_id:
                return macro
        return None

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        logger.info(message)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            save_state(self.state_path, self.state)
        except StorageError as exc:
            QMessageBox.warning(self, "Save Failed", str(exc))
        finally:
            keyboard.remove_hotkey(self._emergency_hotkey_id)
            self.binding_registry.clear()
            self.player.stop()
        super().closeEvent(event)


def run_main_window(state_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(state_path)
    window.show()
    app.exec()