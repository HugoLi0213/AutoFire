"""Tests for multi-slot functionality in AutoFire UI."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from tkinter import messagebox
from typing import Generator
import pytest

import autofire_ui
from autofire_ui import (
    AutoFireUI,
    AutoFireConfig,
    AutoFireSlot,
    save_config,
    load_config,
)
from tests.test_autofire_runner import FakeKeyboard, FakeCtypes


@pytest.fixture
def root_window() -> Generator[tk.Tk, None, None]:
    """Fixture to create a root Tk window for each test."""
    root = tk.Tk()
    root.withdraw()  # Hide the window during tests
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


class MultiSlotHarness:
    """Test harness for multi-slot UI testing."""
    
    def __init__(self, ui: AutoFireUI):
        self.ui = ui
        self.saved_configs: list[AutoFireConfig] = []
        
    def pump(self) -> None:
        """Process all pending UI events."""
        self.ui.root.update()


@pytest.fixture
def multi_slot_ui(monkeypatch: pytest.MonkeyPatch, root_window: tk.Tk) -> Generator[MultiSlotHarness, None, None]:
    """Fixture to create a multi-slot UI harness with mocked dependencies."""
    fake_keyboard = FakeKeyboard()
    fake_ctypes = FakeCtypes()
    
    saved_configs: list[AutoFireConfig] = []
    
    def mock_save_config(config: AutoFireConfig) -> None:
        saved_configs.append(config)
    
    def mock_load_config() -> AutoFireConfig:
        return AutoFireConfig(
            slots=[
                AutoFireSlot(
                    trigger_key="e",
                    output_key="r",
                    interval_ms=50,
                    window_title="",
                    pass_through=False,
                    use_sendinput=False,
                    enabled=True
                )
            ],
            language="en"
        )
    
    monkeypatch.setattr(autofire_ui, "keyboard", fake_keyboard)
    monkeypatch.setattr(autofire_ui, "ctypes", fake_ctypes)
    monkeypatch.setattr(autofire_ui, "save_config", mock_save_config)
    monkeypatch.setattr(autofire_ui, "load_config", mock_load_config)
    monkeypatch.setattr(
        autofire_ui,
        "get_all_window_titles",
        lambda: ["Window 1", "Window 2", "Window 3"]
    )
    
    # Clear any child widgets from previous tests
    for widget in root_window.winfo_children():
        widget.destroy()
    
    ui = AutoFireUI(root_window)
    harness = MultiSlotHarness(ui)
    harness.saved_configs = saved_configs
    
    yield harness


def test_initial_slot_count(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that UI starts with one slot loaded."""
    harness = multi_slot_ui
    harness.pump()
    
    assert len(harness.ui.config.slots) == 1
    assert harness.ui.current_slot_index == 0
    assert harness.ui.slot_listbox.size() == 1


def test_add_slot(multi_slot_ui: MultiSlotHarness) -> None:
    """Test adding a new slot."""
    harness = multi_slot_ui
    harness.pump()
    
    initial_count = len(harness.ui.config.slots)
    
    # Add a new slot
    harness.ui._add_slot()
    harness.pump()
    
    assert len(harness.ui.config.slots) == initial_count + 1
    assert harness.ui.current_slot_index == initial_count
    assert harness.ui.slot_listbox.size() == initial_count + 1
    assert len(harness.saved_configs) > 0


def test_remove_slot(multi_slot_ui: MultiSlotHarness) -> None:
    """Test removing a slot."""
    harness = multi_slot_ui
    harness.pump()
    
    # Add two slots first
    harness.ui._add_slot()
    harness.ui._add_slot()
    harness.pump()
    
    initial_count = len(harness.ui.config.slots)
    assert initial_count == 3
    
    # Remove a slot
    harness.ui.current_slot_index = 1
    harness.ui._remove_slot()
    harness.pump()
    
    assert len(harness.ui.config.slots) == initial_count - 1
    assert harness.ui.slot_listbox.size() == initial_count - 1


def test_cannot_remove_last_slot(multi_slot_ui: MultiSlotHarness, monkeypatch) -> None:
    """Test that the last slot cannot be removed."""
    harness = multi_slot_ui
    harness.pump()
    
    messagebox_calls = []
    
    def mock_showwarning(title: str, message: str, parent=None) -> None:
        messagebox_calls.append((title, message))
    
    monkeypatch.setattr(messagebox, "showwarning", mock_showwarning)
    
    # Try to remove the only slot
    harness.ui._remove_slot()
    harness.pump()
    
    assert len(harness.ui.config.slots) == 1
    assert len(messagebox_calls) == 1
    assert "Cannot remove the last slot" in messagebox_calls[0][1]


