from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Callable, Iterator

import pytest

pytest.importorskip("tkinter")

import tkinter as tk

import autofire_ui

from tests.test_autofire_runner import FakeClock, FakeKeyboard, advance_in_steps

@dataclass
class UIHarness:
    ui: autofire_ui.AutoFireUI
    root: tk.Tk
    keyboard: FakeKeyboard
    clock: FakeClock
    saved_configs: list[autofire_ui.AutoFireConfig]
    messagebox_calls: list[tuple[str, str]]
    after_queue: Queue[Callable[[], None]]
    closed: bool = False

    def pump(self, cycles: int = 3) -> None:
        for _ in range(cycles):
            if self.closed:
                break
            try:
                self.root.update_idletasks()
                self.root.update()
            except tk.TclError:
                self.closed = True
            self._drain_after_queue()
            if self.closed:
                break

    def advance(self, total_ms: int, step_ms: int = 5) -> None:
        advance_in_steps(self.clock, total_ms, step_ms)
        self.pump()

    def wait_for_status(self, suffix: str, timeout: float = 0.5) -> bool:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self.pump()
            if suffix in self.ui.status_var.get():
                return True
            time.sleep(0.001)
        self.pump()
        return suffix in self.ui.status_var.get()

    def close(self) -> None:
        if not self.closed:
            try:
                self.ui.on_close()
            finally:
                self.closed = True

    def _drain_after_queue(self) -> None:
        while True:
            try:
                callback = self.after_queue.get_nowait()
            except Empty:
                break
            callback()


@pytest.fixture(scope="session")
def tk_root() -> Iterator[tk.Tk]:
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        if root.winfo_exists():
            root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def keyboard_backend(monkeypatch: pytest.MonkeyPatch) -> FakeKeyboard:
    fake = FakeKeyboard()
    monkeypatch.setattr(autofire_ui, "keyboard", fake, raising=False)
    return fake


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    clock = FakeClock()
    monkeypatch.setattr(autofire_ui.time, "perf_counter", clock.now)
    monkeypatch.setattr(autofire_ui.time, "sleep", clock.sleep)
    return clock


@pytest.fixture
def messagebox_spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def fake_showerror(title: str, message: str, *, parent: tk.Misc | None = None) -> None:  # noqa: ARG001
        calls.append((title, message))

    monkeypatch.setattr(autofire_ui.messagebox, "showerror", fake_showerror)
    return calls


@pytest.fixture
def ui_harness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    keyboard_backend: FakeKeyboard,
    fake_clock: FakeClock,
    messagebox_spy: list[tuple[str, str]],
    tk_root: tk.Tk,
) -> Iterator[UIHarness]:
    config_file = tmp_path / "autofire.json"
    monkeypatch.setattr(autofire_ui, "CONFIG_PATH", config_file)
    monkeypatch.setattr(autofire_ui, "load_config", lambda: autofire_ui.AutoFireConfig())
    saved_configs: list[autofire_ui.AutoFireConfig] = []

    def fake_save(config: autofire_ui.AutoFireConfig) -> None:
        saved_configs.append(config)

    monkeypatch.setattr(autofire_ui, "save_config", fake_save)
    monkeypatch.setattr(autofire_ui.sys, "platform", "win32")
    keyboard_backend.attach_clock(fake_clock)
    keyboard_backend.set_async_callbacks(False)

    root = tk.Toplevel(tk_root)
    root.withdraw()

    after_queue: Queue[Callable[[], None]] = Queue()

    def safe_after(self: tk.Misc, delay_ms: int, callback: Callable[..., None], *args: object) -> str:  # noqa: ARG001
        def runner() -> None:
            callback(*args)

        after_queue.put(runner)
        return f"after-{after_queue.qsize()}"

    def safe_after_cancel(self: tk.Misc, handle: str) -> None:  # noqa: ARG001
        return None

    root.after = safe_after.__get__(root, tk.Misc)
    root.after_cancel = safe_after_cancel.__get__(root, tk.Misc)

    ui = autofire_ui.AutoFireUI(root)
    autofire_ui.APP = ui

    harness = UIHarness(
        ui=ui,
        root=root,
        keyboard=keyboard_backend,
        clock=fake_clock,
        saved_configs=saved_configs,
        messagebox_calls=messagebox_spy,
        after_queue=after_queue,
    )

    yield harness

    if not harness.closed:
        harness.close()
    else:
        try:
            if harness.root.winfo_exists():
                harness.root.destroy()
        except tk.TclError:
            pass
    autofire_ui.APP = None


