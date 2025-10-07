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
class AutoFireSlot:
    """Validated configuration for a single while-held AutoFire binding."""

    trigger_key: str = "e"
    output_key: str = "r"
    interval_ms: int = 50
    pass_through: bool = False
    enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "triggerKey": self.trigger_key,
            "outputKey": self.output_key,
            "intervalMs": self.interval_ms,
            "passThrough": self.pass_through,
            "enabled": self.enabled,
        }

    def active_line(self) -> str:
        status = "ON" if self.pass_through else "OFF"
        enabled_status = "ENABLED" if self.enabled else "DISABLED"
        return (
            f"[{enabled_status}] {self.trigger_key}->{self.output_key} @{self.interval_ms}ms "
            f"(Pass-through {status})"
        )


@dataclass(slots=True)
class AutoFireConfig:
    """Configuration containing multiple AutoFire slots."""

    slots: list[AutoFireSlot] | None = None

    def __post_init__(self):
        if self.slots is None:
            self.slots = [AutoFireSlot()]

    def as_dict(self) -> dict[str, Any]:
        return {
            "slots": [slot.as_dict() for slot in self.slots]
        }

    def active_line(self) -> str:
        enabled_count = sum(1 for slot in self.slots if slot.enabled)
        return f"Active slots: {enabled_count}/{len(self.slots)}"


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


def validate_slot(mapping: Mapping[str, Any]) -> AutoFireSlot:
    """Validate a slot mapping and return an AutoFireSlot instance."""

    trigger = _normalize_key(mapping.get("triggerKey", "e"))
    output = _normalize_key(mapping.get("outputKey", "r"))
    try:
        interval = int(mapping.get("intervalMs", 50))
    except (TypeError, ValueError) as exc:
        raise ValueError("intervalMs must be an integer") from exc
    if not (MIN_INTERVAL_MS <= interval <= MAX_INTERVAL_MS):
        raise ValueError(
            f"intervalMs must be between {MIN_INTERVAL_MS} and {MAX_INTERVAL_MS} inclusive"
        )
    pass_through = _coerce_bool(mapping.get("passThrough", False))
    enabled = _coerce_bool(mapping.get("enabled", True))
    return AutoFireSlot(
        trigger_key=trigger,
        output_key=output,
        interval_ms=interval,
        pass_through=pass_through,
        enabled=enabled,
    )


