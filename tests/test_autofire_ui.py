"""UI-level QA tests for AutoFire editor interactions using pytest-qt."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pytest
from PySide6 import QtWidgets

from core.bindings_autofire import AutoFireBindingRegistry
from ui.main_window import MainWindow


@pytest.fixture
def autofire_window(
    qtbot,
    tmp_path,
    fake_keyboard_backend,
    fake_clock,
    monkeypatch,
):
    state_path = Path(tmp_path) / "state.json"

    # Route all keyboard interactions through the fake backend.
    monkeypatch.setattr("ui.main_window.keyboard", fake_keyboard_backend, raising=False)
    monkeypatch.setattr("core.bindings.keyboard", fake_keyboard_backend, raising=False)

    window = MainWindow(state_path)
    qtbot.addWidget(window)

    # Replace the AutoFire registry so it uses the fake clock/backend and exposes emergency stop.
    window.autofire_registry = AutoFireBindingRegistry(
        keyboard_module=fake_keyboard_backend,
        now=fake_clock.now,
        sleep=fake_clock.sleep,
        status_callback=window._set_autofire_status,
        error_callback=window._on_autofire_error,
        register_emergency=True,
    )
    window._apply_autofire_bindings()

    return window, fake_keyboard_backend, fake_clock


def _configure_binding(window: MainWindow, trigger: str, output: str, interval: int, pass_through: bool) -> None:
    editor = window.autofire_editor
    editor.trigger_edit.setText(trigger)
    editor.output_edit.setText(output)
    editor.interval_spin.setValue(interval)
    editor.pass_check.setChecked(pass_through)
    window._save_autofire_binding()


def test_editor_and_status_feedback(autofire_window, qtbot):
    window, keyboard, clock = autofire_window
    _configure_binding(window, "E", "R", 10, False)

    keyboard.simulate_keydown("e")
    clock.advance_ms(50)

    qtbot.waitUntil(
        lambda: window.autofire_status_label.text().startswith("AutoFire: E -> R @10ms"),
        timeout=1000,
    )

    pulses_before_release = len([k for k in keyboard.press_history if k == "r"])

    keyboard.simulate_keyup("e")
    clock.advance_ms(20)

    qtbot.waitUntil(lambda: window.autofire_status_label.text() == "AutoFire: idle", timeout=1000)

    pulses_after_release = len([k for k in keyboard.press_history if k == "r"])
    assert pulses_after_release >= pulses_before_release
    assert keyboard.block_calls.count("e") == 1
    assert keyboard.unblock_calls.count("e") == 1


def test_conflict_dialog(autofire_window, qtbot, monkeypatch):
    window, keyboard, _ = autofire_window
    _configure_binding(window, "E", "R", 10, False)

    messages: list[Tuple[str, str]] = []

    def _fake_warning(parent, title, text):  # noqa: ANN001
        messages.append((title, text))
        return QtWidgets.QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", _fake_warning)

    window.autofire_editor.table.clearSelection()
    window.autofire_editor.clear_fields()
    _configure_binding(window, "E", "T", 20, False)

    assert messages
    last_title, last_text = messages[-1]
    assert last_title == "AutoFire"
    assert "already used" in last_text

    bindings = window.autofire_editor.bindings()
    assert len(bindings) == 1
    assert bindings[0].output_key == "r"
    assert set(window.autofire_registry._handles.keys()) == {"e"}


def test_emergency_stop(autofire_window, qtbot):
    window, keyboard, clock = autofire_window
    _configure_binding(window, "E", "R", 15, False)

    keyboard.simulate_keydown("e")
    clock.advance_ms(45)

    qtbot.waitUntil(
        lambda: window.autofire_status_label.text().startswith("AutoFire: E -> R"),
        timeout=1000,
    )

    pulses_before = len([k for k in keyboard.press_history if k == "r"])

    keyboard.simulate_hotkey("ctrl+alt+esc")
    clock.advance_ms(20)

    qtbot.waitUntil(lambda: window.autofire_status_label.text() == "AutoFire: idle", timeout=1000)

    pulses_after = len([k for k in keyboard.press_history if k == "r"])
    assert pulses_after == pulses_before

    handle = window.autofire_registry._handles["e"]
    assert not handle.runner.running
    assert handle.runner._thread is None

    keyboard.simulate_keyup("e")
