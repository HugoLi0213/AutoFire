import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pytest


class FakeHotkey:
    def __init__(self, key: str, callback: Callable[[], None], *, trigger_on_release: bool, suppress: bool) -> None:
        self.key = key
        self.callback = callback
        self.trigger_on_release = trigger_on_release
        self.suppress = suppress


class FakeKeyboardBackend:
    def __init__(self) -> None:
        self._handlers: Dict[int, FakeHotkey] = {}
        self._handler_seq = 1
        self._pressed: Dict[str, int] = {}
        self.press_history: List[str] = []
        self.block_calls: List[str] = []
        self.unblock_calls: List[str] = []
        self._suppressed_keys: set[str] = set()
        self._press_hooks: Dict[int, tuple[str, Callable]] = {}
        self._release_hooks: Dict[int, tuple[str, Callable]] = {}
        self._hook_seq = 1

    # keyboard-like API ---------------------------------------------------------
    def press_and_release(self, key: str) -> None:
        self.press_history.append(key)

    def is_pressed(self, key: str) -> bool:
        return key in self._pressed

    def block_key(self, key: str) -> None:
        self.block_calls.append(key)
        self._suppressed_keys.add(key)

    def unblock_key(self, key: str) -> None:
        self.unblock_calls.append(key)
        self._suppressed_keys.discard(key)

    def write(self, text: str) -> None:
        self.press_history.append(text)

    def add_hotkey(self, key: str, callback: Callable[[], None], *, suppress: bool = False, trigger_on_release: bool = False) -> int:
        handler_id = self._handler_seq
        self._handler_seq += 1
        self._handlers[handler_id] = FakeHotkey(key, callback, trigger_on_release=trigger_on_release, suppress=suppress)
        return handler_id

    def remove_hotkey(self, handler_id: int) -> None:
        self._handlers.pop(handler_id, None)

    def on_press_key(self, key: str, callback: Callable, suppress: bool = False):  # noqa: ARG002 - suppress unused in fake
        handle = self._hook_seq
        self._hook_seq += 1
        self._press_hooks[handle] = (key, callback)
        return handle

    def on_release_key(self, key: str, callback: Callable, suppress: bool = False):  # noqa: ARG002
        handle = self._hook_seq
        self._hook_seq += 1
        self._release_hooks[handle] = (key, callback)
        return handle

    def unhook(self, handle) -> None:
        self._press_hooks.pop(handle, None)
        self._release_hooks.pop(handle, None)

    # test helpers --------------------------------------------------------------
    def simulate_keydown(self, key: str) -> None:
        self._pressed[key] = self._pressed.get(key, 0) + 1
        for hotkey in list(self._handlers.values()):
            if hotkey.key == key and not hotkey.trigger_on_release:
                hotkey.callback()
        for hook_key, callback in list(self._press_hooks.values()):
            if hook_key == key:
                callback(None)

    def simulate_keyup(self, key: str) -> None:
        if key in self._pressed:
            self._pressed[key] = max(0, self._pressed[key] - 1)
            if self._pressed[key] == 0:
                del self._pressed[key]
        for hotkey in list(self._handlers.values()):
            if hotkey.key == key and hotkey.trigger_on_release:
                hotkey.callback()
        for hook_key, callback in list(self._release_hooks.values()):
            if hook_key == key:
                callback(None)

    def was_key_suppressed(self, key: str) -> bool:
        return key in self._suppressed_keys

    def simulate_hotkey(self, key: str) -> None:
        for hotkey in list(self._handlers.values()):
            if hotkey.key == key:
                hotkey.callback()


class FakeClock:
    def __init__(self) -> None:
        self._now_ms = 0
        self._listeners: List[Callable[[float], None]] = []

    def now(self) -> float:
        return self._now_ms / 1000.0

    def sleep(self, seconds: float) -> None:
        self.advance(int(math.ceil(seconds * 1000)))

    def advance(self, milliseconds: int) -> None:
        target = self._now_ms + max(0, milliseconds)
        # Notify listeners at 1ms increments to keep scheduling granular
        while self._now_ms < target:
            self._now_ms += 1
            current = self.now()
            for listener in list(self._listeners):
                listener(current)

    def register_listener(self, listener: Callable[[float], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: Callable[[float], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def advance_ms(self, milliseconds: int) -> None:
        self.advance(milliseconds)


@dataclass
class ProfileManagerFake:
    current_profile: str = "A"
    switch_log: List[str] = None

    def __post_init__(self) -> None:
        if self.switch_log is None:
            self.switch_log = []

    def get_current_profile(self) -> str:
        return self.current_profile

    def switch_to(self, profile_id: str) -> None:
        self.switch_log.append(profile_id)
        self.current_profile = profile_id


@pytest.fixture
def fake_keyboard_backend() -> FakeKeyboardBackend:
    return FakeKeyboardBackend()


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def profile_manager_fake() -> ProfileManagerFake:
    return ProfileManagerFake()


@pytest.fixture
def status_spy() -> List[str]:
    messages: List[str] = []
    return messages
