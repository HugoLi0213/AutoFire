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
    window_title: str = ""  # Target window for PostMessage
    use_sendinput: bool = True  # Use SendInput vs PostMessage

    def as_dict(self) -> dict[str, Any]:
        return {
            "triggerKey": self.trigger_key,
            "outputKey": self.output_key,
            "intervalMs": self.interval_ms,
            "passThrough": self.pass_through,
            "enabled": self.enabled,
            "windowTitle": self.window_title,
            "useSendInput": self.use_sendinput,
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
    language: str = "en"  # UI language: en, zh_TW, zh_CN

    def __post_init__(self):
        if self.slots is None:
            self.slots = [AutoFireSlot()]

    def as_dict(self) -> dict[str, Any]:
        return {
            "slots": [slot.as_dict() for slot in self.slots],
            "language": self.language
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
    window_title = str(mapping.get("windowTitle", ""))
    use_sendinput = _coerce_bool(mapping.get("useSendInput", True))
    return AutoFireSlot(
        trigger_key=trigger,
        output_key=output,
        interval_ms=interval,
        pass_through=pass_through,
        enabled=enabled,
        window_title=window_title,
        use_sendinput=use_sendinput,
    )


def validate_config(mapping: Mapping[str, Any]) -> AutoFireConfig:
    """Validate a config mapping and return an AutoFireConfig instance."""

    # Support legacy format (single slot)
    if "triggerKey" in mapping and "slots" not in mapping:
        slot = validate_slot(mapping)
        language = str(mapping.get("language", "en"))
        return AutoFireConfig(slots=[slot], language=language)

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
    
    language = str(mapping.get("language", "en"))
    return AutoFireConfig(slots=slots, language=language)


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


# Translations for UI
TRANSLATIONS = {
    "en": {
        "title": "AutoFire",
        "simple_mode": "Simple Mode",
        "multi_mode": "Multi-Slot Mode",
        "switch_to_multi": "Switch to Multi-Slot Mode →",
        "switch_to_simple": "← Switch to Simple Mode",
        "trigger_key": "Trigger key",
        "output_key": "Output key",
        "target_window": "Target Window",
        "interval": "Interval (ms)",
        "pass_through": "Pass-through trigger key",
        "use_sendinput": "Use SendInput (better game compatibility)",
        "start": "Start",
        "stop": "Stop",
        "apply_save": "Apply & Save",
        "add_slot": "+ Add Slot",
        "remove_slot": "Remove Slot",
        "enabled": "Enabled",
        "capture": "Capture",
        "refresh": "🔄",
        "running": "Running",
        "stopped": "Stopped",
        "no_windows": "No windows found",
        "status": "Configure your settings and click Start",
    },
    "zh_TW": {
        "title": "AutoFire 自動連發",
        "simple_mode": "簡易模式",
        "multi_mode": "多槽位模式",
        "switch_to_multi": "切換至多槽位模式 →",
        "switch_to_simple": "← 切換至簡易模式",
        "trigger_key": "觸發鍵",
        "output_key": "輸出鍵",
        "target_window": "目標視窗",
        "interval": "間隔 (毫秒)",
        "pass_through": "穿透觸發鍵",
        "use_sendinput": "使用 SendInput (更好的遊戲相容性)",
        "start": "啟動",
        "stop": "停止",
        "apply_save": "套用並儲存",
        "add_slot": "+ 新增槽位",
        "remove_slot": "移除槽位",
        "enabled": "啟用",
        "capture": "擷取",
        "refresh": "🔄",
        "running": "執行中",
        "stopped": "已停止",
        "no_windows": "未找到視窗",
        "status": "設定完成後點擊啟動",
    },
    "zh_CN": {
        "title": "AutoFire 自动连发",
        "simple_mode": "简易模式",
        "multi_mode": "多槽位模式",
        "switch_to_multi": "切换至多槽位模式 →",
        "switch_to_simple": "← 切换至简易模式",
        "trigger_key": "触发键",
        "output_key": "输出键",
        "target_window": "目标窗口",
        "interval": "间隔 (毫秒)",
        "pass_through": "穿透触发键",
        "use_sendinput": "使用 SendInput (更好的游戏兼容性)",
        "start": "启动",
        "stop": "停止",
        "apply_save": "应用并保存",
        "add_slot": "+ 添加槽位",
        "remove_slot": "移除槽位",
        "enabled": "启用",
        "capture": "捕获",
        "refresh": "🔄",
        "running": "运行中",
        "stopped": "已停止",
        "no_windows": "未找到窗口",
        "status": "配置完成后点击启动",
    }
}


def get_all_window_titles() -> list[str]:
    """Get a list of all visible window titles (Windows only)."""
    if sys.platform != "win32":
        return []
    
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return []
    
    windows = []
    
    def enum_windows_callback(hwnd, _):
        try:
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    if title and title.strip():
                        windows.append(title)
        except Exception:
            pass
        return True
    
    try:
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        callback = EnumWindowsProc(enum_windows_callback)
        ctypes.windll.user32.EnumWindows(callback, 0)
    except Exception:
        pass
    
    return sorted(set(windows))


def run_ui(app: AutoFireApp, config_path: Path) -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk, scrolledtext

    root = tk.Tk()
    root.title("AutoFire")
    
    # Track UI mode
    ui_mode = tk.StringVar(value="simple" if len(app.config.slots) == 1 else "multi")
    
    def show_simple_ui():
        ui_mode.set("simple")
        show_ui()
    
    def show_multi_ui():
        ui_mode.set("multi")
        show_ui()
    
    def show_ui():
        # Clear all widgets
        for widget in root.winfo_children():
            widget.destroy()
        
        if ui_mode.get() == "simple":
            run_simple_ui(root, app, config_path, show_multi_ui)
        else:
            run_multi_ui(root, app, config_path, show_simple_ui)
    
    show_ui()
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


def run_simple_ui(root: Any, app: AutoFireApp, config_path: Path, switch_callback) -> None:
    """Simple single-slot UI (original design with all features)"""
    import tkinter as tk
    from tkinter import messagebox, ttk
    
    root.geometry("500x400")
    root.resizable(False, False)

    # Get first slot or create default
    slot = app.config.slots[0] if app.config.slots else AutoFireSlot()
    
    # Language
    current_lang = tk.StringVar(value=app.config.language)
    
    # Variables
    trigger_var = tk.StringVar(value=slot.trigger_key.upper())
    output_var = tk.StringVar(value=slot.output_key.upper())
    interval_var = tk.IntVar(value=slot.interval_ms)
    pass_through_var = tk.BooleanVar(value=slot.pass_through)
    window_title_var = tk.StringVar(value=slot.window_title)
    use_sendinput_var = tk.BooleanVar(value=slot.use_sendinput)
    status_var = tk.StringVar(value=TRANSLATIONS[current_lang.get()]["status"])
    
    # Track UI elements for language switching
    ui_elements = {}
    
    def toggle_language() -> None:
        langs = ["en", "zh_TW", "zh_CN"]
        current_idx = langs.index(current_lang.get())
        next_lang = langs[(current_idx + 1) % len(langs)]
        current_lang.set(next_lang)
        update_ui_language()
        # Save language preference
        config = AutoFireConfig(slots=app.config.slots, language=next_lang)
        write_config(config_path, config)
    
    def update_ui_language() -> None:
        t = TRANSLATIONS[current_lang.get()]
        root.title(t["title"])
        ui_elements['mode_label'].config(text=t["simple_mode"])
        ui_elements['switch_btn'].config(text=t["switch_to_multi"])
        ui_elements['trigger_label'].config(text=t["trigger_key"])
        ui_elements['output_label'].config(text=t["output_key"])
        ui_elements['window_label'].config(text=t["target_window"])
        ui_elements['interval_label'].config(text=t["interval"])
        ui_elements['pass_check'].config(text=t["pass_through"])
        ui_elements['sendinput_check'].config(text=t["use_sendinput"])
        ui_elements['start_btn'].config(text=t["start"])
        ui_elements['stop_btn'].config(text=t["stop"])
        status_var.set(t["running"] if app.is_running else t["stopped"])
    
    def refresh_windows() -> None:
        windows = get_all_window_titles()
        ui_elements['window_combo']['values'] = windows if windows else [TRANSLATIONS[current_lang.get()]["no_windows"]]

    def on_start() -> None:
        data = {
            "triggerKey": trigger_var.get().strip(),
            "outputKey": output_var.get().strip(),
            "intervalMs": interval_var.get(),
            "passThrough": pass_through_var.get(),
            "enabled": True,
            "windowTitle": window_title_var.get().strip(),
            "useSendInput": use_sendinput_var.get(),
        }
        try:
            new_slot = validate_slot(data)
        except ValueError as exc:
            status_var.set(f"Error: {exc}")
            messagebox.showerror("AutoFire", str(exc))
            return
        
        new_config = AutoFireConfig(slots=[new_slot], language=current_lang.get())
        
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
        t = TRANSLATIONS[current_lang.get()]
        status_var.set(t["running"])
        ui_elements['start_btn'].config(state=tk.DISABLED)
        ui_elements['stop_btn'].config(state=tk.NORMAL)
    
    def on_stop() -> None:
        for trigger_key in list(app._slot_workers.keys()):
            app.stop_loop(trigger_key, join=True)
        t = TRANSLATIONS[current_lang.get()]
        status_var.set(t["stopped"])
        ui_elements['start_btn'].config(state=tk.NORMAL)
        ui_elements['stop_btn'].config(state=tk.DISABLED)

    # Header with mode switch and language toggle
    header = ttk.Frame(root, padding=5)
    header.pack(fill="x")
    ui_elements['mode_label'] = ttk.Label(header, text="Simple Mode", font=("", 10, "bold"))
    ui_elements['mode_label'].pack(side="left")
    ttk.Button(header, text="EN/繁/简", width=8, command=toggle_language).pack(side="right", padx=2)
    ui_elements['switch_btn'] = ttk.Button(header, text="Switch to Multi-Slot Mode →", command=switch_callback)
    ui_elements['switch_btn'].pack(side="right")

    frame = ttk.Frame(root, padding=10)
    frame.pack(fill="both", expand=True)

    row = 0
    # Trigger key
    ui_elements['trigger_label'] = ttk.Label(frame, text="Trigger", width=20)
    ui_elements['trigger_label'].grid(column=0, row=row, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=trigger_var, width=25).grid(column=1, row=row, columnspan=2, padx=4, pady=4, sticky="ew")
    
    row += 1
    # Output key
    ui_elements['output_label'] = ttk.Label(frame, text="Output", width=20)
    ui_elements['output_label'].grid(column=0, row=row, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=output_var, width=25).grid(column=1, row=row, columnspan=2, padx=4, pady=4, sticky="ew")
    
    row += 1
    # Target Window
    ui_elements['window_label'] = ttk.Label(frame, text="Target Window", width=20)
    ui_elements['window_label'].grid(column=0, row=row, sticky="w", pady=4)
    ui_elements['window_combo'] = ttk.Combobox(frame, textvariable=window_title_var, width=13)
    ui_elements['window_combo'].grid(column=1, row=row, padx=4, pady=4)
    ttk.Button(frame, text="🔄", width=3, command=refresh_windows).grid(column=2, row=row, pady=4)
    
    row += 1
    # Interval
    ui_elements['interval_label'] = ttk.Label(frame, text="Interval (ms)", width=20)
    ui_elements['interval_label'].grid(column=0, row=row, sticky="w", pady=4)
    ttk.Spinbox(frame, from_=MIN_INTERVAL_MS, to=MAX_INTERVAL_MS, textvariable=interval_var, width=15).grid(column=1, row=row, padx=4, sticky="ew", pady=4)
    
    row += 1
    # Pass-through
    ui_elements['pass_check'] = ttk.Checkbutton(frame, text="Pass-through", variable=pass_through_var)
    ui_elements['pass_check'].grid(column=0, row=row, columnspan=3, sticky="w", pady=4)
    
    row += 1
    # SendInput toggle
    ui_elements['sendinput_check'] = ttk.Checkbutton(frame, text="Use SendInput", variable=use_sendinput_var)
    ui_elements['sendinput_check'].grid(column=0, row=row, columnspan=3, sticky="w", pady=4)
    
    row += 1
    # Buttons
    button_frame = ttk.Frame(frame)
    button_frame.grid(column=0, row=row, columnspan=3, pady=(15, 5), sticky="ew")
    ui_elements['start_btn'] = ttk.Button(button_frame, text="Start", command=on_start)
    ui_elements['start_btn'].pack(side="left", expand=True, fill="x", padx=3)
    ui_elements['stop_btn'] = ttk.Button(button_frame, text="Stop", command=on_stop, state=tk.DISABLED)
    ui_elements['stop_btn'].pack(side="left", expand=True, fill="x", padx=3)
    
    row += 1
    # Status
    status_label = ttk.Label(frame, textvariable=status_var, relief=tk.SUNKEN, anchor="w")
    status_label.grid(column=0, row=row, columnspan=3, sticky="ew", pady=(10, 0))

    # Initialize window list
    refresh_windows()
    
    # Update language
    update_ui_language()


def run_multi_ui(root: Any, app: AutoFireApp, config_path: Path, switch_callback) -> None:
    """Multi-slot UI with add/remove functionality"""
    import tkinter as tk
    from tkinter import messagebox, ttk
    
    root.geometry("700x500")

    # Header with mode switch
    header = ttk.Frame(root, padding=5)
    header.pack(fill="x")
    ttk.Label(header, text="Multi-Slot Mode", font=("", 10, "bold")).pack(side="left")
    ttk.Button(header, text="← Switch to Simple Mode", command=switch_callback).pack(side="right")

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
        ttk.Entry(frame, textvariable=trigger_var, width=15).grid(column=1, row=1, columnspan=2, padx=4, sticky="ew")

        # Row 2: Output
        ttk.Label(frame, text="Output:").grid(column=0, row=2, sticky="w")
        ttk.Entry(frame, textvariable=output_var, width=15).grid(column=1, row=2, columnspan=2, padx=4, sticky="ew")

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
