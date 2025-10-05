"""Hotkey binding management using the keyboard library."""
from __future__ import annotations

import logging
from typing import Callable, Dict, Iterable, Optional

import keyboard

from .actions import ActionError, SystemActionExecutor
from .player import MacroPlayer
from .types import Binding, BindingType, Macro, PlaybackMode

logger = logging.getLogger(__name__)

MacroResolver = Callable[[str], Optional[Macro]]
ErrorCallback = Callable[[str], None]


class BindingRegistry:
    """Registers and manages global hotkeys for macros and system actions."""

    def __init__(
        self,
        player: MacroPlayer,
        system_actions: SystemActionExecutor,
        macro_resolver: MacroResolver,
        *,
        keyboard_module=None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self._player = player
        self._system_actions = system_actions
        self._macro_resolver = macro_resolver
        self._keyboard = keyboard_module or keyboard
        self._on_error = on_error
        self._handlers: Dict[str, int] = {}
        self._bindings: Dict[str, Binding] = {}

    # Management ------------------------------------------------------------------
    def clear(self) -> None:
        for hotkey, handler_id in list(self._handlers.items()):
            try:
                self._keyboard.remove_hotkey(handler_id)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to remove hotkey %s", hotkey)
        self._handlers.clear()
        self._bindings.clear()

    def apply_bindings(self, bindings: Iterable[Binding]) -> None:
        self.clear()
        for binding in bindings:
            try:
                self.register(binding)
            except ValueError as exc:
                logger.warning("Skipping binding %s: %s", binding.hotkey, exc)
                self._emit_error(str(exc))

    def register(self, binding: Binding) -> None:
        hotkey = binding.hotkey.lower().strip()
        if not hotkey:
            raise ValueError("Binding hotkey cannot be empty")
        if hotkey in self._handlers:
            raise ValueError(f"Hotkey '{hotkey}' already in use")

        def callback() -> None:
            self._invoke_binding(binding)

        handler_id = self._keyboard.add_hotkey(hotkey, callback, suppress=binding.suppress)
        self._handlers[hotkey] = handler_id
        self._bindings[hotkey] = binding
        logger.debug("Registered binding %s -> %s", hotkey, binding.binding_type)

    def unregister(self, binding: Binding) -> None:
        hotkey = binding.hotkey.lower().strip()
        handler_id = self._handlers.pop(hotkey, None)
        self._bindings.pop(hotkey, None)
        if handler_id is not None:
            try:
                self._keyboard.remove_hotkey(handler_id)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to remove hotkey %s", hotkey)

    def list_bindings(self) -> Dict[str, Binding]:
        return dict(self._bindings)

    # Invocation ------------------------------------------------------------------
    def _invoke_binding(self, binding: Binding) -> None:
        try:
            if binding.binding_type == BindingType.MACRO:
                self._invoke_macro_binding(binding)
            elif binding.binding_type == BindingType.TEXT:
                if binding.payload:
                    self._keyboard.write(binding.payload)
            elif binding.binding_type == BindingType.PROGRAM:
                if binding.payload:
                    self._system_actions.execute("launch_program", binding.payload)
            elif binding.binding_type == BindingType.SYSTEM:
                if binding.target_id:
                    self._system_actions.execute(binding.target_id, binding.payload)
            else:  # pragma: no cover - future extension
                raise ValueError(f"Unsupported binding type: {binding.binding_type}")
        except (ValueError, ActionError) as exc:
            self._emit_error(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Binding execution failed")
            self._emit_error(str(exc))

    def _invoke_macro_binding(self, binding: Binding) -> None:
        if not binding.target_id:
            raise ValueError("Macro binding missing target id")
        macro = self._macro_resolver(binding.target_id)
        if macro is None:
            raise ValueError("Macro not found")
        options = binding.playback
        trigger_hotkey = binding.hotkey if options.mode == PlaybackMode.WHILE_HELD else None
        try:
            self._player.play(macro, options, trigger_hotkey=trigger_hotkey)
        except RuntimeError as exc:
            self._emit_error(str(exc))

    def _emit_error(self, message: str) -> None:
        if self._on_error:
            try:
                self._on_error(message)
            except Exception:  # noqa: BLE001
                logger.exception("Error callback failed")