def test_trigger_press_runs_until_release(ui_harness: UIHarness) -> None:
    harness = ui_harness
    harness.ui.trigger_var.set("e")
    harness.ui.output_var.set("r")
    harness.ui.interval_spin.delete(0, tk.END)
    harness.ui.interval_spin.insert(0, "10")
    harness.ui.pass_var.set(False)

    harness.ui.start_button.invoke()
    harness.pump()

    harness.keyboard.clear_calls()
    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[Running]")

    for _ in range(5):
        harness.advance(10, 5)

    harness.keyboard.simulate_keyup("e")
    harness.advance(20, 5)
    assert harness.wait_for_status("[Stopped]")

    pulses = [key for key in harness.keyboard.press_calls if key == "r"]
    assert 4 <= len(pulses) <= 6
    assert harness.ui.status_var.get().endswith("[Stopped]")


def test_pass_through_modes_control_blocking(ui_harness: UIHarness) -> None:
    harness = ui_harness

    harness.ui.pass_var.set(True)
    harness.ui.start_button.invoke()
    harness.pump()

    harness.keyboard.clear_calls()
    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[Running]")
    harness.advance(40, 10)
    harness.keyboard.simulate_keyup("e")
    harness.advance(20, 5)
    assert harness.wait_for_status("[Stopped]")

    assert harness.keyboard.block_calls == []
    assert harness.keyboard.unblock_calls == []
    assert any(key == "r" for key in harness.keyboard.press_calls)

    harness.ui.stop_button.invoke()
    harness.pump()
    harness.keyboard.clear_calls()

    harness.ui.pass_var.set(False)
    harness.ui.start_button.invoke()
    harness.pump()

    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[Running]")
    harness.advance(40, 10)
    harness.keyboard.simulate_keyup("e")
    harness.advance(20, 5)
    assert harness.wait_for_status("[Stopped]")

    assert harness.keyboard.block_calls.count("e") >= 1
    assert harness.keyboard.unblock_calls.count("e") >= 1
    assert all(key != "e" for key in harness.keyboard.press_calls)


def test_capture_buttons_update_entries(ui_harness: UIHarness) -> None:
    harness = ui_harness

    harness.ui.trigger_capture_button.invoke()
    harness.keyboard.simulate_keydown("f1")
    harness.keyboard.simulate_keyup("f1")
    harness.pump()

    assert harness.ui.trigger_var.get() == "f1"
    assert not harness.keyboard.has_active_hooks()

    harness.ui.output_capture_button.invoke()
    harness.keyboard.simulate_keydown("z")
    harness.keyboard.simulate_keyup("z")
    harness.pump()

    assert harness.ui.output_var.get() == "z"
    assert not harness.keyboard.has_active_hooks()


def test_interval_validation_clamps_and_saves(ui_harness: UIHarness) -> None:
    harness = ui_harness

    harness.ui.interval_spin.delete(0, tk.END)
    harness.ui.interval_spin.insert(0, "0")
    harness.ui.start_button.invoke()
    harness.pump()

    assert harness.saved_configs[-1].interval_ms == autofire_ui.MIN_INTERVAL_MS
    assert f"@ {autofire_ui.MIN_INTERVAL_MS}ms" in harness.ui.status_var.get()
    assert harness.messagebox_calls == []

    harness.ui.stop_button.invoke()
    harness.pump()

    harness.ui.interval_spin.delete(0, tk.END)
    harness.ui.interval_spin.insert(0, "5000")
    harness.ui.start_button.invoke()
    harness.pump()

    assert harness.saved_configs[-1].interval_ms == autofire_ui.MAX_INTERVAL_MS
    assert f"@ {autofire_ui.MAX_INTERVAL_MS}ms" in harness.ui.status_var.get()
    assert harness.messagebox_calls == []


def test_start_stop_buttons_reflect_status(ui_harness: UIHarness) -> None:
    harness = ui_harness

    harness.ui.start_button.invoke()
    harness.pump()
    assert harness.ui.start_button.instate(["!disabled"])
    assert harness.ui.stop_button.instate(["disabled"])

    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[Running]")
    assert harness.ui.start_button.instate(["disabled"])
    assert harness.ui.stop_button.instate(["!disabled"])

    harness.advance(30, 5)
    harness.keyboard.simulate_keyup("e")
    harness.advance(20, 5)
    assert harness.wait_for_status("[Stopped]")
    assert harness.ui.start_button.instate(["!disabled"])
    assert harness.ui.stop_button.instate(["disabled"])

    harness.keyboard.clear_calls()
    harness.ui.start_button.invoke()
    harness.pump()
    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[Running]")
    harness.ui.stop_button.invoke()
    harness.advance(20, 5)
    assert harness.wait_for_status("[Stopped]")
    assert harness.ui.start_button.instate(["!disabled"])
    assert harness.ui.stop_button.instate(["disabled"])


def test_on_close_unhooks_and_clears_state(ui_harness: UIHarness) -> None:
    harness = ui_harness

    harness.ui.start_button.invoke()
    harness.pump()
    harness.keyboard.simulate_keydown("e")
    assert harness.wait_for_status("[Running]")

    harness.keyboard.simulate_keyup("e")
    harness.advance(10, 5)
    harness.close()

    assert not harness.keyboard.has_active_hooks()
    assert not harness.keyboard.is_blocked("e")