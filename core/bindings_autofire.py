"""AutoFire bindings management using the keyboard library."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import keyboard

from .types import AutoFireBinding

logger = logging.getLogger(__name__)

NowFunc = Callable[[], float]
SleepFunc = Callable[[float], None]
StatusCallback = Callable[[str], None]
ErrorCallback = Callable[[str], None]


class AutoFireBindingRunner:
    """Runs an auto-fire loop while a trigger key is held."""

    def __init__(
        self,
        *,
        trigger_key: str,
        output_key: str,
        interval_ms: int,
        pass_through_trigger: bool,
        now: Optional[NowFunc] = None,
        sleep: Optional[SleepFunc] = None,
        keyboard_module=None,
    ) -> None:
        self.trigger_key = trigger_key
        self.output_key = output_key
        self.interval_s = max(0.001, interval_ms / 1000.0)
        self.pass_through_trigger = pass_through_trigger
        self._now = now or time.monotonic
        self._sleep = sleep or time.sleep
        self._keyboard = keyboard_module or keyboard
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._stop_request = threading.Event()
        self._blocked = False

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def start(self) -> None:
        if self.running:
            return
        try:
            if not self.pass_through_trigger and not self._blocked:
                self._keyboard.block_key(self.trigger_key)
                self._blocked = True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to block key %s", self.trigger_key)
            raise RuntimeError(f"Unable to block {self.trigger_key}: {exc}") from exc
        self._stop_request.clear()
        self._running.set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.running:
            return
        self._stop_request.set()
        self._running.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None
        if self._blocked:
            try:
                self._keyboard.unblock_key(self.trigger_key)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to unblock key %s", self.trigger_key)
            self._blocked = False

    def _loop(self) -> None:
        next_ts = self._now()
        try:
            while not self._stop_request.is_set():
                if not self._keyboard.is_pressed(self.trigger_key):
                    break
                now_ts = self._now()
                if now_ts >= next_ts:
                    try:
                        self._keyboard.press_and_release(self.output_key)
                    except Exception:  # noqa: BLE001
                        logger.exception("Failed to emit key %s", self.output_key)
                        break
                    next_ts = now_ts + self.interval_s
                else:
                    delay = max(0.0005, next_ts - now_ts)
                    self._sleep(delay)
        finally:
            self._stop_request.set()
            self._running.clear()
            if self._blocked:
                try:
                    self._keyboard.unblock_key(self.trigger_key)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to unblock key %s", self.trigger_key)
                self._blocked = False


@dataclass
class _AutoFireHandle:
    binding: AutoFireBinding
    runner: AutoFireBindingRunner
    press_handle: Optional[object]
    release_handle: Optional[object]


class AutoFireBindingRegistry:
    """Registers AutoFire bindings and keeps them coordinated."""

    def __init__(
        self,
        *,
        keyboard_module=None,
        now: Optional[NowFunc] = None,
        sleep: Optional[SleepFunc] = None,
        status_callback: Optional[StatusCallback] = None,
        error_callback: Optional[ErrorCallback] = None,
        register_emergency: bool = True,
    ) -> None:
        self._keyboard = keyboard_module or keyboard
        self._now = now or time.monotonic
        self._sleep = sleep or time.sleep
        self._status_callback = status_callback
        self._error_callback = error_callback
        self._handles: Dict[str, _AutoFireHandle] = {}
        self._emergency_hotkey_id: Optional[int] = None
        self._register_emergency = register_emergency

    # Lifecycle -----------------------------------------------------------------
    def clear(self) -> None:
        for handle in list(self._handles.values()):
            self._teardown_handle(handle)
        self._handles.clear()
        if self._emergency_hotkey_id is not None:
            try:
                self._keyboard.remove_hotkey(self._emergency_hotkey_id)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to remove emergency hotkey")
            self._emergency_hotkey_id = None

    def apply_bindings(self, bindings: Dict[str, AutoFireBinding]) -> None:
        self.clear()
        for binding in bindings.values():
            try:
                self.register(binding)
            except ValueError as exc:
                self._emit_error(str(exc))

    def register(self, binding: AutoFireBinding) -> None:
        trigger = binding.trigger_key
        if trigger in self._handles:
            existing = self._handles[trigger].binding
            if existing.id != binding.id:
                raise ValueError(f"AutoFire trigger '{trigger}' already registered")
            return
        runner = AutoFireBindingRunner(
            trigger_key=binding.trigger_key,
            output_key=binding.output_key,
            interval_ms=binding.interval_ms,
            pass_through_trigger=binding.pass_through_trigger,
            now=self._now,
            sleep=self._sleep,
            keyboard_module=self._keyboard,
        )

        def on_press(_event) -> None:
            if not runner.running:
                try:
                    runner.start()
                    self._set_status(
                        f"AutoFire: {binding.trigger_key.upper()} -> {binding.output_key.upper()} @{binding.interval_ms}ms"
                        f" (Pass-through {'ON' if binding.pass_through_trigger else 'OFF'})"
                    )
                except RuntimeError as exc:
                    self._emit_error(str(exc))

        def on_release(_event) -> None:
            runner.stop()
            self._set_status("")

        try:
            press_handle = self._keyboard.on_press_key(trigger, on_press, suppress=False)
            release_handle = self._keyboard.on_release_key(trigger, on_release, suppress=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to register auto-fire hotkey for %s", trigger)
            raise ValueError(f"Failed to register AutoFire trigger '{trigger}': {exc}") from exc

        if self._register_emergency and self._emergency_hotkey_id is None:
            try:
                self._emergency_hotkey_id = self._keyboard.add_hotkey(
                    "ctrl+alt+esc",
                    self.stop_all,
                    suppress=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to register emergency stop for AutoFire")
                self._emit_error(f"Unable to register AutoFire emergency stop: {exc}")

        self._handles[trigger] = _AutoFireHandle(
            binding=binding,
            runner=runner,
            press_handle=press_handle,
            release_handle=release_handle,
        )

    def stop_all(self) -> None:
        for handle in self._handles.values():
            handle.runner.stop()
        self._set_status("")

    # Internal ------------------------------------------------------------------
    def _teardown_handle(self, handle: _AutoFireHandle) -> None:
        handle.runner.stop()
        for key, hook in ("press", handle.press_handle), ("release", handle.release_handle):
            if hook is not None:
                try:
                    self._keyboard.unhook(hook)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to unhook %s handler for %s", key, handle.binding.trigger_key)
        handle.press_handle = None
        handle.release_handle = None

    def _set_status(self, message: str) -> None:
        if self._status_callback:
            try:
                self._status_callback(message)
            except Exception:  # noqa: BLE001
                logger.exception("AutoFire status callback failed")

    def _emit_error(self, message: str) -> None:
        if self._error_callback:
            try:
                self._error_callback(message)
            except Exception:  # noqa: BLE001
                logger.exception("AutoFire error callback failed")