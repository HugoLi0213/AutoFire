"""Keyboard-only AutoFire runner for Windows.

Inline README:
- Usage: `python autofire.py [--ui]` (requires administrator rights so the
  `keyboard` hooks can listen globally). Default mode is headless; add `--ui`
  for a tiny Tk window to edit the config on the fly. Press Ctrl+C in the
  console to exit.
- Configuration: `autofire.json` controls the trigger key, output key,
  interval, and pass-through behaviour. Changes are hot-reloaded every 500 ms.
  Invalid edits are rejected with a clear error and the previous binding stays
  active.
- Known limitations: like most global keyboard hooks, function-key rows that
  double as hardware/Fn shortcuts may not be capturable on every laptop, and
  the script intentionally avoids any mouse APIs.
"""
from __future__ import annotations

import argparse
import atexit
import json
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import keyboard

CONFIG_FILE = Path(__file__).with_name("autofire.json")
CONFIG_POLL_SECONDS = 0.5
MIN_INTERVAL_MS = 1
MAX_INTERVAL_MS = 1000


@dataclass(slots=True)
class AutoFireConfig:
    """Validated configuration for a single while-held AutoFire binding."""

    trigger_key: str = "e"
    output_key: str = "r"
    interval_ms: int = 50
    pass_through: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "triggerKey": self.trigger_key,
            "outputKey": self.output_key,
            "intervalMs": self.interval_ms,
            "passThrough": self.pass_through,
        }

    def active_line(self) -> str:
        status = "ON" if self.pass_through else "OFF"
        return (
            f"Active: {self.trigger_key}->{self.output_key} @{self.interval_ms}ms "
            f"(Pass-through {status})"
        )


def _normalize_key(name: str) -> str:
    key = str(name or "").strip().lower()
    if not key:
        raise ValueError("Key name cannot be empty")
    try:
        keyboard.key_to_scan_codes(key)
    except ValueError as exc:
        raise ValueError(f"Unknown key '{name}'") from exc
    return key


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def validate_config(mapping: Mapping[str, Any]) -> AutoFireConfig:
    """Validate a config mapping and return an AutoFireConfig instance."""

    trigger = _normalize_key(mapping.get("triggerKey", AutoFireConfig.trigger_key))
    output = _normalize_key(mapping.get("outputKey", AutoFireConfig.output_key))
    try:
        interval = int(mapping.get("intervalMs", AutoFireConfig.interval_ms))
    except (TypeError, ValueError) as exc:
        raise ValueError("intervalMs must be an integer") from exc
    if not (MIN_INTERVAL_MS <= interval <= MAX_INTERVAL_MS):
        raise ValueError(
            f"intervalMs must be between {MIN_INTERVAL_MS} and {MAX_INTERVAL_MS} inclusive"
        )
    pass_through = _coerce_bool(mapping.get("passThrough", AutoFireConfig.pass_through))
    return AutoFireConfig(
        trigger_key=trigger,
        output_key=output,
        interval_ms=interval,
        pass_through=pass_through,
    )


