"""Minimal AutoFire Tk GUI for Windows.

Usage: ``python autofire_ui.py`` (run from an elevated command prompt if
global keyboard hooks require administrator privileges).
The UI lets you choose a trigger key, an output key, the repeat interval
(in milliseconds), and whether the trigger should pass through to other
applications while auto-fire is active. Press *Start* to register the
hooks, hold the trigger key to emit the output at the configured rate,
and use *Stop* or the emergency hotkey (Ctrl+Alt+Esc) to halt.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import keyboard
import tkinter as tk
from tkinter import messagebox, ttk

CONFIG_PATH = Path(__file__).with_name("autofire.json")
MIN_INTERVAL_MS = 1
MAX_INTERVAL_MS = 1000


@dataclass(slots=True)
class AutoFireConfig:
    trigger_key: str = "e"
    output_key: str = "r"
    interval_ms: int = 50
    pass_through: bool = False

    def formatted(self) -> str:
        status = "ON" if self.pass_through else "OFF"
        return (
            f"AutoFire: {self.trigger_key.upper()}->{self.output_key.upper()} "
            f"@ {self.interval_ms}ms (Pass-through {status})"
        )


class AutoFireEngine:
    def __init__(self, status_callback: Callable[[str, AutoFireConfig], None]) -> None:
        self._config = AutoFireConfig()
        self._status_callback = status_callback
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._running = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._press_handle: Optional[str] = None
        self._release_handle: Optional[str] = None
        self._emergency_handle: Optional[str] = None
        self._trigger_blocked = False
        self._register_emergency_hotkey()

    @property
    def config(self) -> AutoFireConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def apply_config(self, config: AutoFireConfig) -> None:
        with self._lock:
            if config == self._config:
                return
            was_running = self._running.is_set()
            if was_running:
                self.stop_loop(join=True)
            self.unbind_trigger_handlers()
            self._config = config

    def bind_trigger_handlers(self) -> None:
        with self._lock:
            self.unbind_trigger_handlers()
            try:
                suppress = not self._config.pass_through
                self._press_handle = keyboard.on_press_key(
                    self._config.trigger_key,
                    self._handle_press,
                    suppress=suppress,
                )
                self._release_handle = keyboard.on_release_key(
                    self._config.trigger_key,
                    self._handle_release,
                    suppress=suppress,
                )
            except (ValueError, RuntimeError, OSError) as exc:
                self._press_handle = None
                self._release_handle = None
                raise RuntimeError(f"Unable to register trigger '{self._config.trigger_key}': {exc}")
            self._update_status("Stopped")

    def unbind_trigger_handlers(self) -> None:
        if self._press_handle is not None:
            try:
                keyboard.unhook(self._press_handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
            self._press_handle = None
        if self._release_handle is not None:
            try:
                keyboard.unhook(self._release_handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
            self._release_handle = None

    def start_loop(self) -> None:
        with self._lock:
            if self._running.is_set():
                return
            block_ok = True
            if not self._config.pass_through and not self._trigger_blocked:
                block_ok = self._block_trigger()
            self._stop_event.clear()
            self._running.set()
            self._worker = threading.Thread(
                target=self._run_loop,
                name="AutoFireWorker",
                daemon=True,
            )
            self._worker.start()
            if block_ok:
                self._update_status("Running")
            else:
                self._status_callback(
                    "Running: Trigger not blocked - run as admin to suppress trigger",
                    self._config,
                )

    def stop_loop(self, join: bool = True) -> None:
        with self._lock:
            if not self._running.is_set():
                self._stop_event.set()
            else:
                self._stop_event.set()
        worker = self._worker
        if join and worker and worker.is_alive():
            worker.join(timeout=0.5)
        self._running.clear()
        if not self._config.pass_through:
            self._unblock_trigger()
        self._update_status("Stopped")

    def shutdown(self) -> None:
        self.stop_loop(join=True)
        self.unbind_trigger_handlers()
        if self._emergency_handle is not None:
            try:
                keyboard.remove_hotkey(self._emergency_handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
            self._emergency_handle = None
        self._unblock_trigger()

    def emergency_stop(self) -> None:
        self.stop_loop(join=True)

    def _run_loop(self) -> None:
        interval_s = max(MIN_INTERVAL_MS / 1000.0, self._config.interval_ms / 1000.0)
        next_tick = time.perf_counter()
        try:
            while not self._stop_event.is_set():
                try:
                    if not keyboard.is_pressed(self._config.trigger_key):
                        break
                except (ValueError, RuntimeError, OSError):
                    break
                now = time.perf_counter()
                if now >= next_tick:
                    try:
                        keyboard.press_and_release(self._config.output_key)
                    except (ValueError, RuntimeError, OSError):
                        break
                    next_tick += interval_s
                    if next_tick - now > interval_s * 5:
                        next_tick = now + interval_s
                sleep_for = max(0.0, min(interval_s, next_tick - now))
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            self._running.clear()
            self._stop_event.set()
            if not self._config.pass_through:
                self._unblock_trigger()
            self._update_status("Stopped")

    def _handle_press(self, _event: keyboard.KeyboardEvent) -> None:
        self.start_loop()

    def _handle_release(self, _event: keyboard.KeyboardEvent) -> None:
        self.stop_loop(join=False)

    def _block_trigger(self) -> bool:
        try:
            keyboard.block_key(self._config.trigger_key)
        except (ValueError, RuntimeError, OSError):
            self._status_callback(
                "Warning: Could not block trigger key - run AutoFire as administrator",
                self._config,
            )
            return False
        self._trigger_blocked = True
        return True

    def _unblock_trigger(self) -> None:
        if not self._trigger_blocked:
            return
        try:
            keyboard.unblock_key(self._config.trigger_key)
        except (ValueError, RuntimeError, OSError):
            pass
        self._trigger_blocked = False

    def _register_emergency_hotkey(self) -> None:
        try:
            self._emergency_handle = keyboard.add_hotkey(
                "ctrl+alt+esc",
                self.emergency_stop,
                suppress=False,
            )
        except (ValueError, RuntimeError, OSError) as exc:
            raise SystemExit(f"Unable to register emergency stop hotkey: {exc}") from exc

    def _update_status(self, state: str) -> None:
        self._status_callback(state, self._config)


def _normalize_key(name: str) -> str:
    key = (name or "").strip().lower()
    if not key:
        raise ValueError("Key name cannot be empty")
    try:
        keyboard.key_to_scan_codes(key)
    except ValueError as exc:
        raise ValueError(f"Unknown key '{name}'") from exc
    return key


def load_config() -> AutoFireConfig:
    if not CONFIG_PATH.exists():
        return AutoFireConfig()
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in '{CONFIG_PATH.name}': {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read '{CONFIG_PATH}': {exc}") from exc
    trigger = raw.get("triggerKey", AutoFireConfig.trigger_key)
    output = raw.get("outputKey", AutoFireConfig.output_key)
    interval = raw.get("intervalMs", AutoFireConfig.interval_ms)
    pass_through = raw.get("passThrough", AutoFireConfig.pass_through)
    return AutoFireConfig(
        trigger_key=_normalize_key(trigger),
        output_key=_normalize_key(output),
        interval_ms=int(max(MIN_INTERVAL_MS, min(int(interval), MAX_INTERVAL_MS))),
        pass_through=bool(pass_through),
    )


def save_config(config: AutoFireConfig) -> None:
    payload = {
        "triggerKey": config.trigger_key,
        "outputKey": config.output_key,
        "intervalMs": config.interval_ms,
        "passThrough": config.pass_through,
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class AutoFireUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AutoFire")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if sys.platform != "win32":
            raise SystemExit("This script is supported on Windows only.")

        self.engine = AutoFireEngine(self._schedule_status_update)
        self._capture_handle: Optional[Callable[[keyboard.KeyboardEvent], None]] = None
        self._pending_status = "Stopped"
        self._current_config = self.engine.config

        self.trigger_var = tk.StringVar(value=self._current_config.trigger_key)
        self.output_var = tk.StringVar(value=self._current_config.output_key)
        self.interval_var = tk.IntVar(value=self._current_config.interval_ms)
        self.pass_var = tk.BooleanVar(value=self._current_config.pass_through)

        self.status_var = tk.StringVar(value=self._format_status("Stopped", self._current_config))

        self._build_layout()
        self._set_button_states(running=False)
        self.populate_from_config(load_config())

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        trigger_row = ttk.Frame(container)
        trigger_row.pack(fill=tk.X, pady=4)
        ttk.Label(trigger_row, text="Trigger key").pack(side=tk.LEFT)
        trigger_entry = ttk.Entry(trigger_row, textvariable=self.trigger_var, width=12)
        trigger_entry.pack(side=tk.LEFT, padx=6)
        self.trigger_entry = trigger_entry
        trigger_capture = ttk.Button(
            trigger_row,
            text="Capture",
            command=lambda: capture_next_key(trigger_entry),
        )
        trigger_capture.pack(side=tk.LEFT)
        self.trigger_capture_button = trigger_capture

        output_row = ttk.Frame(container)
        output_row.pack(fill=tk.X, pady=4)
        ttk.Label(output_row, text="Output key").pack(side=tk.LEFT)
        output_entry = ttk.Entry(output_row, textvariable=self.output_var, width=12)
        output_entry.pack(side=tk.LEFT, padx=6)
        self.output_entry = output_entry
        output_capture = ttk.Button(
            output_row,
            text="Capture",
            command=lambda: capture_next_key(output_entry),
        )
        output_capture.pack(side=tk.LEFT)
        self.output_capture_button = output_capture

        interval_row = ttk.Frame(container)
        interval_row.pack(fill=tk.X, pady=4)
        ttk.Label(interval_row, text="Interval (ms)").pack(side=tk.LEFT)
        interval_spin = ttk.Spinbox(
            interval_row,
            from_=MIN_INTERVAL_MS,
            to=MAX_INTERVAL_MS,
            textvariable=self.interval_var,
            width=10,
            increment=1,
        )
        interval_spin.pack(side=tk.LEFT, padx=6)
        self.interval_spin = interval_spin

        pass_row = ttk.Frame(container)
        pass_row.pack(fill=tk.X, pady=4)
        pass_check = ttk.Checkbutton(pass_row, text="Pass-through", variable=self.pass_var)
        pass_check.pack(side=tk.LEFT)
        self.pass_check = pass_check

        button_row = ttk.Frame(container)
        button_row.pack(fill=tk.X, pady=10)
        start_btn = ttk.Button(button_row, text="Start", command=start_autofire)
        start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.start_button = start_btn
        stop_btn = ttk.Button(button_row, text="Stop", command=stop_autofire)
        stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.stop_button = stop_btn

        ttk.Label(container, textvariable=self.status_var, relief=tk.SUNKEN, padding=6).pack(fill=tk.X, pady=(8, 0))

    def populate_from_config(self, config: AutoFireConfig) -> None:
        self.trigger_var.set(config.trigger_key)
        self.output_var.set(config.output_key)
        self.interval_var.set(config.interval_ms)
        self.pass_var.set(config.pass_through)
        self._current_config = config
        self.engine.apply_config(config)
        self.status_var.set(self._format_status("Stopped", config))
        self._set_button_states(running=False)

    def start(self) -> None:
        self.root.mainloop()

    def on_close(self) -> None:
        stop_autofire()
        self.engine.shutdown()
        self._cancel_capture()
        self.root.destroy()

    def start_autofire(self) -> None:
        config = self._build_config_from_inputs()
        if config is None:
            return
        save_config(config)
        self.engine.apply_config(config)
        try:
            self.engine.bind_trigger_handlers()
        except RuntimeError as exc:
            messagebox.showerror("AutoFire", str(exc), parent=self.root)
            return
        self._current_config = config
        self.status_var.set(self._format_status("Stopped", config))

    def stop_autofire(self) -> None:
        self.engine.stop_loop(join=True)
        self.engine.unbind_trigger_handlers()
        self.status_var.set(self._format_status("Stopped", self.engine.config))
        self._set_button_states(running=False)

    def capture_next_key(self, entry: ttk.Entry) -> None:
        self._cancel_capture()

        def handler(event: keyboard.KeyboardEvent) -> None:
            if event.event_type != "down":
                return
            self._cancel_capture()
            entry.delete(0, tk.END)
            entry.insert(0, event.name)

        self._capture_handle = handler
        keyboard.hook(handler)

    def _cancel_capture(self) -> None:
        if self._capture_handle is None:
            return
        try:
            keyboard.unhook(self._capture_handle)
        except (KeyError, ValueError, RuntimeError, OSError):
            pass
        self._capture_handle = None

    def _build_config_from_inputs(self) -> Optional[AutoFireConfig]:
        try:
            trigger = _normalize_key(self.trigger_var.get())
            output = _normalize_key(self.output_var.get())
        except ValueError as exc:
            messagebox.showerror("AutoFire", str(exc), parent=self.root)
            return None
        try:
            interval = int(self.interval_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("AutoFire", "Interval must be an integer", parent=self.root)
            return None
        interval = max(MIN_INTERVAL_MS, min(interval, MAX_INTERVAL_MS))
        pass_through = bool(self.pass_var.get())
        return AutoFireConfig(trigger_key=trigger, output_key=output, interval_ms=interval, pass_through=pass_through)

    def _schedule_status_update(self, state: str, config: AutoFireConfig) -> None:
        self._pending_status = state
        self._current_config = config
        self.root.after(0, self._flush_status_update)

    def _flush_status_update(self) -> None:
        running = self.engine.is_running
        self._set_button_states(running)
        self.status_var.set(self._format_status(self._pending_status, self._current_config))

    def _set_button_states(self, running: bool) -> None:
        if running:
            self.start_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.NORMAL)
        else:
            self.start_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.DISABLED)

    @staticmethod
    def _format_status(state: str, config: AutoFireConfig) -> str:
        if state == "Running":
            suffix = "Running"
        elif state == "Stopped":
            suffix = "Stopped"
        else:
            suffix = state
        return f"{config.formatted()} [{suffix}]"


APP: Optional[AutoFireUI] = None


def start_autofire() -> None:
    if APP is None:
        raise RuntimeError("UI has not been initialized")
    APP.start_autofire()


def stop_autofire() -> None:
    if APP is None:
        raise RuntimeError("UI has not been initialized")
    APP.stop_autofire()


def bind_trigger_handlers() -> None:
    if APP is None:
        raise RuntimeError("UI has not been initialized")
    APP.engine.bind_trigger_handlers()


def unbind_trigger_handlers() -> None:
    if APP is None:
        raise RuntimeError("UI has not been initialized")
    APP.engine.unbind_trigger_handlers()


def capture_next_key(field: ttk.Entry) -> None:
    if APP is None:
        raise RuntimeError("UI has not been initialized")
    APP.capture_next_key(field)


def main() -> None:
    global APP
    root = tk.Tk()
    APP = AutoFireUI(root)
    APP.start()


if __name__ == "__main__":
    main()
