from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List

import pytest

import autofire


class FakeKeyboard:
    def __init__(self) -> None:
        self.press_calls: List[str] = []
        self.block_calls: List[str] = []
        self.unblock_calls: List[str] = []
        self._pressed: set[str] = set()
        self._blocked: set[str] = set()
        self._press_hooks: Dict[Any, tuple[str, Callable[[Any], None]]] = {}
        self._release_hooks: Dict[Any, tuple[str, Callable[[Any], None]]] = {}
        self._hotkeys: Dict[Any, Callable[[], None]] = {}
        self._hooks: Dict[Any, Callable[[Any], None]] = {}
        self._next_handle = 1
        self._press_event = threading.Event()
        self.is_pressed_queries: List[tuple[str, bool]] = []
        self._clock: Callable[[], float] | None = None
        self.press_events: List[tuple[str, float]] = []
        self._hold_end_time: float | None = None
        self._use_threads = True

    # keyboard API -------------------------------------------------------------
    def press_and_release(self, key: str) -> None:
        self.press_calls.append(key)
        if self._clock is not None:
            self.press_events.append((key, self._clock()))
        self._press_event.set()

    def is_pressed(self, key: str) -> bool:
        result = key in self._pressed
        if result and self._hold_end_time is not None and self._clock is not None:
            result = self._clock() < self._hold_end_time
        self.is_pressed_queries.append((key, result))
        return result

    def block_key(self, key: str) -> None:
        self._blocked.add(key)
        self.block_calls.append(key)

    def unblock_key(self, key: str) -> None:
        self._blocked.discard(key)
        self.unblock_calls.append(key)

    def on_press_key(
        self, key: str, callback: Callable[[Any], None], *, suppress: bool = False  # noqa: ARG002
    ) -> Any:
        handle = f"press-{self._next_handle}"
        self._next_handle += 1
        self._press_hooks[handle] = (key, callback)
        return handle

    def on_release_key(
        self, key: str, callback: Callable[[Any], None], *, suppress: bool = False  # noqa: ARG002
    ) -> Any:
        handle = f"release-{self._next_handle}"
        self._next_handle += 1
        self._release_hooks[handle] = (key, callback)
        return handle

    def unhook(self, handle: Any) -> None:
        self._press_hooks.pop(handle, None)
        self._release_hooks.pop(handle, None)
        self._hooks.pop(handle, None)

    def add_hotkey(
        self, combo: str, callback: Callable[[], None], suppress: bool = False  # noqa: ARG002
    ) -> Any:
        handle = f"hotkey-{self._next_handle}"
        self._next_handle += 1
        self._hotkeys[handle] = callback
        return handle

    def remove_hotkey(self, handle: Any) -> None:
        self._hotkeys.pop(handle, None)

    def release(self, key: str) -> None:
        self._pressed.discard(key)

    # helpers ------------------------------------------------------------------
    def simulate_keydown(self, key: str) -> None:
        self._pressed.add(key)
        event = SimpleNamespace(name=key, event_type="down")
        for stored_key, callback in list(self._press_hooks.values()):
            if stored_key == key:
                self._invoke_async(callback, event)
        for callback in list(self._hooks.values()):
            self._invoke_async(callback, event)

    def simulate_keyup(self, key: str) -> None:
        self._pressed.discard(key)
        event = SimpleNamespace(name=key, event_type="up")
        for stored_key, callback in list(self._release_hooks.values()):
            if stored_key == key:
                self._invoke_async(callback, event)
        for callback in list(self._hooks.values()):
            self._invoke_async(callback, event)

    def simulate_hotkey(self, combo: str) -> None:
        for callback in list(self._hotkeys.values()):
            self._invoke_async(callback, None)

    def attach_clock(self, clock: FakeClock) -> None:
        self._clock = clock.now

    def set_async_callbacks(self, enabled: bool) -> None:
        self._use_threads = bool(enabled)

    def hook(self, callback: Callable[[Any], None], suppress: bool = False) -> Any:  # noqa: ARG002
        self._hooks[callback] = callback
        return callback

    def set_hold_duration(self, seconds: float) -> None:
        if self._clock is None:
            self._hold_end_time = None
            return
        base = self._clock()
        self._hold_end_time = base + max(0.0, seconds)

    def key_to_scan_codes(self, key: str) -> List[int]:
        normalized = (key or "").strip().lower()
        if not normalized or normalized.startswith("invalid"):
            raise ValueError(f"Unknown key '{key}'")
        return [1]

    def _invoke_async(self, callback: Callable[[Any], None], event: Any) -> None:
        if self._use_threads:
            thread = threading.Thread(target=callback, args=(event,), daemon=True)
            thread.start()
        else:
            callback(event)

    def clear_calls(self) -> None:
        self.press_calls.clear()
        self.block_calls.clear()
        self.unblock_calls.clear()
        self._press_event.clear()
        self.press_events.clear()
        self._hold_end_time = None

    def has_active_hooks(self) -> bool:
        return bool(self._press_hooks or self._release_hooks or self._hooks)

    def is_blocked(self, key: str) -> bool:
        return key in self._blocked


