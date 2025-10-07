from __future__ import annotations

from unittest.mock import call
import time
from typing import Callable


class FakeClock:
    def __init__(self, now: float = 0.0):
        self._now = now

    def now(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        self._now += seconds

    def advance(self, seconds: float) -> None:
        self._now += seconds


def advance_in_steps(clock: FakeClock, total_ms: int, step_ms: int) -> None:
    """Advances the clock in smaller steps to allow other events to process."""
    total_secs = total_ms / 1000.0
    step_secs = step_ms / 1000.0
    end_time = clock.now() + total_secs

    while clock.now() < end_time:
        clock.advance(min(step_secs, end_time - clock.now()))
        time.sleep(0)  # Yield to other threads/events if necessary in a real scenario


class FakeKeyboard:
    def __init__(self) -> None:
        self.press_calls: list[str] = []
        self.release_calls: list[str] = []
        self.block_calls: list[str] = []
        self.unblock_calls: list[str] = []
        self.hotkey_hooks: dict[str, Callable[[], None]] = {}
        self.key_hooks: dict[str, tuple[Callable, bool]] = {}
        self._is_pressed_map: dict[str, bool] = {}
        self._clock: FakeClock | None = None
        self._async_callbacks = True
        self.hook_key_calls: list = []  # Add this line

    def attach_clock(self, clock: FakeClock) -> None:
        self._clock = clock

    def set_async_callbacks(self, is_async: bool) -> None:
        self._async_callbacks = is_async

    def press(self, key: str) -> None:
        self.press_calls.append(key)

    def release(self, key: str) -> None:
        self.release_calls.append(key)

    def block_key(self, key: str) -> None:
        self.block_calls.append(key)

    def unblock_key(self, key: str) -> None:
        self.unblock_calls.append(key)

    def add_hotkey(self, hotkey: str, callback: Callable[[], None], suppress: bool = False) -> None:  # noqa
        self.hotkey_hooks[hotkey] = callback

    def remove_hotkey(self, hotkey: str | list) -> None:
        if isinstance(hotkey, list):
            hotkey = hotkey[0]  # simplified for test
        if hotkey in self.hotkey_hooks:
            del self.hotkey_hooks[hotkey]

    def on_press_key(self, key: str, callback: Callable, suppress: bool = False) -> None:
        """Records the hook registration."""
        self.key_hooks[key] = (callback, suppress)
        self.hook_key_calls.append(call(key, callback, suppress=suppress))

    def on_release_key(self, key: str, callback: Callable, suppress: bool = False) -> None:
        """Records the release hook registration."""
        release_key = f"release:{key}"
        self.key_hooks[release_key] = (callback, suppress)
        self.hook_key_calls.append(call(key, callback, suppress=suppress))

    def unhook_key(self, key: str) -> None:
        if key in self.key_hooks:
            del self.key_hooks[key]

    def unhook_all(self) -> None:
        self.hotkey_hooks.clear()
        self.key_hooks.clear()

    def is_pressed(self, key: str) -> bool:
        return self._is_pressed_map.get(key, False)

    def clear_calls(self) -> None:
        self.press_calls.clear()
        self.release_calls.clear()
        self.block_calls.clear()
        self.unblock_calls.clear()
        self.hook_key_calls.clear()

    def has_active_hooks(self) -> bool:
        return bool(self.hotkey_hooks or self.key_hooks)

    def is_blocked(self, key: str) -> bool:
        return self.block_calls.count(key) > self.unblock_calls.count(key)

    def simulate_keydown(self, key: str) -> None:
        self._is_pressed_map[key] = True
        event = type("KeyboardEvent", (), {"name": key})
        if key in self.key_hooks:
            self.key_hooks[key][0](event)
        if key in self.hotkey_hooks:
            self.hotkey_hooks[key]()

    def simulate_keyup(self, key: str) -> None:
        self._is_pressed_map[key] = False
        release_hook = f"release:{key}"
        if release_hook in self.key_hooks:
            event = type("KeyboardEvent", (), {"name": key})
            self.key_hooks[release_hook][0](event)


class FakeCtypes:
    def __init__(self):
        self.post_message_calls = []
        self.target_hwnd = 12345
        self.target_window_title = "Test Window"

    def clear_calls(self):
        self.post_message_calls.clear()

    @property
    def windll(self):
        return self

    @property
    def user32(self):
        return self

    def FindWindowW(self, lpClassName, lpWindowName):
        if lpWindowName == self.target_window_title:
            return self.target_hwnd
        return 0

    def PostMessageW(self, hWnd, Msg, wParam, lParam):
        self.post_message_calls.append((hWnd, Msg, wParam, lParam))

    def MapVirtualKeyW(self, vk_code, map_type):
        """Mock MapVirtualKeyW to return a fake scan code."""
        return vk_code  # Simplified: just return the vk_code as scan_code

    def SendInput(self, nInputs, pInputs, cbSize):
        """Mock SendInput - just return success."""
        return nInputs  # Return number of inputs successfully sent