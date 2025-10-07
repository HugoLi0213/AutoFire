"""Minimal AutoFire Tk GUI for Windows using PostMessage.

Author: Hugo
Last Updated: 2025-10-06

SECURITY & ANTI-CHEAT CONSIDERATIONS:
=====================================
This application uses LEGITIMATE Windows API calls for input simulation:

✓ Standard Input Simulation: Uses PostMessage(), a legitimate Windows API call
  that sends simulated keyboard inputs to the target window's message queue.
  This is the SAME mechanism used by:
  - Remote desktop software (TeamViewer, RDP)
  - Accessibility tools (screen readers, voice control)
  - Macro utilities and automation software

✓ No Memory Interference: Does NOT read from or write to game memory.
  Does NOT hook into game's internal functions or inject any code (DLLs).
  Operates entirely outside the game process.

✓ Reduced Detection Risk: From the OS perspective, PostMessage inputs are
  indistinguishable from legitimate software-generated inputs. Anti-cheat
  systems are unlikely to block this API because doing so would break many
  normal applications (false positives).

✓ Non-Invasive: Only sends WM_KEYDOWN and WM_KEYUP messages to the window's
  message queue - the same way other legitimate software communicates.

Usage: Run from an elevated command prompt for keyboard hook permissions.
The UI lets you choose a trigger key, output key, repeat interval, and target
window. Press *Start*, hold the trigger key to activate rapid-fire output.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import messagebox, ttk

# This is a third-party library, ensure it's installed
try:
    import keyboard
except ImportError:
    raise SystemExit("The 'keyboard' library is required. Please run 'pip install keyboard'.")

# Windows API integration using ctypes
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    # Constants for Windows API
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101

    # SendInput constants (AHK-like behavior)
    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_SCANCODE = 0x0008

    # Virtual Key Codes (a small subset)
    # A more complete mapping would be needed for full key support
    VK_CODES = {
        'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46,
        'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C,
        'm': 0x4D, 'n': 0x4E, 'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52,
        's': 0x53, 't': 0x54, 'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58,
        'y': 0x59, 'z': 0x5A,
        '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34, '5': 0x35,
        '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
        'enter': 0x0D, 'space': 0x20, 'backspace': 0x08, 'tab': 0x09,
        'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12,
    }

    # Define SendInput structures for AHK-like input simulation
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

    def send_key_with_sendinput(vk_code: int, key_up: bool = False) -> None:
        """Send keyboard input using SendInput API (AHK-like behavior).
        
        This simulates hardware-level input and works with DirectInput games.
        """
        # Get scan code from virtual key code
        scan_code = ctypes.windll.user32.MapVirtualKeyW(vk_code, 0)
        
        # Create keyboard input structure
        ki = KEYBDINPUT()
        ki.wVk = vk_code
        ki.wScan = scan_code
        ki.dwFlags = KEYEVENTF_KEYUP if key_up else 0
        ki.time = 0
        ki.dwExtraInfo = None
        
        # Create INPUT structure
        input_struct = INPUT()
        input_struct.type = INPUT_KEYBOARD
        input_struct.union.ki = ki
        
        # Send the input
        ctypes.windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

CONFIG_PATH = Path(__file__).with_name("autofire.json")
MIN_INTERVAL_MS = 1
MAX_INTERVAL_MS = 1000

# Translations
TRANSLATIONS = {
    "en": {
        "title": "AutoFire (PostMessage)",
        "trigger_key": "Trigger key",
        "output_key": "Output key",
        "target_window": "Target Window Title",
        "interval": "Interval (ms)",
        "pass_through": "Pass-through trigger key",
        "use_sendinput": "Use SendInput (AHK-like, better game compatibility)",
        "start": "Start",
        "stop": "Stop",
        "author_info": "Author: Hugo | Last Updated: 2025-10-06",
        "running": "Running",
        "stopped": "Stopped",
        "error_window": "Error: Window",
        "no_windows": "No windows found",
    },
    "zh_TW": {
        "title": "AutoFire 自動連發工具",
        "trigger_key": "觸發鍵",
        "output_key": "輸出鍵",
        "target_window": "目標視窗標題",
        "interval": "間隔 (毫秒)",
        "pass_through": "穿透觸發鍵",
        "use_sendinput": "使用 SendInput (AHK 風格，更好的遊戲相容性)",
        "start": "啟動",
        "stop": "停止",
        "author_info": "作者：Hugo | 最後更新：2025-10-06",
        "running": "執行中",
        "stopped": "已停止",
        "error_window": "錯誤：視窗",
        "no_windows": "未找到視窗",
    }
}


def get_all_window_titles() -> list[str]:
    """Get a list of all visible window titles."""
    if sys.platform != "win32":
        return []
    
    windows = []
    
    def enum_windows_callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value
                if title and title.strip():
                    windows.append(title)
        return True
    
    # Define the callback function type
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    callback = EnumWindowsProc(enum_windows_callback)
    ctypes.windll.user32.EnumWindows(callback, 0)
    
    # Sort alphabetically and remove duplicates
    return sorted(set(windows))


@dataclass(slots=True)
class AutoFireConfig:
    trigger_key: str = "e"
    output_key: str = "r"
    interval_ms: int = 50
    window_title: str = "Untitled - Notepad"  # New field for PostMessage target
    pass_through: bool = False # This is now managed by the keyboard library
    use_sendinput: bool = True  # Use SendInput (AHK-like) by default
    language: str = "en"  # Language setting: "en" or "zh_TW"

    def formatted(self) -> str:
        return (
            f"AutoFire (PostMessage): {self.trigger_key.upper()}->{self.output_key.upper()} "
            f"@ {self.interval_ms}ms -> '{self.window_title}'"
        )


class AutoFireEngine:
    def __init__(
        self,
        status_callback: Callable[[str, AutoFireConfig], None],
        error_callback: Callable[[str, AutoFireConfig], None],
    ) -> None:
        self._config = AutoFireConfig()
        self._status_callback = status_callback
        self._error_callback = error_callback
        self._is_running = False
        self._is_active = False
        self._error_state: Optional[str] = None
        self._pending_error_status: Optional[tuple[str, AutoFireConfig]] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def config(self) -> AutoFireConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._is_running

    def apply_config(self, config: AutoFireConfig) -> None:
        if self.is_running:
            self.unbind_trigger_handlers()
        self._config = config

    def bind_trigger_handlers(self) -> None:
        if self.is_running:
            return

        self._error_state = None
        self._is_running = True
        try:
            # The 'suppress' argument should be True to block the event,
            # which is the opposite of 'pass_through'.
            suppress_event = not self.config.pass_through
            keyboard.on_press_key(
                self.config.trigger_key,
                self._on_trigger_press,
                suppress=suppress_event,
            )
            keyboard.on_release_key(
                self.config.trigger_key,
                self._on_trigger_release,
                suppress=suppress_event,
            )
            self._update_status("Running")
        except Exception as exc:
            self._is_running = False
            raise RuntimeError(
                f"Failed to bind keys. Try running as Administrator. Error: {exc}"
            )

    def unbind_trigger_handlers(self) -> None:
        if not self.is_running:
            return
        
        self._is_running = False
        self._set_active(False) # Ensure the loop stops
        keyboard.unhook_all()
        self._update_status("Stopped")

    def shutdown(self) -> None:
        self.unbind_trigger_handlers()

    def _on_trigger_press(self, e: keyboard.KeyboardEvent) -> None:
        # This check prevents the hotkey from re-triggering itself if not suppressed
        if e.name != self._config.trigger_key.lower():
            return
        self._set_active(True)

    def _on_trigger_release(self, e: keyboard.KeyboardEvent) -> None:
        if e.name != self._config.trigger_key.lower():
            return
        self._set_active(False)

    def _set_active(self, active: bool) -> None:
        with self._lock:
            if self._is_active == active:
                return
            self._is_active = active

            if active and self._is_running:
                if not self._error_state:
                    self._update_status("[active]")
                # Start the autofire loop in a new thread
                self._thread = threading.Thread(target=self._autofire_loop, daemon=True)
                self._thread.start()
            elif not active and self._is_running:
                if not self._error_state:
                    self._update_status("Running")

    def _autofire_loop(self) -> None:
        """The main loop that sends keyboard events.
        
        Uses SendInput (AHK-like) by default for better game compatibility,
        or PostMessage for window-specific targeting.
        """
        # For PostMessage, we need a window handle
        hwnd = None
        if not self.config.use_sendinput:
            hwnd = ctypes.windll.user32.FindWindowW(None, self.config.window_title)
            if not hwnd:
                logging.warning(f"Window '{self.config.window_title}' not found.")
                with self._lock:
                    self._error_state = "Error: Window"
                    self._is_active = False
                    self._pending_error_status = ("Error: Window", self.config)
                return

        vk_code = VK_CODES.get(self.config.output_key.lower())
        if not vk_code:
            self._update_status(f"Error: Key '{self.config.output_key}' not supported.")
            with self._lock:
                self._is_active = False
            return

        interval_sec = self.config.interval_ms / 1000.0

        while True:
            with self._lock:
                if not self._is_active or not self._is_running:
                    break
            
            if self.config.use_sendinput:
                # SendInput method (AHK-like) - works with DirectInput games
                send_key_with_sendinput(vk_code, key_up=False)
                time.sleep(0.02)  # Small delay between down and up
                send_key_with_sendinput(vk_code, key_up=True)
            else:
                # PostMessage method - window-specific targeting
                ctypes.windll.user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, 0)
                time.sleep(0.02)
                ctypes.windll.user32.PostMessageW(hwnd, WM_KEYUP, vk_code, 0)
            
            time.sleep(interval_sec)

    def _update_status(self, state: str) -> None:
        self._status_callback(state, self._config)

    def get_pending_error_status(self) -> Optional[tuple[str, AutoFireConfig]]:
        """Check if there's a pending error status from a background thread."""
        with self._lock:
            error = self._pending_error_status
            self._pending_error_status = None
            return error


