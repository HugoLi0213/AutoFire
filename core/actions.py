"""System-level actions triggered by bindings."""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import keyboard

logger = logging.getLogger(__name__)

try:
    import ctypes
    from ctypes import wintypes
except ImportError:  # pragma: no cover
    ctypes = None  # type: ignore
    wintypes = None  # type: ignore


class ActionError(RuntimeError):
    """Raised when a system action fails."""


@dataclass(slots=True)
class SystemAction:
    name: str
    handler: Callable[[Optional[str]], None]


class SystemActionExecutor:
    """Executes predefined system actions with graceful fallbacks."""

    def __init__(self) -> None:
        self._actions: Dict[str, SystemAction] = {
            "volume_up": SystemAction("Volume Up", lambda _: keyboard.send("volume up")),
            "volume_down": SystemAction("Volume Down", lambda _: keyboard.send("volume down")),
            "volume_mute": SystemAction("Volume Mute", lambda _: keyboard.send("volume mute")),
            "minimize_window": SystemAction("Minimize Window", lambda _: self._show_window(6)),
            "restore_window": SystemAction("Restore Window", lambda _: self._show_window(9)),
            "type_text": SystemAction("Type Text", lambda text: keyboard.write(text or "")),
            "launch_program": SystemAction("Launch Program", self._launch_program),
        }

    def execute(self, action_id: str, payload: Optional[str] = None) -> None:
        action = self._actions.get(action_id)
        if not action:
            raise ActionError(f"Unknown system action '{action_id}'")
        try:
            action.handler(payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("System action '%s' failed", action_id)
            raise ActionError(str(exc)) from exc

    # Internal helpers -------------------------------------------------------------
    def _launch_program(self, payload: Optional[str]) -> None:
        if not payload:
            raise ActionError("Program path is required")
        path = os.path.expandvars(payload)
        try:
            subprocess.Popen(path, shell=True)
        except FileNotFoundError as exc:  # pragma: no cover - depends on user input
            raise ActionError(f"Program not found: {path}") from exc

    def _show_window(self, command: int) -> None:
        if ctypes is None:  # pragma: no cover
            raise ActionError("Window APIs unavailable on this platform")
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if hwnd == 0:
            raise ActionError("No active window")
        if not user32.ShowWindow(hwnd, command):
            raise ActionError("Window command failed")