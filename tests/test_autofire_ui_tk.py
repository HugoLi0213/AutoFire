import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ruff: noqa: E501
import tkinter as tk
from tkinter import messagebox
from typing import Generator
from unittest.mock import MagicMock, call
import time

import pytest

import autofire_ui
from autofire_ui import (
    MIN_INTERVAL_MS,
    MAX_INTERVAL_MS,
    AutoFireUI,
    AutoFireConfig,
    AutoFireSlot,
    WM_KEYDOWN,
    WM_KEYUP,
)
from tests.test_autofire_runner import FakeClock, FakeKeyboard, FakeCtypes


class UIHarness:
    """A test harness for the AutoFireUI."""

    def __init__(self, ui: AutoFireUI, clock: FakeClock, keyboard: FakeKeyboard, ctypes: FakeCtypes):
        self.ui = ui
        self.clock = clock
        self.keyboard = keyboard
        self.ctypes = ctypes
        self.saved_configs: list[AutoFireConfig] = []
        self.messagebox_calls: list[tuple[str, str]] = []

    def pump(self) -> None:
        """Process all pending UI events."""
        # Check for pending error status from background threads
        if self.ui.engine:
            error_status = self.ui.engine.get_pending_error_status()
            if error_status:
                state, config = error_status
                self.ui._update_status_display(state, config)
        self.ui.root.update()

    def advance(self, duration_ms: int, step_ms: int = 1) -> None:
        """Advance the clock and pump the UI."""
        for _ in range(0, duration_ms, step_ms):
            self.clock.advance(step_ms / 1000.0)
            self.pump()

    def close(self) -> None:
        """Close the UI."""
        self.ui.on_close()

    def wait_for_status(self, status_substring: str, timeout_ms: int = 1000) -> bool:
        """Wait until the status label contains the given substring."""
        for _ in range(timeout_ms):
            self.pump()
            if status_substring in self.ui.status_var.get():
                return True
            self.clock.advance(0.001)
        # To aid debugging, print the final status if the wait fails.
        print(f"wait_for_status timed out. Final status: '{self.ui.status_var.get()}'")
        return False


@pytest.fixture(scope="session")
def root_window() -> Generator[tk.Tk, None, None]:
    """Create a single, persistent root window for the entire test session."""
    root = tk.Tk()
    root.withdraw()  # Keep it hidden
    yield root
    try:
        if root.winfo_exists():
            root.destroy()
    except tk.TclError:
        # This can happen if the window is already destroyed, which is fine.
        pass


@pytest.fixture
def ui_harness(
    monkeypatch: pytest.MonkeyPatch, root_window: tk.Tk
) -> Generator[UIHarness, None, None]:
    """Fixture to create a UI harness with mocked dependencies."""
    fake_clock = FakeClock()
    fake_keyboard = FakeKeyboard()
    fake_ctypes = FakeCtypes()

    saved_configs: list[AutoFireConfig] = []

    def mock_save_config(config: AutoFireConfig) -> None:
        saved_configs.append(config)

    messagebox_calls: list[tuple[str, str]] = []

    def mock_showerror(title: str, message: str, parent=None) -> None:
        messagebox_calls.append((title, message))

    monkeypatch.setattr(autofire_ui, "keyboard", fake_keyboard)
    monkeypatch.setattr(autofire_ui, "ctypes", fake_ctypes)
    monkeypatch.setattr(messagebox, "showerror", mock_showerror)
    monkeypatch.setattr(
        autofire_ui,
        "load_config",
        lambda: AutoFireConfig(
            slots=[AutoFireSlot(
                trigger_key="e",
                output_key="r",
                interval_ms=100,
                window_title="Test Window",
                pass_through=False,
                use_sendinput=False,
                enabled=True
            )],
            language="en"
        ),
    )
    monkeypatch.setattr(autofire_ui, "save_config", mock_save_config)
    # Mock the window enumeration function to return a simple list
    monkeypatch.setattr(
        autofire_ui,
        "get_all_window_titles",
        lambda: ["Test Window", "Notepad", "Calculator"]
    )

    # Clear any child widgets from previous tests
    for widget in root_window.winfo_children():
        widget.destroy()

    ui = AutoFireUI(root_window)

    # Monkeypatch time functions used by the engine's thread
    monkeypatch.setattr(time, "sleep", fake_clock.sleep)
    monkeypatch.setattr(time, "time", fake_clock.now)

    harness = UIHarness(ui, fake_clock, fake_keyboard, fake_ctypes)
    harness.saved_configs = saved_configs
    harness.messagebox_calls = messagebox_calls

    yield harness

    # Cleanup after test
    if ui.engine and ui.engine.is_running:
        ui.stop_autofire()