def test_slot_selection_updates_ui(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that selecting a slot updates the UI fields."""
    harness = multi_slot_ui
    harness.pump()
    
    # Configure first slot (index 0)
    harness.ui.trigger_var.set("a")
    harness.ui.output_var.set("b")
    harness.ui.interval_var.set(100)
    harness.ui.window_title_var.set("Test Window")
    
    # Add second slot (this saves slot 0 and switches to slot 1)
    harness.ui._add_slot()
    harness.pump()
    
    # Configure second slot (index 1)
    harness.ui.trigger_var.set("x")
    harness.ui.output_var.set("y")
    harness.ui.interval_var.set(200)
    harness.ui.window_title_var.set("Another Window")
    
    # Simulate clicking on first slot in listbox
    # This should save slot 1's data and load slot 0's data
    harness.ui.slot_listbox.selection_clear(0, tk.END)
    harness.ui.slot_listbox.selection_set(0)
    harness.ui._on_slot_select(None)
    harness.pump()
    
    # Check that UI shows first slot's data
    assert harness.ui.trigger_var.get() == "a"
    assert harness.ui.output_var.get() == "b"
    assert harness.ui.interval_var.get() == 100
    assert harness.ui.window_title_var.get() == "Test Window"


def test_save_slot_data_on_switch(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that slot data is saved when switching slots."""
    harness = multi_slot_ui
    harness.pump()
    
    # Configure first slot
    harness.ui.trigger_var.set("q")
    harness.ui.output_var.set("w")
    harness.ui.interval_var.set(75)
    
    # Add second slot (this should save first slot's data)
    harness.ui._add_slot()
    harness.pump()
    
    # Check first slot was saved
    slot0 = harness.ui.config.slots[0]
    assert slot0.trigger_key == "q"
    assert slot0.output_key == "w"
    assert slot0.interval_ms == 75


def test_toggle_slot_enabled(multi_slot_ui: MultiSlotHarness) -> None:
    """Test toggling slot enabled state."""
    harness = multi_slot_ui
    harness.pump()
    
    # Get initial state
    slot = harness.ui.config.slots[0]
    initial_state = slot.enabled
    
    # Toggle enabled
    harness.ui._toggle_slot_enabled()
    harness.pump()
    
    assert slot.enabled == (not initial_state)
    
    # Toggle again
    harness.ui._toggle_slot_enabled()
    harness.pump()
    
    assert slot.enabled == initial_state


def test_slot_list_display_format(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that slot list shows correct format."""
    harness = multi_slot_ui
    harness.pump()
    
    # Configure first slot
    harness.ui.trigger_var.set("e")
    harness.ui.output_var.set("r")
    harness.ui.interval_var.set(50)
    harness.ui._save_current_slot_to_config()
    harness.ui._update_slot_list()
    harness.pump()
    
    # Check listbox content
    item_text = harness.ui.slot_listbox.get(0)
    assert "E → R" in item_text
    assert "@50ms" in item_text
    assert "✓" in item_text  # Enabled marker


def test_start_with_current_slot(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that starting uses the current slot."""
    harness = multi_slot_ui
    harness.pump()
    
    # Add multiple slots
    harness.ui._add_slot()
    harness.ui._add_slot()
    harness.pump()
    
    # Select second slot
    harness.ui.current_slot_index = 1
    harness.ui.trigger_var.set("m")
    harness.ui.output_var.set("n")
    harness.ui.interval_var.set(60)
    harness.ui._save_current_slot_to_config()
    
    # Start autofire
    harness.ui.start_autofire()
    harness.pump()
    
    # Check that engine is using slot 1
    assert harness.ui.engine.slot.trigger_key == "m"
    assert harness.ui.engine.slot.output_key == "n"
    assert harness.ui.engine.slot.interval_ms == 60


def test_multilanguage_slot_ui(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that slot UI elements update with language toggle."""
    harness = multi_slot_ui
    harness.pump()
    
    # Check English labels
    assert harness.ui.ui_elements['slot_frame'].cget('text') == "Slots"
    assert harness.ui.ui_elements['add_slot_btn'].cget('text') == "Add Slot"
    assert harness.ui.ui_elements['remove_slot_btn'].cget('text') == "Remove Slot"
    
    # Toggle to Traditional Chinese
    harness.ui.toggle_language()
    harness.pump()
    
    # Check Chinese labels
    assert harness.ui.ui_elements['slot_frame'].cget('text') == "插槽"
    assert harness.ui.ui_elements['add_slot_btn'].cget('text') == "新增插槽"
    assert harness.ui.ui_elements['remove_slot_btn'].cget('text') == "移除插槽"


def test_config_persistence_with_multiple_slots(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that config with multiple slots is saved correctly."""
    harness = multi_slot_ui
    harness.pump()
    
    # Create multiple slots with different configs
    harness.ui.trigger_var.set("a")
    harness.ui.output_var.set("b")
    harness.ui._save_current_slot_to_config()
    
    harness.ui._add_slot()
    harness.ui.trigger_var.set("c")
    harness.ui.output_var.set("d")
    harness.ui._save_current_slot_to_config()
    
    harness.ui._add_slot()
    harness.ui.trigger_var.set("e")
    harness.ui.output_var.set("f")
    harness.ui._save_current_slot_to_config()
    
    # Save config
    harness.ui.config.language = "en"
    saved_config = harness.ui.config
    
    # Verify saved config has all slots
    assert len(saved_config.slots) == 3
    assert saved_config.slots[0].trigger_key == "a"
    assert saved_config.slots[0].output_key == "b"
    assert saved_config.slots[1].trigger_key == "c"
    assert saved_config.slots[1].output_key == "d"
    assert saved_config.slots[2].trigger_key == "e"
    assert saved_config.slots[2].output_key == "f"


def test_disabled_slot_shown_in_list(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that disabled slots show with ✗ marker."""
    harness = multi_slot_ui
    harness.pump()
    
    # Disable the slot
    slot = harness.ui.config.slots[0]
    slot.enabled = False
    harness.ui._update_slot_list()
    harness.pump()
    
    # Check listbox shows disabled marker
    item_text = harness.ui.slot_listbox.get(0)
    assert "✗" in item_text


def test_multiple_slots_simultaneously(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that multiple enabled slots can be active simultaneously."""
    harness = multi_slot_ui
    harness.pump()
    
    # Configure first slot: Q -> W
    harness.ui.trigger_var.set("q")
    harness.ui.output_var.set("w")
    harness.ui.interval_var.set(50)
    harness.ui._save_current_slot_to_config()
    
    # Add second slot: E -> R
    harness.ui._add_slot()
    harness.ui.trigger_var.set("e")
    harness.ui.output_var.set("r")
    harness.ui.interval_var.set(50)
    harness.ui._save_current_slot_to_config()
    
    # Add third slot: A -> S
    harness.ui._add_slot()
    harness.ui.trigger_var.set("a")
    harness.ui.output_var.set("s")
    harness.ui.interval_var.set(50)
    harness.ui._save_current_slot_to_config()
    
    # Verify all slots are enabled
    assert all(slot.enabled for slot in harness.ui.config.slots)
    assert len(harness.ui.config.slots) == 3
    
    # Start autofire (should bind all 3 slots)
    harness.ui.start_autofire()
    harness.pump()
    
    # Verify engine is running with all slots
    assert harness.ui.engine.is_running
    assert len(harness.ui.engine._slots) == 3
    
    # Verify all trigger keys are registered
    assert "q" in harness.ui.engine._slot_states
    assert "e" in harness.ui.engine._slot_states
    assert "a" in harness.ui.engine._slot_states


def test_disabled_slots_not_activated(multi_slot_ui: MultiSlotHarness) -> None:
    """Test that disabled slots are not activated when starting."""
    harness = multi_slot_ui
    harness.pump()
    
    # Configure first slot and keep enabled
    harness.ui.trigger_var.set("q")
    harness.ui.output_var.set("w")
    harness.ui._save_current_slot_to_config()
    
    # Add second slot
    harness.ui._add_slot()
    harness.ui.trigger_var.set("e")
    harness.ui.output_var.set("r")
    harness.ui._save_current_slot_to_config()
    
    # Disable second slot
    harness.ui.config.slots[1].enabled = False
    
    # Start autofire (should only bind slot 0)
    harness.ui.start_autofire()
    harness.pump()
    
    # Verify engine is running with only 1 slot
    assert harness.ui.engine.is_running
    assert len(harness.ui.engine._slots) == 1
    assert harness.ui.engine._slots[0].trigger_key == "q"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