class FakeClock:
    def __init__(self) -> None:
        self._now = 0.0
        self._cv = threading.Condition()
        self._auto_advance = False

    def now(self) -> float:
        with self._cv:
            return self._now

    def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        target = self._now + seconds
        if self._auto_advance:
            with self._cv:
                self._now = max(self._now, target)
                return
        with self._cv:
            while self._now < target:
                remaining = target - self._now
                timeout = min(remaining, 0.01)
                self._cv.wait(timeout=timeout)
                if self._now < target and timeout == 0.01:
                    self._now = target
                    break

    def advance_ms(self, milliseconds: int) -> None:
        if milliseconds < 0:
            raise ValueError("Milliseconds must be non-negative")
        with self._cv:
            self._now += milliseconds / 1000.0
            self._cv.notify_all()

    def enable_auto_advance(self) -> None:
        with self._cv:
            self._auto_advance = True


@pytest.fixture
def fake_keyboard(monkeypatch: pytest.MonkeyPatch) -> FakeKeyboard:
    keyboard_backend = FakeKeyboard()
    monkeypatch.setattr(autofire, "keyboard", keyboard_backend, raising=False)
    return keyboard_backend


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def config_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("cfg") / "autofire.json"


def build_app(
    config: autofire.AutoFireConfig,
    keyboard_backend: FakeKeyboard,
    clock: FakeClock,
    config_path: Path,
) -> autofire.AutoFireApp:
    app = autofire.AutoFireApp(
        config,
        keyboard_module=keyboard_backend,
        now=clock.now,
        sleep=clock.sleep,
        config_path=config_path,
        poll_seconds=0.2,
    )
    keyboard_backend.attach_clock(clock)
    app.start(start_watcher=False)
    keyboard_backend.clear_calls()
    return app


def advance_in_steps(clock: FakeClock, total_ms: int, step_ms: int) -> None:
    remaining = max(0, total_ms)
    step = max(1, step_ms)
    while remaining > 0:
        slice_ms = min(step, remaining)
        clock.advance_ms(slice_ms)
        time.sleep(0)
        remaining -= slice_ms


def wait_for(predicate: Callable[[], bool], timeout: float = 0.5) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(0.001)
    return predicate()


@pytest.mark.parametrize(
    ("trigger", "output", "interval"),
    [
        ("e", "r", 10),
        ("f1", "a", 75),
        ("x", "z", 1),
    ],
)
def test_whileheld_interval_accuracy(
    trigger: str,
    output: str,
    interval: int,
    fake_keyboard: FakeKeyboard,
    fake_clock: FakeClock,
    config_path: Path,
) -> None:
    config = autofire.AutoFireConfig(
        trigger_key=trigger,
        output_key=output,
        interval_ms=interval,
        pass_through=False,
    )
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    try:
        fake_clock.enable_auto_advance()
        fake_keyboard.set_hold_duration(0.1)
        fake_keyboard.simulate_keydown(trigger)
        assert wait_for(lambda: app.is_running)

        assert wait_for(lambda: len(fake_keyboard.press_events) >= 2, timeout=0.1)
        fake_keyboard.simulate_keyup(trigger)
        wait_for(lambda: not app.is_running)

        events = [timestamp for key, timestamp in fake_keyboard.press_events if key == output]
        assert len(events) >= 2
        deltas = [
            (later - earlier) * 1000.0
            for earlier, later in zip(events, events[1:])
        ]
        tolerance = max(1.0, interval * 0.25)
        for delta in deltas:
            assert abs(delta - interval) <= tolerance
    finally:
        app.shutdown()


