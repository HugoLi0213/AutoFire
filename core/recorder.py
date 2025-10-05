"""Global keyboard and mouse recorder with precise timing."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

import keyboard
import mouse

from .types import EventKind, KeyAction, KeyEvent, MacroEvent, MouseAction, MouseEvent, generate_id

logger = logging.getLogger(__name__)

KeyboardHook = Callable[[Callable[[keyboard.KeyboardEvent], None]], object]
MouseHook = Callable[[Callable[[mouse.MoveEvent], None]], object]
UnhookFunc = Callable[[object], None]
ClockFunc = Callable[[], int]


@dataclass(slots=True)
class RecorderConfig:
    include_keyboard: bool = True
    include_mouse: bool = True
    blocklist: Sequence[str] = ()


class MacroRecorder:
    """Records keyboard and mouse events using the `keyboard` and `mouse` libraries."""

    def __init__(
        self,
        *,
        clock: Optional[ClockFunc] = None,
        keyboard_hook: Optional[KeyboardHook] = None,
        keyboard_unhook: Optional[UnhookFunc] = None,
        mouse_hook: Optional[MouseHook] = None,
        mouse_unhook: Optional[UnhookFunc] = None,
    ) -> None:
        self._clock = clock or time.perf_counter_ns
        self._keyboard_hook = keyboard_hook or (lambda callback: keyboard.hook(callback, suppress=False))
        self._keyboard_unhook = keyboard_unhook or keyboard.unhook
        self._mouse_hook = mouse_hook or mouse.hook
        self._mouse_unhook = mouse_unhook or mouse.unhook
        self._lock = threading.RLock()
        self._keyboard_handle: Optional[object] = None
        self._mouse_handle: Optional[object] = None
        self._config = RecorderConfig()
        self._events: List[MacroEvent] = []
        self._recording = False
        self._last_timestamp_ns: Optional[int] = None

    def start(self, config: Optional[RecorderConfig] = None) -> None:
        with self._lock:
            if self._recording:
                raise RuntimeError("Recorder already running")
            self._config = config or RecorderConfig()
            if not self._config.include_keyboard and not self._config.include_mouse:
                raise ValueError("Recorder must include keyboard or mouse events")
            self._events = []
            self._recording = True
            self._last_timestamp_ns = self._clock()
            blocklist = {key.lower() for key in self._config.blocklist}
            if self._config.include_keyboard:
                self._keyboard_handle = self._keyboard_hook(
                    lambda event: self._handle_keyboard_event(event, blocklist)
                )
            if self._config.include_mouse:
                self._mouse_handle = self._mouse_hook(self._handle_mouse_event)
            logger.debug("Recorder started with config=%s", self._config)

    def stop(self) -> List[MacroEvent]:
        with self._lock:
            if not self._recording:
                raise RuntimeError("Recorder not running")
            if self._keyboard_handle is not None:
                self._keyboard_unhook(self._keyboard_handle)
                self._keyboard_handle = None
            if self._mouse_handle is not None:
                self._mouse_unhook(self._mouse_handle)
                self._mouse_handle = None
            self._recording = False
            events = list(self._events)
            self._events.clear()
            self._last_timestamp_ns = None
            logger.debug("Recorder stopped, captured %d events", len(events))
            return events

    def is_recording(self) -> bool:
        return self._recording

    # Event handlers -----------------------------------------------------------------
    def _handle_keyboard_event(self, event: keyboard.KeyboardEvent, blocklist: Iterable[str]) -> None:
        if event.event_type not in ("down", "up"):
            return
        key_name = (event.name or "").lower()
        if not key_name or key_name in blocklist:
            return
        action = KeyAction.DOWN if event.event_type == "down" else KeyAction.UP
        scan_code = getattr(event, "scan_code", None)
        self._append_event(
            KeyEvent(
                id=generate_id(),
                kind=EventKind.KEY,
                delay_ms=self._compute_delay_ms(),
                timestamp_ns=self._clock(),
                key=key_name,
                scan_code=scan_code,
                action=action,
            )
        )

    def _handle_mouse_event(self, event: mouse.MoveEvent) -> None:
        if isinstance(event, mouse.MoveEvent):
            macro_event: MacroEvent = MouseEvent(
                id=generate_id(),
                kind=EventKind.MOUSE,
                delay_ms=self._compute_delay_ms(),
                timestamp_ns=self._clock(),
                action=MouseAction.MOVE,
                button=None,
                x=int(getattr(event, "x", 0)),
                y=int(getattr(event, "y", 0)),
                delta=None,
            )
            self._append_event(macro_event)
        elif isinstance(event, mouse.ButtonEvent):
            action = MouseAction.DOWN if event.event_type == "down" else MouseAction.UP
            macro_event = MouseEvent(
                id=generate_id(),
                kind=EventKind.MOUSE,
                delay_ms=self._compute_delay_ms(),
                timestamp_ns=self._clock(),
                action=action,
                button=event.button,
                x=int(getattr(event, "x", 0)),
                y=int(getattr(event, "y", 0)),
                delta=None,
            )
            self._append_event(macro_event)
        elif isinstance(event, mouse.WheelEvent):
            macro_event = MouseEvent(
                id=generate_id(),
                kind=EventKind.MOUSE,
                delay_ms=self._compute_delay_ms(),
                timestamp_ns=self._clock(),
                action=MouseAction.WHEEL,
                button=None,
                x=int(getattr(event, "x", 0)),
                y=int(getattr(event, "y", 0)),
                delta=int(getattr(event, "delta", 0)),
            )
            self._append_event(macro_event)

    # Internal helpers ----------------------------------------------------------------
    def _compute_delay_ms(self) -> int:
        now_ns = self._clock()
        if self._last_timestamp_ns is None:
            self._last_timestamp_ns = now_ns
            return 0
        delta_ns = max(0, now_ns - self._last_timestamp_ns)
        self._last_timestamp_ns = now_ns
        return int(delta_ns / 1_000_000)

    def _append_event(self, event: MacroEvent) -> None:
        with self._lock:
            if not self._recording:
                return
            if not self._events:
                event.delay_ms = 0
            self._events.append(event)
            logger.debug("Captured event: %s", event)