def load_config(path: Path) -> AutoFireConfig:
    """Load and validate configuration, returning defaults when file is missing."""

    if not path.exists():
        return AutoFireConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in '{path.name}': {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read '{path}': {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("Config root must be an object mapping")
    return validate_config(raw)


def write_config(path: Path, config: AutoFireConfig) -> None:
    payload = json.dumps(config.as_dict(), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")


class AutoFireApp:
    """Core AutoFire controller responsible for hooks, worker loop, and hot reload."""

    def __init__(
        self,
        config: AutoFireConfig,
        *,
        keyboard_module=None,
        now: Optional[Callable[[], float]] = None,
        sleep: Optional[Callable[[float], None]] = None,
        config_path: Path = CONFIG_FILE,
        poll_seconds: float = CONFIG_POLL_SECONDS,
    ) -> None:
        self.config = config
        self._keyboard = keyboard_module or keyboard
        self._now = now or time.perf_counter
        self._sleep = sleep or time.sleep
        self._watch_sleep = time.sleep
        self._config_path = config_path
        self._poll_seconds = max(0.1, poll_seconds)

        self._running = threading.Event()
        self._stop_signal = threading.Event()
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._press_handle: Any | None = None
        self._release_handle: Any | None = None
        self._emergency_handle: Any | None = None
        self._trigger_blocked = False

        self._watch_stop = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self._last_config_mtime: Optional[float] = None
        if config_path.exists():
            try:
                self._last_config_mtime = config_path.stat().st_mtime
            except OSError:
                self._last_config_mtime = None

    def start(self, *, start_watcher: bool = True) -> None:
        self._register_hooks()
        self._ensure_emergency_hotkey()
        if start_watcher:
            self._start_watcher()
        print("Stopped")

    def start_loop(self) -> None:
        with self._lock:
            if self._running.is_set():
                return
            if not self.config.pass_through and not self._trigger_blocked:
                try:
                    self._keyboard.block_key(self.config.trigger_key)
                    self._trigger_blocked = True
                except (ValueError, RuntimeError, OSError) as exc:
                    print(f"Validation error: unable to block '{self.config.trigger_key}': {exc}")
            self._stop_signal.clear()
            self._running.set()
            self._worker = threading.Thread(
                target=self._loop,
                name="AutoFireWorker",
                daemon=True,
            )
            self._worker.start()
        print(self.config.active_line())

    def stop_loop(self, join: bool = True) -> None:
        self._stop_signal.set()
        worker: Optional[threading.Thread]
        with self._lock:
            worker = self._worker
        if join and worker and worker.is_alive():
            worker.join(timeout=0.5)

    def apply_binding(self, config: AutoFireConfig) -> None:
        if config == self.config:
            return
        previous = self.config
        self.stop_loop(join=True)
        try:
            self.config = config
            self._register_hooks()
        except Exception as exc:
            self.config = previous
            self._register_hooks()
            raise RuntimeError(f"Failed to bind '{config.trigger_key}': {exc}") from exc

    def reload_config(self) -> bool:
        try:
            new_config = load_config(self._config_path)
        except ValueError as exc:
            print(f"Validation error: {exc}")
            return False
        if new_config == self.config:
            return False
        try:
            self.apply_binding(new_config)
        except RuntimeError as exc:
            print(f"Validation error: {exc}")
            return False
        print("Config reloaded")
        return True

    def watch_config(self) -> None:
        self._watch_config_loop()

    def shutdown(self) -> None:
        self.stop_loop(join=True)
        self._stop_watcher()
        self._unregister_hooks()
        if self._emergency_handle is not None:
            try:
                self._keyboard.remove_hotkey(self._emergency_handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
            self._emergency_handle = None
        self._unblock_trigger()

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def _register_hooks(self) -> None:
        self._unregister_hooks()
        try:
            self._press_handle = self._keyboard.on_press_key(
                self.config.trigger_key,
                self._handle_press,
                suppress=False,
            )
            self._release_handle = self._keyboard.on_release_key(
                self.config.trigger_key,
                self._handle_release,
                suppress=False,
            )
        except (ValueError, RuntimeError, OSError) as exc:
            raise RuntimeError(f"Unable to register key '{self.config.trigger_key}': {exc}") from exc

    def _unregister_hooks(self) -> None:
        if self._press_handle is not None:
            try:
                self._keyboard.unhook(self._press_handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
            self._press_handle = None
        if self._release_handle is not None:
            try:
                self._keyboard.unhook(self._release_handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
            self._release_handle = None

    def _ensure_emergency_hotkey(self) -> None:
        if self._emergency_handle is None:
            try:
                self._emergency_handle = self._keyboard.add_hotkey(
                    "ctrl+alt+esc",
                    self.emergency_stop,
                    suppress=False,
                )
            except (ValueError, RuntimeError, OSError) as exc:
                raise SystemExit(f"[ERROR] Unable to register emergency stop: {exc}") from exc

    def _handle_press(self, event: Any) -> None:  # noqa: ANN001
        if not self.is_running:
            self.start_loop()

    def _handle_release(self, event: Any) -> None:  # noqa: ANN001
        self.stop_loop(join=True)

    def emergency_stop(self) -> None:
        if self.is_running:
            print("Validation error: emergency stop activated")
        self.stop_loop(join=True)
        try:
            self._keyboard.release(self.config.trigger_key)
        except (ValueError, RuntimeError, OSError):
            pass

    def _loop(self) -> None:
        interval_s = max(MIN_INTERVAL_MS / 1000.0, self.config.interval_ms / 1000.0)
        next_tick = self._now()
        try:
            while not self._stop_signal.is_set():
                try:
                    if not self._keyboard.is_pressed(self.config.trigger_key):
                        break
                except Exception:
                    break
                now_value = self._now()
                if now_value >= next_tick:
                    try:
                        self._keyboard.press_and_release(self.config.output_key)
                    except (ValueError, RuntimeError, OSError) as exc:
                        print(f"Validation error: unable to emit '{self.config.output_key}': {exc}")
                        break
                    next_tick += interval_s
                    if next_tick - now_value > 5 * interval_s:
                        next_tick = now_value + interval_s
                sleep_for = max(0.0, min(interval_s, next_tick - now_value))
                if sleep_for > 0:
                    self._sleep(sleep_for)
        finally:
            self._stop_signal.set()
            self._running.clear()
            self._unblock_trigger()
            with self._lock:
                self._worker = None
            print("Stopped")

    def _unblock_trigger(self) -> None:
        if self._trigger_blocked:
            try:
                self._keyboard.unblock_key(self.config.trigger_key)
            except (ValueError, RuntimeError, OSError):
                pass
            self._trigger_blocked = False

    def _start_watcher(self) -> None:
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._watch_stop.clear()
        self._watch_thread = threading.Thread(
            target=self._watch_config_loop,
            name="AutoFireConfigWatcher",
            daemon=True,
        )
        self._watch_thread.start()

    def _stop_watcher(self) -> None:
        self._watch_stop.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=0.5)
        self._watch_thread = None

    def _watch_config_loop(self) -> None:
        while not self._watch_stop.is_set():
            if self._watch_stop.wait(self._poll_seconds):
                break
            try:
                mtime = self._config_path.stat().st_mtime
            except OSError:
                mtime = None
            if mtime != self._last_config_mtime:
                self._last_config_mtime = mtime
                self.reload_config()

def run_ui(app: AutoFireApp, config_path: Path) -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("AutoFire")
    root.resizable(False, False)

    trigger_var = tk.StringVar(value=app.config.trigger_key.upper())
    output_var = tk.StringVar(value=app.config.output_key.upper())
    interval_var = tk.IntVar(value=app.config.interval_ms)
    pass_through_var = tk.BooleanVar(value=app.config.pass_through)
    status_var = tk.StringVar(value="Hold trigger to test. Apply to save.")

    def capture_into(target: tk.StringVar, button: tk.Button) -> None:
        status_var.set("Press a key to capture...")
        button.configure(state=tk.DISABLED)

        def worker() -> None:
            try:
                key = keyboard.read_key(suppress=False)
            except Exception as exc:
                root.after(0, lambda: status_var.set(f"Capture failed: {exc}"))
            else:
                display = key.upper()
                root.after(0, lambda: target.set(display))
                root.after(0, lambda: status_var.set(f"Captured {display}"))
            finally:
                root.after(0, lambda: button.configure(state=tk.NORMAL))

        threading.Thread(target=worker, name="CaptureKey", daemon=True).start()

    def sync_from_config(config: AutoFireConfig) -> None:
        trigger_var.set(config.trigger_key.upper())
        output_var.set(config.output_key.upper())
        interval_var.set(config.interval_ms)
        pass_through_var.set(config.pass_through)

    def on_apply() -> None:
        data = {
            "triggerKey": trigger_var.get().strip(),
            "outputKey": output_var.get().strip(),
            "intervalMs": interval_var.get(),
            "passThrough": pass_through_var.get(),
        }
        try:
            new_config = validate_config(data)
        except ValueError as exc:
            status_var.set(f"Validation error: {exc}")
            messagebox.showerror("AutoFire", str(exc))
            return
        try:
            write_config(config_path, new_config)
        except OSError as exc:
            status_var.set(f"Validation error: unable to save ({exc})")
            messagebox.showerror("AutoFire", f"Unable to save config: {exc}")
            return
        try:
            app.apply_binding(new_config)
        except RuntimeError as exc:
            status_var.set(f"Validation error: {exc}")
            messagebox.showerror("AutoFire", str(exc))
            return
        status_var.set("Config reloaded")

    frame = ttk.Frame(root, padding=10)
    frame.grid(column=0, row=0, sticky="nsew")

    ttk.Label(frame, text="Trigger").grid(column=0, row=0, sticky="w")
    trigger_entry = ttk.Entry(frame, textvariable=trigger_var, width=8)
    trigger_entry.grid(column=1, row=0, padx=4)
    trigger_button = ttk.Button(
        frame,
        text="Capture",
        command=lambda: capture_into(trigger_var, trigger_button),
    )
    trigger_button.grid(column=2, row=0)

    ttk.Label(frame, text="Output").grid(column=0, row=1, sticky="w")
    output_entry = ttk.Entry(frame, textvariable=output_var, width=8)
    output_entry.grid(column=1, row=1, padx=4)
    output_button = ttk.Button(
        frame,
        text="Capture",
        command=lambda: capture_into(output_var, output_button),
    )
    output_button.grid(column=2, row=1)

    ttk.Label(frame, text="Interval (ms)").grid(column=0, row=2, sticky="w")
    interval_spin = ttk.Spinbox(
        frame,
        from_=MIN_INTERVAL_MS,
        to=MAX_INTERVAL_MS,
        textvariable=interval_var,
        width=8,
    )
    interval_spin.grid(column=1, row=2, padx=4, sticky="ew")

    pass_check = ttk.Checkbutton(frame, text="Pass-through", variable=pass_through_var)
    pass_check.grid(column=0, row=3, columnspan=3, sticky="w")

    ttk.Button(frame, text="Apply & Save", command=on_apply).grid(
        column=0, row=4, columnspan=3, pady=(8, 0), sticky="ew"
    )

    status_label = ttk.Label(frame, textvariable=status_var)
    status_label.grid(column=0, row=5, columnspan=3, sticky="w", pady=(6, 0))

    for child in frame.winfo_children():
        child.grid_configure(padx=2, pady=2)

    def poll_config() -> None:
        sync_from_config(app.config)
        root.after(1000, poll_config)

    poll_config()
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


def apply_binding(app: AutoFireApp, config: AutoFireConfig) -> None:
    app.apply_binding(config)


def start_loop(app: AutoFireApp) -> None:
    app.start_loop()


def stop_loop(app: AutoFireApp) -> None:
    app.stop_loop(join=True)


def watch_config(app: AutoFireApp) -> None:
    app.watch_config()


def run_headless(app: AutoFireApp) -> None:
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        app.shutdown()


def run_ui_mode(app: AutoFireApp) -> None:
    try:
        run_ui(app, CONFIG_FILE)
    finally:
        app.shutdown()


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Keyboard-only AutoFire controller")
    parser.add_argument("--ui", action="store_true", help="Launch minimal Tk UI for config edits")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without UI (default behaviour)",
    )
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        raise SystemExit("[ERROR] AutoFire supports Windows only (keyboard library limitation).")

    try:
        config = load_config(CONFIG_FILE)
    except ValueError as exc:
        print(f"Validation error: {exc}")
        config = AutoFireConfig()

    app = AutoFireApp(config, config_path=CONFIG_FILE)
    atexit.register(app.shutdown)

    try:
        app.start(start_watcher=True)
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"[ERROR] Startup failed: {exc}") from exc

    print("Press Ctrl+C to exit. AutoFire is armed.")

    if args.ui and not args.headless:
        run_ui_mode(app)
    else:
        run_headless(app)


if __name__ == "__main__":
    main()
