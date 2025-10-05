from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import pytest

import autofire


class FakeKeyboard:
    def __init__(self) -> None:
        self.press_calls: List[str] = []
        self.block_calls: List[str] = []
        self.unblock_calls: List[str] = []
        self._pressed: set[str] = set()
        self._press_hooks: Dict[Any, tuple[str, Callable[[Any], None]]] = {}
        self._release_hooks: Dict[Any, tuple[str, Callable[[Any], None]]] = {}
        self._hotkeys: Dict[Any, Callable[[], None]] = {}
        self._next_handle = 1
        letters = {chr(code) for code in range(ord("a"), ord("z") + 1)}
        digits = {str(d) for d in range(10)}
        functions = {f"f{i}" for i in range(1, 13)}
        self._valid_keys = letters | digits | functions

    # keyboard API -------------------------------------------------------
    def key_to_scan_codes(self, key: str) -> List[int]:
        key_lc = key.lower()
        if key_lc in self._valid_keys:
            return [1]
        raise ValueError(f"Unknown key {key}")

    def press_and_release(self, key: str) -> None:
        self.press_calls.append(key)

    def is_pressed(self, key: str) -> bool:
        return key in self._pressed

    def block_key(self, key: str) -> None:
        self.block_calls.append(key)

    def unblock_key(self, key: str) -> None:
        self.unblock_calls.append(key)

    def on_press_key(self, key: str, callback: Callable[[Any], None], *, suppress: bool = False) -> Any:  # noqa: ARG002
        handle = f"press-{self._next_handle}"
        self._next_handle += 1
        self._press_hooks[handle] = (key, callback)
        return handle

    def on_release_key(self, key: str, callback: Callable[[Any], None], *, suppress: bool = False) -> Any:  # noqa: ARG002
        handle = f"release-{self._next_handle}"
        self._next_handle += 1
        self._release_hooks[handle] = (key, callback)
        return handle

    def unhook(self, handle: Any) -> None:
        self._press_hooks.pop(handle, None)
        self._release_hooks.pop(handle, None)

    def add_hotkey(self, combo: str, callback: Callable[[], None], suppress: bool = False) -> Any:  # noqa: ARG002
        handle = f"hotkey-{self._next_handle}"
        self._next_handle += 1
        self._hotkeys[handle] = callback
        return handle

    def remove_hotkey(self, handle: Any) -> None:
        self._hotkeys.pop(handle, None)

    def release(self, key: str) -> None:
        self._pressed.discard(key)

    # helpers for tests --------------------------------------------------
    def simulate_keydown(self, key: str) -> None:
        self._pressed.add(key)
        for registered_key, callback in list(self._press_hooks.values()):
            if registered_key == key:
                callback(SimpleNamespace(name=key))

    def simulate_keyup(self, key: str) -> None:
        self._pressed.discard(key)
        for registered_key, callback in list(self._release_hooks.values()):
            if registered_key == key:
                callback(SimpleNamespace(name=key))

    def simulate_hotkey(self, combo: str) -> None:
        for callback in list(self._hotkeys.values()):
            callback()

    def clear_calls(self) -> None:
        self.press_calls.clear()
        self.block_calls.clear()
        self.unblock_calls.clear()


class FakeClock:
    def __init__(self) -> None:
        self._now = 0.0
        self._cv = threading.Condition()

    def now(self) -> float:
        with self._cv:
            return self._now

    def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        with self._cv:
            target = self._now + seconds
            while self._now < target:
                self._cv.wait()

    def advance_ms(self, milliseconds: int) -> None:
        if milliseconds < 0:
            return
        with self._cv:
            self._now += milliseconds / 1000.0
            self._cv.notify_all()


@pytest.fixture
def fake_keyboard(monkeypatch: pytest.MonkeyPatch) -> FakeKeyboard:
    keyboard = FakeKeyboard()
    monkeypatch.setattr(autofire, "keyboard", keyboard, raising=False)
    return keyboard


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "autofire.json"


def advance_in_steps(clock: FakeClock, total_ms: int, step_ms: int) -> None:
    remaining = max(0, total_ms)
    step = max(1, step_ms)
    yield_event = threading.Event()
    while remaining > 0:
        slice_ms = min(step, remaining)
        clock.advance_ms(slice_ms)
        # Allow other threads to process between clock jumps so the worker loop runs.
        yield_event.wait(0.001)
        remaining -= slice_ms


def wait_for(predicate: Callable[[], bool], timeout: float = 0.5) -> bool:
    deadline = time.perf_counter() + max(0.0, timeout)
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(0.001)
    return predicate()


def build_app(
    config: autofire.AutoFireConfig,
    fake_keyboard: FakeKeyboard,
    fake_clock: FakeClock,
    config_path: Path,
) -> autofire.AutoFireApp:
    return autofire.AutoFireApp(
        config,
        keyboard_module=fake_keyboard,
        now=fake_clock.now,
        sleep=fake_clock.sleep,
        config_path=config_path,
        poll_seconds=0.2,
    )