def test_initial_state_and_config_load(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.pump()

    assert harness.ui.trigger_var.get() == "e"
    assert harness.ui.output_var.get() == "r"
    assert harness.ui.interval_var.get() == 100
    assert not harness.ui.pass_var.get()
    assert harness.ui.window_title_var.get() == "Test Window"
    assert "Stopped" in harness.ui.status_var.get()
    assert harness.ui.ui_elements['start_button'].instate(["!disabled"])
    assert harness.ui.ui_elements['stop_button'].instate(["disabled"])


def test_start_and_stop_engine(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.ui.window_title_var.set(harness.ctypes.target_window_title)
    harness.pump()

    harness.ui.start_autofire()
    harness.pump()

    assert harness.wait_for_status("Running", timeout_ms=1000)
    assert harness.ui.engine is not None and harness.ui.engine.is_running
    assert harness.ui.ui_elements['start_button'].instate(["disabled"])
    assert harness.ui.ui_elements['stop_button'].instate(["!disabled"])
    assert harness.keyboard.hook_key_calls

    harness.ui.stop_autofire()
    harness.pump()

    assert "Stopped" in harness.ui.status_var.get()
    assert not harness.ui.engine.is_running
    assert harness.ui.ui_elements['start_button'].instate(["!disabled"])
    assert harness.ui.ui_elements['stop_button'].instate(["disabled"])
    assert not harness.keyboard.has_active_hooks()


def test_trigger_press_runs_until_release(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.ui.trigger_var.set("e")
    harness.ui.output_var.set("r")
    harness.ui.interval_var.set(10)
    harness.ui.pass_var.set(False)
    harness.ui.window_title_var.set(harness.ctypes.target_window_title)

    harness.ui.start_autofire()
    harness.pump()
    assert harness.wait_for_status("Running")

    harness.keyboard.clear_calls()
    harness.ctypes.post_message_calls.clear()

    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[active]", timeout_ms=1000)

    harness.advance(50, 5)

    harness.keyboard.simulate_keyup("e")
    assert harness.wait_for_status("Running")

    output_vk = autofire_ui.VK_CODES["r"]
    keydown_events = [
        call
        for call in harness.ctypes.post_message_calls
        if call[1] == WM_KEYDOWN and call[2] == output_vk
    ]
    keyup_events = [
        call
        for call in harness.ctypes.post_message_calls
        if call[1] == WM_KEYUP and call[2] == output_vk
    ]

    assert len(keydown_events) > 0
    assert len(keydown_events) == len(keyup_events)
    assert all(
        call[0] == harness.ctypes.target_hwnd for call in harness.ctypes.post_message_calls
    )


def test_start_fails_if_window_not_found(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.ui.window_title_var.set("Non-existent Window")
    harness.pump()

    harness.ui.start_autofire()
    harness.pump()

    harness.keyboard.simulate_keydown("e")
    harness.advance(50, 10)

    assert harness.wait_for_status("Error: Window", timeout_ms=1000)
    assert not harness.messagebox_calls
    assert harness.ui.engine is not None and harness.ui.engine.is_running


def test_pass_through_modes_control_blocking(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.ui.window_title_var.set(harness.ctypes.target_window_title)

    # Test with pass_through = True
    harness.ui.pass_var.set(True)
    harness.ui.start_autofire()
    harness.pump()
    assert harness.wait_for_status("Running")

    assert len(harness.keyboard.hook_key_calls) > 0
    for c in harness.keyboard.hook_key_calls:
        assert c.kwargs["suppress"] is False

    harness.ui.stop_autofire()
    harness.pump()
    harness.keyboard.clear_calls()

    # Test with pass_through = False
    harness.ui.pass_var.set(False)
    harness.ui.start_autofire()
    harness.pump()
    assert harness.wait_for_status("Running")

    assert len(harness.keyboard.hook_key_calls) > 0
    for c in harness.keyboard.hook_key_calls:
        assert c.kwargs["suppress"] is True


def test_capture_buttons_update_entries(ui_harness: UIHarness) -> None:
    pytest.skip("Capture button functionality removed from UI")


def test_interval_validation_clamps_and_saves(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.ui.window_title_var.set(harness.ctypes.target_window_title)
    harness.pump()

    harness.ui.interval_var.set(0)
    harness.ui.start_autofire()
    harness.pump()

    assert harness.saved_configs[-1].slots[0].interval_ms == MIN_INTERVAL_MS
    assert f"@{MIN_INTERVAL_MS}ms" in harness.ui.status_var.get()
    assert not harness.messagebox_calls

    harness.ui.stop_autofire()
    harness.pump()

    harness.ui.interval_var.set(5000)
    harness.ui.start_autofire()
    harness.pump()

    assert harness.saved_configs[-1].slots[0].interval_ms == MAX_INTERVAL_MS
    assert f"@{MAX_INTERVAL_MS}ms" in harness.ui.status_var.get()
    assert not harness.messagebox_calls


def test_start_stop_buttons_reflect_status(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.ui.window_title_var.set(harness.ctypes.target_window_title)
    harness.pump()

    assert harness.ui.ui_elements['start_button'].instate(["!disabled"])
    assert harness.ui.ui_elements['stop_button'].instate(["disabled"])

    harness.ui.start_autofire()
    harness.pump()
    assert harness.wait_for_status("Running")

    assert harness.ui.ui_elements['start_button'].instate(["disabled"])
    assert harness.ui.ui_elements['stop_button'].instate(["!disabled"])

    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[active]")

    harness.advance(30, 5)
    harness.keyboard.simulate_keyup("e")
    harness.advance(20, 5)
    assert harness.wait_for_status("Running")

    harness.ui.stop_autofire()
    harness.advance(20, 5)
    assert harness.wait_for_status("Stopped")
    assert harness.ui.ui_elements['start_button'].instate(["!disabled"])
    assert harness.ui.ui_elements['stop_button'].instate(["disabled"])


def test_on_close_unhooks_and_clears_state(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.ui.window_title_var.set(harness.ctypes.target_window_title)
    harness.pump()

    harness.ui.start_autofire()
    harness.pump()
    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[active]")

    harness.keyboard.simulate_keyup("e")
    harness.advance(10, 5)
    harness.close()

    assert not harness.keyboard.has_active_hooks()
    assert not harness.keyboard.is_blocked("e")