"""Playback engine for macros with support for multiple modes."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

import keyboard
import mouse

from .types import (
    DelayStrategy,
    KeyAction,
    KeyEvent,
    Macro,
    MacroEvent,
    MouseAction,
    MouseEvent,
    PlaybackMode,
    PlaybackOptions,
)

logger = logging.getLogger(__name__)

SleepFunc = Callable[[float], None]
StateCallback = Callable[[str], None]


class MacroPlayer:
    """Plays macros on a background thread while keeping the UI responsive."""

    def __init__(
        self,
        *,
        sleep_func: Optional[SleepFunc] = None,
        keyboard_module = None,
        mouse_module = None,
        state_callback: Optional[StateCallback] = None,
    ) -> None:
        self._sleep = sleep_func or time.sleep
        self._keyboard = keyboard_module or keyboard
        self._mouse = mouse_module or mouse
        self._state_callback = state_callback
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._toggle_active = False
        self._lock = threading.RLock()
        self._trigger_hotkey: Optional[str] = None

    # Public API ---------------------------------------------------------------------
    def play(self, macro: Macro, options: PlaybackOptions, trigger_hotkey: Optional[str] = None) -> None:
        with self._lock:
            if self.is_playing() and options.mode != PlaybackMode.TOGGLE_LOOP:
                raise RuntimeError("Playback already in progress")
            if options.mode == PlaybackMode.TOGGLE_LOOP and self.is_playing():
                # Toggle request to stop current loop
                self.stop()
                return
            self._trigger_hotkey = trigger_hotkey
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_playback,
                args=(macro, options),
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # Internal playback loop ---------------------------------------------------------
    def _run_playback(self, macro: Macro, options: PlaybackOptions) -> None:
        self._notify_state("started")
        try:
            mode = options.mode
            if mode == PlaybackMode.ONCE:
                self._execute_macro(macro, options)
            elif mode == PlaybackMode.REPEAT_N:
                repetitions = max(1, options.repeat_count)
                for _ in range(repetitions):
                    if self._stop_event.is_set():
                        break
                    self._execute_macro(macro, options)
            elif mode == PlaybackMode.WHILE_HELD:
                if not self._trigger_hotkey:
                    raise ValueError("WhileHeld mode requires a trigger hotkey")
                while self._keyboard.is_pressed(self._trigger_hotkey) and not self._stop_event.is_set():
                    self._execute_macro(macro, options)
            elif mode == PlaybackMode.TOGGLE_LOOP:
                self._toggle_active = True
                while not self._stop_event.is_set():
                    self._execute_macro(macro, options)
            else:
                raise ValueError(f"Unsupported playback mode: {mode}")
            if self._stop_event.is_set():
                self._notify_state("stopped")
            else:
                self._notify_state("finished")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Playback failed: %s", exc)
            self._notify_state("error")
        finally:
            self._stop_event.clear()
            with self._lock:
                thread = self._thread
                self._thread = None
                self._toggle_active = False
            if thread:
                thread = None

    def _execute_macro(self, macro: Macro, options: PlaybackOptions) -> None:
        for index, event in enumerate(macro.events):
            if self._stop_event.is_set():
                break
            delay_ms = self._compute_delay(event, options, is_first=index == 0)
            if delay_ms > 0:
                self._sleep(delay_ms / 1000.0)
            if self._stop_event.is_set():
                break
            self._dispatch_event(event)

    def _compute_delay(self, event: MacroEvent, options: PlaybackOptions, *, is_first: bool) -> int:
        if is_first:
            return 0
        if options.delay_strategy == DelayStrategy.FIXED and options.fixed_delay_ms is not None:
            base_delay = options.fixed_delay_ms
        else:
            base_delay = getattr(event, "delay_ms", 0)
        scaled = max(0.0, float(base_delay) * max(0.1, options.speed_multiplier))
        return int(round(scaled))

    def _dispatch_event(self, event: MacroEvent) -> None:
        if isinstance(event, KeyEvent):
            if event.action == KeyAction.DOWN:
                self._keyboard.press(event.key)
            elif event.action == KeyAction.UP:
                self._keyboard.release(event.key)
        elif isinstance(event, MouseEvent):
            self._dispatch_mouse_event(event)
        else:
            raise TypeError(f"Unsupported event type: {type(event)}")

    def _dispatch_mouse_event(self, event: MouseEvent) -> None:
        if event.action == MouseAction.MOVE:
            if event.x is not None and event.y is not None:
                self._mouse.move(event.x, event.y, absolute=True, duration=0)
        elif event.action == MouseAction.DOWN:
            if event.button:
                self._mouse.press(event.button)
        elif event.action == MouseAction.UP:
            if event.button:
                self._mouse.release(event.button)
        elif event.action == MouseAction.WHEEL:
            if event.delta:
                self._mouse.wheel(event.delta)

    def _notify_state(self, state: str) -> None:
        if self._state_callback:
            try:
                self._state_callback(state)
            except Exception:  # noqa: BLE001
                logger.exception("State callback failed")