@pytest.mark.parametrize(
    "trigger,output,interval",
    [
        ("e", "r", 10),
        ("f1", "a", 75),
        ("x", "z", 1),
    ],
)
def test_arbitrary_keys_and_interval(trigger, output, interval, fake_keyboard, fake_clock, config_path):
    config = autofire.AutoFireConfig(trigger_key=trigger, output_key=output, interval_ms=interval, pass_through=False)
    autofire.write_config(config_path, config)
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    app.start(start_watcher=False)
    fake_keyboard.clear_calls()

    try:
        fake_keyboard.simulate_keydown(trigger)
        advance_in_steps(fake_clock, 100, max(1, interval))
        fake_keyboard.simulate_keyup(trigger)
        fake_clock.advance_ms(max(1, interval))
        app.stop_loop(join=True)

        pulses = [key for key in fake_keyboard.press_calls if key == output]
        expected = max(0, 100 // interval)
        assert expected - 1 <= len(pulses) <= expected + 1
        assert all(key == output for key in pulses)
    finally:
        app.shutdown()


def test_pass_through_toggle(fake_keyboard, fake_clock, config_path):
    config = autofire.AutoFireConfig(trigger_key="e", output_key="r", interval_ms=20, pass_through=False)
    autofire.write_config(config_path, config)
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    app.start(start_watcher=False)
    fake_keyboard.clear_calls()

    try:
        fake_keyboard.simulate_keydown("e")
        advance_in_steps(fake_clock, 60, 10)
        fake_keyboard.simulate_keyup("e")
        advance_in_steps(fake_clock, 20, 5)
        app.stop_loop(join=True)
        assert wait_for(lambda: not app._trigger_blocked)

        assert fake_keyboard.block_calls.count("e") == 1
        assert fake_keyboard.unblock_calls.count("e") == 1
        assert "e" not in fake_keyboard.press_calls

        app.apply_binding(
            autofire.AutoFireConfig(trigger_key="e", output_key="r", interval_ms=20, pass_through=True)
        )
        fake_keyboard.clear_calls()

        fake_keyboard.simulate_keydown("e")
        advance_in_steps(fake_clock, 40, 10)
        fake_keyboard.simulate_keyup("e")
        advance_in_steps(fake_clock, 20, 5)
        app.stop_loop(join=True)
        assert wait_for(lambda: not app._trigger_blocked)

        assert fake_keyboard.block_calls == []
        assert fake_keyboard.unblock_calls == []
        assert len(fake_keyboard.press_calls) > 0
    finally:
        app.shutdown()


def test_stop_on_release_fast(fake_keyboard, fake_clock, config_path):
    config = autofire.AutoFireConfig(trigger_key="e", output_key="r", interval_ms=15, pass_through=False)
    autofire.write_config(config_path, config)
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    app.start(start_watcher=False)
    fake_keyboard.clear_calls()

    try:
        fake_keyboard.simulate_keydown("e")
        advance_in_steps(fake_clock, 30, 5)
        before = len(fake_keyboard.press_calls)
        fake_keyboard.simulate_keyup("e")
        advance_in_steps(fake_clock, 20, 5)
        app.stop_loop(join=True)
        after = len(fake_keyboard.press_calls)
        assert before == after
    finally:
        app.shutdown()


def test_config_validation_and_defaults(fake_keyboard, fake_clock, config_path):
    if config_path.exists():
        config_path.unlink()
    default_config = autofire.load_config(config_path)
    assert default_config == autofire.AutoFireConfig()

    with pytest.raises(ValueError):
        autofire.validate_config({"triggerKey": "invalid", "outputKey": "r", "intervalMs": 50})

    with pytest.raises(ValueError):
        autofire.validate_config({"triggerKey": "e", "outputKey": "r", "intervalMs": 0})

    base = autofire.AutoFireConfig(trigger_key="e", output_key="r", interval_ms=50, pass_through=False)
    autofire.write_config(config_path, base)
    app = build_app(base, fake_keyboard, fake_clock, config_path)
    app.start(start_watcher=False)

    try:
        bad_payload = {"triggerKey": "e", "outputKey": "r", "intervalMs": 2000}
        config_path.write_text(json.dumps(bad_payload), encoding="utf-8")
        result = app.reload_config()
        assert result is False
        assert app.config == base
    finally:
        app.shutdown()


def test_hot_reload_applies_changes(fake_keyboard, fake_clock, config_path):
    config_a = autofire.AutoFireConfig(trigger_key="e", output_key="r", interval_ms=50, pass_through=False)
    autofire.write_config(config_path, config_a)
    app = build_app(config_a, fake_keyboard, fake_clock, config_path)
    app.start(start_watcher=False)
    fake_keyboard.clear_calls()

    try:
        config_b = autofire.AutoFireConfig(trigger_key="x", output_key="z", interval_ms=25, pass_through=False)
        autofire.write_config(config_path, config_b)
        assert app.reload_config() is True

        fake_keyboard.clear_calls()
        fake_keyboard.simulate_keydown("e")
        advance_in_steps(fake_clock, 40, 10)
        fake_keyboard.simulate_keyup("e")
        advance_in_steps(fake_clock, 10, 5)
        app.stop_loop(join=True)
        assert fake_keyboard.press_calls == []

        fake_keyboard.clear_calls()
        fake_keyboard.simulate_keydown("x")
        advance_in_steps(fake_clock, 150, 10)
        fake_keyboard.simulate_keyup("x")
        advance_in_steps(fake_clock, 15, 5)
        app.stop_loop(join=True)

        pulses = [key for key in fake_keyboard.press_calls if key == "z"]
        expected = max(0, 150 // 25)
        assert expected - 1 <= len(pulses) <= expected + 1
    finally:
        app.shutdown()