def validate_config(mapping: Mapping[str, Any]) -> AutoFireConfig:
    """Validate a config mapping and return an AutoFireConfig instance."""

    # Support legacy format (single slot)
    if "triggerKey" in mapping and "slots" not in mapping:
        slot = validate_slot(mapping)
        return AutoFireConfig(slots=[slot])

    # New format with multiple slots
    slots_data = mapping.get("slots", [])
    if not isinstance(slots_data, list):
        raise ValueError("'slots' must be a list")
    
    if not slots_data:
        return AutoFireConfig(slots=[AutoFireSlot()])
    
    slots = []
    for idx, slot_data in enumerate(slots_data):
        if not isinstance(slot_data, Mapping):
            raise ValueError(f"Slot {idx} must be an object")
        try:
            slots.append(validate_slot(slot_data))
        except ValueError as exc:
            raise ValueError(f"Slot {idx}: {exc}") from exc
    
    return AutoFireConfig(slots=slots)


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

        # Dictionary to track running slots: {trigger_key: (slot, worker_thread, stop_event, running_event, blocked)}
        self._slot_workers: dict[str, tuple[AutoFireSlot, threading.Thread, threading.Event, threading.Event, bool]] = {}
        self._lock = threading.RLock()
        self._press_handles: dict[str, Any] = {}
        self._release_handles: dict[str, Any] = {}
        self._emergency_handle: Any | None = None

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
        print(f"AutoFire started with {len(self.config.slots)} slot(s)")
        for idx, slot in enumerate(self.config.slots):
            status = "enabled" if slot.enabled else "disabled"
            print(f"  Slot {idx + 1}: {slot.active_line()}")

    def start_loop(self, trigger_key: str) -> None:
        """Start the worker loop for a specific trigger key."""
        with self._lock:
            if trigger_key in self._slot_workers:
                _, _, _, running, _ = self._slot_workers[trigger_key]
                if running.is_set():
                    return
            
            # Find the enabled slot for this trigger key
            slot = None
            for s in self.config.slots:
                if s.enabled and s.trigger_key == trigger_key:
                    slot = s
                    break
            
            if slot is None:
                return
            
            # Block the trigger key if pass-through is disabled
            trigger_blocked = False
            if not slot.pass_through:
                try:
                    self._keyboard.block_key(trigger_key)
                    trigger_blocked = True
                except (ValueError, RuntimeError, OSError) as exc:
                    print(f"Validation error: unable to block '{trigger_key}': {exc}")
            
            stop_signal = threading.Event()
            running = threading.Event()
            running.set()
            
            worker = threading.Thread(
                target=self._loop,
                args=(slot, stop_signal, running),
                name=f"AutoFireWorker-{trigger_key}",
                daemon=True,
            )
            
            self._slot_workers[trigger_key] = (slot, worker, stop_signal, running, trigger_blocked)
            worker.start()
        print(f"Started: {slot.active_line()}")

    def stop_loop(self, trigger_key: str, join: bool = True) -> None:
        """Stop the worker loop for a specific trigger key."""
        with self._lock:
            if trigger_key not in self._slot_workers:
                return
            
            slot, worker, stop_signal, running, trigger_blocked = self._slot_workers[trigger_key]
            stop_signal.set()
        
        if join and worker and worker.is_alive():
            worker.join(timeout=0.5)
        
        # Unblock the trigger key
        if trigger_blocked:
            try:
                self._keyboard.unblock_key(trigger_key)
            except (ValueError, RuntimeError, OSError):
                pass
        
        with self._lock:
            if trigger_key in self._slot_workers:
                del self._slot_workers[trigger_key]
        
        print(f"Stopped: {trigger_key}")

    def apply_binding(self, config: AutoFireConfig) -> None:
        if config == self.config:
            return
        previous = self.config
        # Stop all running workers
        for trigger_key in list(self._slot_workers.keys()):
            self.stop_loop(trigger_key, join=True)
        try:
            self.config = config
            self._register_hooks()
        except Exception as exc:
            self.config = previous
            self._register_hooks()
            raise RuntimeError(f"Failed to apply new configuration: {exc}") from exc

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
        # Stop all running workers
        for trigger_key in list(self._slot_workers.keys()):
            self.stop_loop(trigger_key, join=True)
        self._stop_watcher()
        self._unregister_hooks()
        if self._emergency_handle is not None:
            try:
                self._keyboard.remove_hotkey(self._emergency_handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
            self._emergency_handle = None

    @property
    def is_running(self) -> bool:
        return len(self._slot_workers) > 0

    def _register_hooks(self) -> None:
        self._unregister_hooks()
        for slot in self.config.slots:
            if not slot.enabled:
                continue
            try:
                press_handle = self._keyboard.on_press_key(
                    slot.trigger_key,
                    lambda e, key=slot.trigger_key: self._handle_press(e, key),
                    suppress=False,
                )
                release_handle = self._keyboard.on_release_key(
                    slot.trigger_key,
                    lambda e, key=slot.trigger_key: self._handle_release(e, key),
                    suppress=False,
                )
                self._press_handles[slot.trigger_key] = press_handle
                self._release_handles[slot.trigger_key] = release_handle
            except (ValueError, RuntimeError, OSError) as exc:
                print(f"Warning: unable to register key '{slot.trigger_key}': {exc}")

    def _unregister_hooks(self) -> None:
        for handle in self._press_handles.values():
            try:
                self._keyboard.unhook(handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
        self._press_handles.clear()
        
        for handle in self._release_handles.values():
            try:
                self._keyboard.unhook(handle)
            except (KeyError, ValueError, RuntimeError, OSError):
                pass
        self._release_handles.clear()

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

    def _handle_press(self, event: Any, trigger_key: str) -> None:  # noqa: ANN001
        with self._lock:
            if trigger_key not in self._slot_workers or not self._slot_workers[trigger_key][3].is_set():
                self.start_loop(trigger_key)

    def _handle_release(self, event: Any, trigger_key: str) -> None:  # noqa: ANN001
        self.stop_loop(trigger_key, join=True)

    def emergency_stop(self) -> None:
        if self.is_running:
            print("Validation error: emergency stop activated")
        for trigger_key in list(self._slot_workers.keys()):
            self.stop_loop(trigger_key, join=True)
            try:
                self._keyboard.release(trigger_key)
            except (ValueError, RuntimeError, OSError):
                pass

    def _loop(self, slot: AutoFireSlot, stop_signal: threading.Event, running: threading.Event) -> None:
        interval_s = max(MIN_INTERVAL_MS / 1000.0, slot.interval_ms / 1000.0)
        next_tick = self._now()
        try:
            while not stop_signal.is_set():
                try:
                    if not self._keyboard.is_pressed(slot.trigger_key):
                        break
                except Exception:
                    break
                now_value = self._now()
                if now_value >= next_tick:
                    try:
                        self._keyboard.press_and_release(slot.output_key)
                    except (ValueError, RuntimeError, OSError) as exc:
                        print(f"Validation error: unable to emit '{slot.output_key}': {exc}")
                        break
                    next_tick += interval_s
                    if next_tick - now_value > 5 * interval_s:
                        next_tick = now_value + interval_s
                sleep_for = max(0.0, min(interval_s, next_tick - now_value))
                if sleep_for > 0:
                    self._sleep(sleep_for)
        finally:
            stop_signal.set()
            running.clear()

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
    from tkinter import messagebox, ttk, scrolledtext

    root = tk.Tk()
    root.title("AutoFire - Multi-Slot Configuration")
    root.geometry("700x500")

    # Slot data storage: list of dicts
    slot_frames = []
    slot_data = []

    main_container = ttk.Frame(root, padding=10)
    main_container.pack(fill=tk.BOTH, expand=True)

    # Scrollable canvas for slots
    canvas = tk.Canvas(main_container)
    scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    status_var = tk.StringVar(value="Configure your AutoFire slots and click Apply & Save")

    def capture_key(target_var: tk.StringVar, button: tk.Button) -> None:
        status_var.set("Press a key to capture...")
        button.configure(state=tk.DISABLED)

        def worker() -> None:
            try:
                key = keyboard.read_key(suppress=False)
            except Exception as exc:
                root.after(0, lambda: status_var.set(f"Capture failed: {exc}"))
            else:
                display = key.upper()
                root.after(0, lambda: target_var.set(display))
                root.after(0, lambda: status_var.set(f"Captured {display}"))
            finally:
                root.after(0, lambda: button.configure(state=tk.NORMAL))

        threading.Thread(target=worker, name="CaptureKey", daemon=True).start()

    def create_slot_ui(parent: ttk.Frame, slot: AutoFireSlot, index: int) -> dict:
        frame = ttk.LabelFrame(parent, text=f"Slot {index + 1}", padding=10)
        frame.pack(fill="x", padx=5, pady=5)

        trigger_var = tk.StringVar(value=slot.trigger_key.upper())
        output_var = tk.StringVar(value=slot.output_key.upper())
        interval_var = tk.IntVar(value=slot.interval_ms)
        pass_through_var = tk.BooleanVar(value=slot.pass_through)
        enabled_var = tk.BooleanVar(value=slot.enabled)

        # Row 0: Enabled checkbox
        ttk.Checkbutton(frame, text="Enabled", variable=enabled_var).grid(
            column=0, row=0, columnspan=4, sticky="w", pady=(0, 5)
        )

        # Row 1: Trigger
        ttk.Label(frame, text="Trigger:").grid(column=0, row=1, sticky="w")
        trigger_entry = ttk.Entry(frame, textvariable=trigger_var, width=10)
        trigger_entry.grid(column=1, row=1, padx=4)
        trigger_btn = ttk.Button(
            frame,
            text="Capture",
            command=lambda: capture_key(trigger_var, trigger_btn),
        )
        trigger_btn.grid(column=2, row=1)

        # Row 2: Output
        ttk.Label(frame, text="Output:").grid(column=0, row=2, sticky="w")
        output_entry = ttk.Entry(frame, textvariable=output_var, width=10)
        output_entry.grid(column=1, row=2, padx=4)
        output_btn = ttk.Button(
            frame,
            text="Capture",
            command=lambda: capture_key(output_var, output_btn),
        )
        output_btn.grid(column=2, row=2)

        # Row 3: Interval
        ttk.Label(frame, text="Interval (ms):").grid(column=0, row=3, sticky="w")
        interval_spin = ttk.Spinbox(
            frame,
            from_=MIN_INTERVAL_MS,
            to=MAX_INTERVAL_MS,
            textvariable=interval_var,
            width=10,
        )
        interval_spin.grid(column=1, row=3, padx=4)

        # Row 4: Pass-through
        ttk.Checkbutton(frame, text="Pass-through", variable=pass_through_var).grid(
            column=0, row=4, columnspan=3, sticky="w", pady=(5, 0)
        )

        # Row 5: Remove button
        def remove_slot():
            frame.destroy()
            slot_frames.remove(data)
            slot_data.remove(data)
            update_slot_numbers()

        ttk.Button(frame, text="Remove Slot", command=remove_slot).grid(
            column=0, row=5, columnspan=3, pady=(5, 0), sticky="ew"
        )

        data = {
            "frame": frame,
            "trigger": trigger_var,
            "output": output_var,
            "interval": interval_var,
            "pass_through": pass_through_var,
            "enabled": enabled_var,
        }

        slot_frames.append(data)
        slot_data.append(data)
        return data

    def update_slot_numbers():
        for idx, data in enumerate(slot_data):
            data["frame"].configure(text=f"Slot {idx + 1}")

    def add_slot():
        create_slot_ui(scrollable_frame, AutoFireSlot(), len(slot_data))
        canvas.update_idletasks()
        canvas.yview_moveto(1.0)

    def on_apply_save():
        slots = []
        for data in slot_data:
            slot_dict = {
                "triggerKey": data["trigger"].get().strip(),
                "outputKey": data["output"].get().strip(),
                "intervalMs": data["interval"].get(),
                "passThrough": data["pass_through"].get(),
                "enabled": data["enabled"].get(),
            }
            try:
                slot = validate_slot(slot_dict)
                slots.append(slot)
            except ValueError as exc:
                status_var.set(f"Validation error: {exc}")
                messagebox.showerror("AutoFire", str(exc))
                return

        new_config = AutoFireConfig(slots=slots)
        
        try:
            write_config(config_path, new_config)
        except OSError as exc:
            status_var.set(f"Error: unable to save ({exc})")
            messagebox.showerror("AutoFire", f"Unable to save config: {exc}")
            return

        try:
            app.apply_binding(new_config)
        except RuntimeError as exc:
            status_var.set(f"Error: {exc}")
            messagebox.showerror("AutoFire", str(exc))
            return

        status_var.set("Configuration saved and applied successfully!")
        messagebox.showinfo("AutoFire", "Configuration saved and applied!")

    # Initialize with existing slots
    for idx, slot in enumerate(app.config.slots):
        create_slot_ui(scrollable_frame, slot, idx)

    # Bottom control frame
    control_frame = ttk.Frame(root, padding=10)
    control_frame.pack(fill="x", side="bottom")

    ttk.Button(control_frame, text="+ Add Slot", command=add_slot).pack(side="left", padx=5)
    ttk.Button(control_frame, text="Apply & Save", command=on_apply_save).pack(side="left", padx=5)

    status_label = ttk.Label(control_frame, textvariable=status_var, relief=tk.SUNKEN)
    status_label.pack(side="left", fill="x", expand=True, padx=5)

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