def load_config() -> AutoFireConfig:
    if not CONFIG_PATH.exists():
        return AutoFireConfig()
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Could not load or parse config: {exc}")
        return AutoFireConfig()
        
    return AutoFireConfig(
        trigger_key=raw.get("trigger_key", "e"),
        output_key=raw.get("output_key", "r"),
        interval_ms=raw.get("interval_ms", 50),
        window_title=raw.get("window_title", "Untitled - Notepad"),
        pass_through=raw.get("pass_through", False),
        use_sendinput=raw.get("use_sendinput", True),
        language=raw.get("language", "en"),
    )


def save_config(config: AutoFireConfig) -> None:
    payload = {
        "trigger_key": config.trigger_key,
        "output_key": config.output_key,
        "interval_ms": config.interval_ms,
        "window_title": config.window_title,
        "pass_through": config.pass_through,
        "use_sendinput": config.use_sendinput,
        "language": config.language,
    }
    try:
        CONFIG_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"Could not save config: {exc}")


class AutoFireUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AutoFire (PostMessage)")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if sys.platform != "win32":
            raise SystemExit("This script is supported on Windows only.")

        self.engine = AutoFireEngine(
            self._schedule_status_update, self._immediate_status_update
        )
        self._pending_status = "Stopped"
        self._current_config = self.engine.config

        self.trigger_var = tk.StringVar(root)
        self.output_var = tk.StringVar(root)
        self.interval_var = tk.IntVar(root)
        self.pass_var = tk.BooleanVar(root)
        self.window_title_var = tk.StringVar(root)
        self.use_sendinput_var = tk.BooleanVar(root)

        self.status_var = tk.StringVar(root)
        
        # Language settings
        self.current_language = "en"
        self.translations = TRANSLATIONS

        # Store UI elements for language switching
        self.ui_elements = {}

        self._build_layout()
        config = load_config()
        self.current_language = config.language
        self.populate_from_config(config)
        self._update_ui_language()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        # --- Language Toggle Button (Top Right) ---
        lang_row = ttk.Frame(container)
        lang_row.pack(fill=tk.X, pady=(0, 10))
        self.lang_button = ttk.Button(lang_row, text="EN/繁中", width=10, command=self.toggle_language)
        self.lang_button.pack(side=tk.RIGHT)

        # --- Input Fields ---
        # Trigger key
        trigger_row = ttk.Frame(container)
        trigger_row.pack(fill=tk.X, pady=4)
        self.ui_elements['trigger_label'] = ttk.Label(trigger_row, text="Trigger key", width=20)
        self.ui_elements['trigger_label'].pack(side=tk.LEFT)
        ttk.Entry(trigger_row, textvariable=self.trigger_var, width=25).pack(side=tk.LEFT, padx=6)
        
        # Output key
        output_row = ttk.Frame(container)
        output_row.pack(fill=tk.X, pady=4)
        self.ui_elements['output_label'] = ttk.Label(output_row, text="Output key", width=20)
        self.ui_elements['output_label'].pack(side=tk.LEFT)
        ttk.Entry(output_row, textvariable=self.output_var, width=25).pack(side=tk.LEFT, padx=6)
        
        # Target Window Title with dropdown and refresh button
        window_row = ttk.Frame(container)
        window_row.pack(fill=tk.X, pady=4)
        self.ui_elements['window_label'] = ttk.Label(window_row, text="Target Window Title", width=20)
        self.ui_elements['window_label'].pack(side=tk.LEFT)
        self.window_combo = ttk.Combobox(window_row, textvariable=self.window_title_var, width=23)
        self.window_combo.pack(side=tk.LEFT, padx=6)
        refresh_btn = ttk.Button(window_row, text="🔄", width=3, command=self.refresh_window_list)
        refresh_btn.pack(side=tk.LEFT, padx=2)
        
        # Populate the window list initially
        self.refresh_window_list()

        interval_row = ttk.Frame(container)
        interval_row.pack(fill=tk.X, pady=4)
        self.ui_elements['interval_label'] = ttk.Label(interval_row, text="Interval (ms)", width=20)
        self.ui_elements['interval_label'].pack(side=tk.LEFT)
        ttk.Spinbox(
            interval_row, from_=MIN_INTERVAL_MS, to=MAX_INTERVAL_MS,
            textvariable=self.interval_var, width=23
        ).pack(side=tk.LEFT, padx=6)

        pass_row = ttk.Frame(container)
        pass_row.pack(fill=tk.X, pady=4)
        self.ui_elements['pass_check'] = ttk.Checkbutton(pass_row, text="Pass-through trigger key", variable=self.pass_var)
        self.ui_elements['pass_check'].pack(side=tk.LEFT)

        # SendInput method selection
        method_row = ttk.Frame(container)
        method_row.pack(fill=tk.X, pady=4)
        self.ui_elements['sendinput_check'] = ttk.Checkbutton(method_row, text="Use SendInput (AHK-like, better game compatibility)", variable=self.use_sendinput_var)
        self.ui_elements['sendinput_check'].pack(side=tk.LEFT)

        # --- Buttons ---
        button_row = ttk.Frame(container)
        button_row.pack(fill=tk.X, pady=10)
        self.ui_elements['start_button'] = ttk.Button(button_row, text="Start", command=self.start_autofire)
        self.ui_elements['start_button'].pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.ui_elements['stop_button'] = ttk.Button(button_row, text="Stop", command=self.stop_autofire)
        self.ui_elements['stop_button'].pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        # --- Status Bar ---
        ttk.Label(container, textvariable=self.status_var, relief=tk.SUNKEN, padding=6).pack(fill=tk.X, pady=(8, 0))
        self.ui_elements['info_label'] = ttk.Label(container, text="Author: Hugo | Last Updated: 2025-10-06", foreground="gray")
        self.ui_elements['info_label'].pack(pady=(6, 0))

    def toggle_language(self) -> None:
        """Toggle between English and Traditional Chinese."""
        self.current_language = "zh_TW" if self.current_language == "en" else "en"
        self._update_ui_language()
        # Save language preference
        config = self._build_config_from_inputs()
        if config:
            config.language = self.current_language
            save_config(config)

    def _update_ui_language(self) -> None:
        """Update all UI text based on current language."""
        t = self.translations[self.current_language]
        
        # Update window title
        self.root.title(t["title"])
        
        # Update labels
        self.ui_elements['trigger_label'].config(text=t["trigger_key"])
        self.ui_elements['output_label'].config(text=t["output_key"])
        self.ui_elements['window_label'].config(text=t["target_window"])
        self.ui_elements['interval_label'].config(text=t["interval"])
        
        # Update checkboxes
        self.ui_elements['pass_check'].config(text=t["pass_through"])
        self.ui_elements['sendinput_check'].config(text=t["use_sendinput"])
        
        # Update buttons
        self.ui_elements['start_button'].config(text=t["start"])
        self.ui_elements['stop_button'].config(text=t["stop"])
        
        # Update info label
        self.ui_elements['info_label'].config(text=t["author_info"])
        
        # Update status if needed
        if self.engine.is_running:
            status = t["running"]
        else:
            status = t["stopped"]
        self._update_status_display(status, self.engine.config)

    def refresh_window_list(self) -> None:
        """Refresh the list of available windows in the dropdown."""
        windows = get_all_window_titles()
        self.window_combo['values'] = windows
        if not windows:
            t = self.translations[self.current_language]
            self.window_combo['values'] = [t["no_windows"]]
    
    def populate_from_config(self, config: AutoFireConfig) -> None:
        self.trigger_var.set(config.trigger_key)
        self.output_var.set(config.output_key)
        self.interval_var.set(config.interval_ms)
        self.pass_var.set(config.pass_through)
        self.window_title_var.set(config.window_title)
        self.use_sendinput_var.set(config.use_sendinput)
        self.current_language = config.language
        
        self.engine.apply_config(config)
        self._update_status_display("Stopped", config)
        self._set_button_states(running=False)

    def start(self) -> None:
        self.root.mainloop()

    def on_close(self) -> None:
        self.stop_autofire()
        self.engine.shutdown()
        self.root.destroy()

    def start_autofire(self) -> None:
        config = self._build_config_from_inputs()
        if config is None:
            return

        # Apply config first to ensure engine state is correct before binding.
        self.engine.apply_config(config)
        save_config(config)

        try:
            self.engine.bind_trigger_handlers()
        except RuntimeError as exc:
            messagebox.showerror("AutoFire Error", str(exc), parent=self.root)
            return

        t = self.translations[self.current_language]
        self._update_status_display(t["running"], config)
        self._set_button_states(running=True)

    def stop_autofire(self) -> None:
        self.engine.unbind_trigger_handlers()
        t = self.translations[self.current_language]
        self._update_status_display(t["stopped"], self.engine.config)
        self._set_button_states(running=False)

    def _build_config_from_inputs(self) -> Optional[AutoFireConfig]:
        trigger = self.trigger_var.get().strip().lower()
        output = self.output_var.get().strip().lower()
        window_title = self.window_title_var.get().strip()

        if not all([trigger, output, window_title]):
            messagebox.showerror("AutoFire", "All fields must be filled.", parent=self.root)
            return None
        
        try:
            interval = int(self.interval_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("AutoFire", "Interval must be an integer.", parent=self.root)
            return None
            
        return AutoFireConfig(
            trigger_key=trigger,
            output_key=output,
            interval_ms=max(MIN_INTERVAL_MS, min(interval, MAX_INTERVAL_MS)),
            window_title=window_title,
            pass_through=bool(self.pass_var.get()),
            use_sendinput=bool(self.use_sendinput_var.get()),
            language=self.current_language,
        )

    def _schedule_status_update(self, state: str, config: AutoFireConfig) -> None:
        self.root.after(0, self._update_status_display, state, config)

    def _immediate_status_update(self, state: str, config: AutoFireConfig) -> None:
        """A thread-safe method for immediate status updates from errors in background threads."""
        # Directly set the internal Tkinter variable value without using .set()
        # This bypasses the Tk event loop and avoids blocking from background threads
        self.status_var._value = f"{config.formatted()} [{state}]"

    def _update_status_display(self, state: str, config: AutoFireConfig) -> None:
        self.status_var.set(f"{config.formatted()} [{state}]")

    def _set_button_states(self, running: bool) -> None:
        start_state = tk.DISABLED if running else tk.NORMAL
        stop_state = tk.NORMAL if running else tk.DISABLED
        self.ui_elements['start_button'].config(state=start_state)
        self.ui_elements['stop_button'].config(state=stop_state)


def main() -> None:
    root = tk.Tk()
    app = AutoFireUI(root)
    app.start()


if __name__ == "__main__":
    main()