def test_stop_on_release_is_immediate(
    fake_keyboard: FakeKeyboard,
    fake_clock: FakeClock,
    config_path: Path,
) -> None:
    config = autofire.AutoFireConfig(interval_ms=15, pass_through=False)
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    try:
        fake_keyboard.simulate_keydown(config.trigger_key)
        assert wait_for(lambda: app.is_running)

        advance_in_steps(fake_clock, 30, 5)
        before = len(fake_keyboard.press_calls)
        fake_keyboard.simulate_keyup(config.trigger_key)
        wait_for(lambda: not app.is_running)
        advance_in_steps(fake_clock, 20, 5)
        after = len(fake_keyboard.press_calls)
        assert after == before
    finally:
        app.shutdown()


def test_pass_through_false_blocks_trigger(
    fake_keyboard: FakeKeyboard,
    fake_clock: FakeClock,
    config_path: Path,
) -> None:
    config = autofire.AutoFireConfig(pass_through=False)
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    try:
        trigger = config.trigger_key
        fake_keyboard.simulate_keydown(trigger)
        assert wait_for(lambda: app.is_running)

        advance_in_steps(fake_clock, 60, 10)
        fake_keyboard.simulate_keyup(trigger)
        wait_for(lambda: not app.is_running)
        advance_in_steps(fake_clock, 20, 5)

        assert fake_keyboard.block_calls.count(trigger) == 1
        assert fake_keyboard.unblock_calls.count(trigger) == 1
        assert trigger not in fake_keyboard.press_calls
    finally:
        app.shutdown()


def test_pass_through_true_allows_trigger(
    fake_keyboard: FakeKeyboard,
    fake_clock: FakeClock,
    config_path: Path,
) -> None:
    config = autofire.AutoFireConfig(pass_through=True)
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    try:
        trigger = config.trigger_key
        output = config.output_key
        fake_keyboard.simulate_keydown(trigger)
        assert wait_for(lambda: app.is_running)

        advance_in_steps(fake_clock, 40, 10)
        wait_for(lambda: bool(fake_keyboard.press_calls), timeout=0.2)
        fake_keyboard.simulate_keyup(trigger)
        wait_for(lambda: not app.is_running)

        assert fake_keyboard.block_calls == []
        assert fake_keyboard.unblock_calls == []
        assert any(key == output for key in fake_keyboard.press_calls)
    finally:
        app.shutdown()


def test_parameter_validation(
    fake_keyboard: FakeKeyboard,
    fake_clock: FakeClock,
    config_path: Path,
) -> None:
    config = autofire.AutoFireConfig()
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    try:
        with pytest.raises(ValueError, match="Unknown key"):
            autofire.validate_config(
                {"triggerKey": "invalid", "outputKey": "r", "intervalMs": 50}
            )
        with pytest.raises(ValueError, match="between"):
            autofire.validate_config(
                {"triggerKey": "e", "outputKey": "r", "intervalMs": 0}
            )
        assert not app.is_running
    finally:
        app.shutdown()


def test_emergency_stop(
    fake_keyboard: FakeKeyboard,
    fake_clock: FakeClock,
    config_path: Path,
) -> None:
    config = autofire.AutoFireConfig(pass_through=False, interval_ms=20)
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    try:
        trigger = config.trigger_key
        fake_keyboard.simulate_keydown(trigger)
        assert wait_for(lambda: app.is_running)
        advance_in_steps(fake_clock, 60, 10)
        wait_for(lambda: bool(fake_keyboard.press_calls), timeout=0.2)
        before = len(fake_keyboard.press_calls)

        app.emergency_stop()
        wait_for(lambda: not app.is_running)
        advance_in_steps(fake_clock, 20, 5)

        after = len(fake_keyboard.press_calls)
        assert after == before
        assert fake_keyboard.unblock_calls.count(trigger) >= 1
    finally:
        app.shutdown()


def test_teardown_unhooks_and_no_leaks(
    fake_keyboard: FakeKeyboard,
    fake_clock: FakeClock,
    config_path: Path,
) -> None:
    config = autofire.AutoFireConfig(interval_ms=25, pass_through=False)
    app = build_app(config, fake_keyboard, fake_clock, config_path)
    trigger = config.trigger_key
    try:
        fake_keyboard.simulate_keydown(trigger)
        assert wait_for(lambda: app.is_running)
        advance_in_steps(fake_clock, 50, 10)
        fake_keyboard.simulate_keyup(trigger)
        wait_for(lambda: not app.is_running)
    finally:
        app.shutdown()

    assert not app.is_running
    assert getattr(app, "_worker", None) is None
    assert not fake_keyboard.has_active_hooks()
    assert not fake_keyboard.is_blocked(trigger)
    assert fake_keyboard._hotkeys == {}