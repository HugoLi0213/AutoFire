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
from typing import Callable, Optional, Any

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
        "title": "AutoFire - Multi-Key Automation",
        "trigger_key": "Press This Key ▼",
        "output_key": "To Fire This Key ▶",
        "target_window": "Target Window (Optional)",
        "interval": "Speed (ms) - Lower = Faster",
        "pass_through": "🔓 Allow Original Key (Mix Mode)",
        "use_sendinput": "⚡ Hardware Mode (Best for Games)",
        "start": "▶ START",
        "stop": "⏹ STOP",
        "author_info": "Author: Hugo | Last Updated: 2025-10-07",
        "running": "Running",
        "stopped": "Stopped",
        "error_window": "Error: Window",
        "no_windows": "No windows found",
        "slots": "⚡ AutoFire Slots",
        "add_slot": "➕ Add New",
        "remove_slot": "➖ Delete",
        "slot_enabled": "✓ Active",
        "guide": "💡 Hold trigger key → Auto-fires output key repeatedly | Create multiple slots for different keys",
    },
    "zh_TW": {
        "title": "AutoFire - 多鍵自動化工具",
        "trigger_key": "按下此鍵 ▼",
        "output_key": "自動連發此鍵 ▶",
        "target_window": "指定視窗 (選填)",
        "interval": "速度 (毫秒) - 越小越快",
        "pass_through": "🔓 保留原始按鍵 (混合模式)",
        "use_sendinput": "⚡ 硬體模式 (遊戲最佳)",
        "start": "▶ 啟動",
        "stop": "⏹ 停止",
        "author_info": "作者：Hugo | 最後更新：2025-10-07",
        "running": "執行中",
        "stopped": "已停止",
        "error_window": "錯誤：視窗",
        "no_windows": "未找到視窗",
        "slots": "⚡ 自動連發組合",
        "add_slot": "➕ 新增",
        "remove_slot": "➖ 刪除",
        "slot_enabled": "✓ 啟用",
        "guide": "💡 按住觸發鍵 → 自動連發輸出鍵 | 可建立多個插槽設定不同按鍵",
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
class AutoFireSlot:
    """Configuration for a single AutoFire slot."""
    trigger_key: str = "e"
    output_key: str = "r"
    interval_ms: int = 50
    window_title: str = ""  # Empty means global (no window targeting)
    pass_through: bool = False
    use_sendinput: bool = True
    enabled: bool = True

    def formatted(self) -> str:
        target = f"-> '{self.window_title}'" if self.window_title else "(global)"
        method = "SendInput" if self.use_sendinput else "PostMessage"
        return (
            f"{self.trigger_key.upper()}->{self.output_key.upper()} "
            f"@{self.interval_ms}ms {target} [{method}]"
        )


@dataclass(slots=True)
class AutoFireConfig:
    """Configuration containing multiple AutoFire slots."""
    slots: list = field(default_factory=lambda: [AutoFireSlot()])
    language: str = "en"  # Language setting: "en", "zh_TW", or "zh_CN"

    def formatted(self) -> str:
        enabled_count = sum(1 for s in self.slots if s.enabled)
        return f"AutoFire: {enabled_count}/{len(self.slots)} slots enabled"


class AutoFireEngine:
    def __init__(
        self,
        status_callback: Callable[[str, AutoFireSlot], None],
        error_callback: Callable[[str, AutoFireSlot], None],
    ) -> None:
        self._slots: list[AutoFireSlot] = []
        self._status_callback = status_callback
        self._error_callback = error_callback
        self._is_running = False
        self._slot_states: dict[str, bool] = {}  # trigger_key -> is_active
        self._slot_threads: dict[str, threading.Thread] = {}  # trigger_key -> thread
        self._lock = threading.Lock()

    @property
    def slot(self) -> AutoFireSlot:
        """For backward compatibility - returns first slot."""
        return self._slots[0] if self._slots else AutoFireSlot()

    @property
    def is_running(self) -> bool:
        return self._is_running

    def apply_slots(self, slots: list[AutoFireSlot]) -> None:
        """Apply multiple slots to the engine."""
        if self.is_running:
            self.unbind_trigger_handlers()
        self._slots = [s for s in slots if s.enabled]
        
    def apply_slot(self, slot: AutoFireSlot) -> None:
        """For backward compatibility - apply a single slot."""
        if self.is_running:
            self.unbind_trigger_handlers()
        self._slots = [slot] if slot.enabled else []

    def bind_trigger_handlers(self) -> None:
        if self.is_running:
            return

        if not self._slots:
            raise RuntimeError("No enabled slots to bind.")

        self._is_running = True
        self._slot_states = {}
        try:
            # Bind handlers for each enabled slot
            for slot in self._slots:
                self._slot_states[slot.trigger_key] = False
                suppress_event = not slot.pass_through
                
                # Create closure to capture slot
                def make_press_handler(s):
                    return lambda e: self._on_trigger_press(e, s)
                
                def make_release_handler(s):
                    return lambda e: self._on_trigger_release(e, s)
                
                keyboard.on_press_key(
                    slot.trigger_key,
                    make_press_handler(slot),
                    suppress=suppress_event,
                )
                keyboard.on_release_key(
                    slot.trigger_key,
                    make_release_handler(slot),
                    suppress=suppress_event,
                )
            
            enabled_count = len(self._slots)
            status = f"Running ({enabled_count} slot{'s' if enabled_count > 1 else ''})"
            self._status_callback(status, self._slots[0])
        except Exception as exc:
            self._is_running = False
            self._slot_states = {}
            raise RuntimeError(
                f"Failed to bind keys. Try running as Administrator. Error: {exc}"
            )

    def unbind_trigger_handlers(self) -> None:
        if not self.is_running:
            return
        
        self._is_running = False
        
        # Stop all active slots
        with self._lock:
            for trigger_key in list(self._slot_states.keys()):
                self._slot_states[trigger_key] = False
        
        # Wait for threads to finish
        for thread in self._slot_threads.values():
            if thread.is_alive():
                thread.join(timeout=0.5)
        
        self._slot_threads.clear()
        self._slot_states.clear()
        keyboard.unhook_all()
        
        if self._slots:
            self._status_callback("Stopped", self._slots[0])

    def shutdown(self) -> None:
        self.unbind_trigger_handlers()

    def _on_trigger_press(self, e: keyboard.KeyboardEvent, slot: AutoFireSlot) -> None:
        # This check prevents the hotkey from re-triggering itself if not suppressed
        if e.name != slot.trigger_key.lower():
            return
        self._set_slot_active(slot, True)

    def _on_trigger_release(self, e: keyboard.KeyboardEvent, slot: AutoFireSlot) -> None:
        if e.name != slot.trigger_key.lower():
            return
        self._set_slot_active(slot, False)

    def _set_slot_active(self, slot: AutoFireSlot, active: bool) -> None:
        trigger_key = slot.trigger_key
        with self._lock:
            if self._slot_states.get(trigger_key) == active:
                return
            self._slot_states[trigger_key] = active

            if active and self._is_running:
                # Start the autofire loop for this slot in a new thread
                thread = threading.Thread(
                    target=self._autofire_loop, 
                    args=(slot,), 
                    daemon=True
                )
                self._slot_threads[trigger_key] = thread
                thread.start()
                
                # Update status to show active slots
                active_slots = [k.upper() for k, v in self._slot_states.items() if v]
                if active_slots:
                    status = f"Active: {', '.join(active_slots)}"
                    self._status_callback(status, slot)
            elif not active and self._is_running:
                # Remove thread reference when slot becomes inactive
                if trigger_key in self._slot_threads:
                    del self._slot_threads[trigger_key]
                
                # Check if any slots are still active
                active_slots = [k.upper() for k, v in self._slot_states.items() if v]
                if active_slots:
                    status = f"Active: {', '.join(active_slots)}"
                    self._status_callback(status, slot)
                else:
                    enabled_count = len(self._slots)
                    status = f"Running ({enabled_count} slot{'s' if enabled_count > 1 else ''})"
                    self._status_callback(status, self._slots[0])

    def _autofire_loop(self, slot: AutoFireSlot) -> None:
        """The main loop that sends keyboard events for a specific slot.
        
        Uses SendInput (AHK-like) by default for better game compatibility,
        or PostMessage for window-specific targeting.
        """
        trigger_key = slot.trigger_key
        
        # For PostMessage, we need a window handle
        hwnd = None
        if not slot.use_sendinput and slot.window_title:
            hwnd = ctypes.windll.user32.FindWindowW(None, slot.window_title)
            if not hwnd:
                logging.warning(f"Window '{slot.window_title}' not found.")
                with self._lock:
                    self._slot_states[trigger_key] = False
                self._status_callback(f"Error: Window '{slot.window_title}' not found", slot)
                return

        vk_code = VK_CODES.get(slot.output_key.lower())
        if not vk_code:
            with self._lock:
                self._slot_states[trigger_key] = False
            self._status_callback(f"Error: Key '{slot.output_key}' not supported", slot)
            return

        interval_sec = slot.interval_ms / 1000.0

        while True:
            with self._lock:
                if not self._slot_states.get(trigger_key, False) or not self._is_running:
                    break
            
            if slot.use_sendinput:
                # SendInput method (AHK-like) - works with DirectInput games
                send_key_with_sendinput(vk_code, key_up=False)
                time.sleep(0.02)  # Small delay between down and up
                send_key_with_sendinput(vk_code, key_up=True)
            else:
                # PostMessage method - window-specific targeting
                if hwnd:
                    ctypes.windll.user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, 0)
                    time.sleep(0.02)
                    ctypes.windll.user32.PostMessageW(hwnd, WM_KEYUP, vk_code, 0)
            
            time.sleep(interval_sec)

    def get_pending_error_status(self) -> Optional[tuple[str, AutoFireSlot]]:
        """Check if there's a pending error status from a background thread."""
        # No longer needed with new architecture, but kept for compatibility
        return None


def load_config() -> AutoFireConfig:
    if not CONFIG_PATH.exists():
        return AutoFireConfig()
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Could not load or parse config: {exc}")
        return AutoFireConfig()
    
    # Support legacy single-slot format
    if "trigger_key" in raw and "slots" not in raw:
        slot = AutoFireSlot(
            trigger_key=raw.get("trigger_key", "e"),
            output_key=raw.get("output_key", "r"),
            interval_ms=raw.get("interval_ms", 50),
            window_title=raw.get("window_title", ""),
            pass_through=raw.get("pass_through", False),
            use_sendinput=raw.get("use_sendinput", True),
            enabled=True,
        )
        language = raw.get("language", "en")
        return AutoFireConfig(slots=[slot], language=language)
    
    # New multi-slot format
    slots_data = raw.get("slots", [])
    slots = []
    for s in slots_data:
        slots.append(AutoFireSlot(
            trigger_key=s.get("trigger_key", "e"),
            output_key=s.get("output_key", "r"),
            interval_ms=s.get("interval_ms", 50),
            window_title=s.get("window_title", ""),
            pass_through=s.get("pass_through", False),
            use_sendinput=s.get("use_sendinput", True),
            enabled=s.get("enabled", True),
        ))
    
    if not slots:
        slots = [AutoFireSlot()]
    
    language = raw.get("language", "en")
    return AutoFireConfig(slots=slots, language=language)


def save_config(config: AutoFireConfig) -> None:
    payload = {
        "slots": [
            {
                "trigger_key": s.trigger_key,
                "output_key": s.output_key,
                "interval_ms": s.interval_ms,
                "window_title": s.window_title,
                "pass_through": s.pass_through,
                "use_sendinput": s.use_sendinput,
                "enabled": s.enabled,
            }
            for s in config.slots
        ],
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
        self._current_slot = self.engine.slot

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
        
        # Multi-slot management
        self.config = AutoFireConfig()
        self.current_slot_index = 0

        self._build_layout()
        config = load_config()
        self.config = config
        self.current_language = config.language
        self.populate_from_config(config)
        self._update_ui_language()
        self._update_slot_list()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        # --- Language Toggle Button (Top Right) ---
        lang_row = ttk.Frame(container)
        lang_row.pack(fill=tk.X, pady=(0, 5))
        self.lang_button = ttk.Button(lang_row, text="EN/繁", width=10, command=self.toggle_language)
        self.lang_button.pack(side=tk.RIGHT)
        
        # --- Quick Guide ---
        guide_frame = ttk.Frame(container, relief=tk.RIDGE, borderwidth=1)
        guide_frame.pack(fill=tk.X, pady=(0, 10), padx=2)
        guide_label = ttk.Label(
            guide_frame, 
            text="💡 Hold trigger key → Auto-fires output key repeatedly | Create multiple slots for different keys",
            font=("Segoe UI", 8),
            foreground="#0066cc",
            wraplength=450,
            justify=tk.LEFT,
            padding=5
        )
        guide_label.pack(fill=tk.X)
        self.ui_elements['guide_label'] = guide_label
        
        # --- Multi-Slot Management Section ---
        slot_frame = ttk.LabelFrame(container, text="Slots", padding=8)
        slot_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.ui_elements['slot_frame'] = slot_frame
        
        # Slot listbox with scrollbar
        list_frame = ttk.Frame(slot_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.slot_listbox = tk.Listbox(list_frame, height=5, yscrollcommand=scrollbar.set)
        self.slot_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.slot_listbox.bind('<<ListboxSelect>>', self._on_slot_select)
        scrollbar.config(command=self.slot_listbox.yview)
        
        # Slot management buttons
        slot_btn_frame = ttk.Frame(slot_frame)
        slot_btn_frame.pack(fill=tk.X)
        
        self.ui_elements['add_slot_btn'] = ttk.Button(slot_btn_frame, text="Add Slot", command=self._add_slot)
        self.ui_elements['add_slot_btn'].pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        self.ui_elements['remove_slot_btn'] = ttk.Button(slot_btn_frame, text="Remove Slot", command=self._remove_slot)
        self.ui_elements['remove_slot_btn'].pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        self.ui_elements['enabled_check'] = ttk.Checkbutton(slot_btn_frame, text="Enabled", command=self._toggle_slot_enabled)
        self.ui_elements['enabled_check'].pack(side=tk.LEFT, padx=5)

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
        
        # Update guide label
        self.ui_elements['guide_label'].config(text=t["guide"])
        
        # Update labels
        self.ui_elements['trigger_label'].config(text=t["trigger_key"])
        self.ui_elements['output_label'].config(text=t["output_key"])
        self.ui_elements['window_label'].config(text=t["target_window"])
        self.ui_elements['interval_label'].config(text=t["interval"])
        
        # Update slot frame
        self.ui_elements['slot_frame'].config(text=t["slots"])
        self.ui_elements['add_slot_btn'].config(text=t["add_slot"])
        self.ui_elements['remove_slot_btn'].config(text=t["remove_slot"])
        self.ui_elements['enabled_check'].config(text=t["slot_enabled"])
        
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
        self._update_status_display(status, self.engine.slot)
        
        # Update slot list display
        self._update_slot_list()
    
    def _update_slot_list(self) -> None:
        """Update the slot listbox with current slots."""
        if not hasattr(self, 'slot_listbox') or self.slot_listbox is None:
            return
            
        self.slot_listbox.delete(0, tk.END)
        for i, slot in enumerate(self.config.slots):
            status = "✓" if slot.enabled else "✗"
            display = f"{status} [{i+1}] {slot.trigger_key.upper()} → {slot.output_key.upper()} @{slot.interval_ms}ms"
            if slot.window_title:
                display += f" ({slot.window_title[:15]}...)" if len(slot.window_title) > 15 else f" ({slot.window_title})"
            self.slot_listbox.insert(tk.END, display)
        
        # Select current slot
        if 0 <= self.current_slot_index < len(self.config.slots):
            self.slot_listbox.selection_set(self.current_slot_index)
            
    def _on_slot_select(self, event) -> None:
        """Handle slot selection from listbox."""
        selection = self.slot_listbox.curselection()
        if not selection and event is not None:
            return
        
        old_index = self.current_slot_index
        
        # If called programmatically (event is None), use the manually set current_slot_index
        # Otherwise use the listbox selection
        if selection:
            new_index = selection[0]
        else:
            # When called with event=None, current_slot_index has been set already
            new_index = self.current_slot_index
        
        # Save current UI values to old slot before switching
        if 0 <= old_index < len(self.config.slots) and old_index != new_index:
            slot = self.config.slots[old_index]
            slot.trigger_key = self.trigger_var.get().strip().lower()
            slot.output_key = self.output_var.get().strip().lower()
            try:
                interval = max(MIN_INTERVAL_MS, min(MAX_INTERVAL_MS, self.interval_var.get()))
                slot.interval_ms = interval
            except (ValueError, tk.TclError):
                slot.interval_ms = 50
            slot.window_title = self.window_title_var.get().strip()
            slot.pass_through = self.pass_var.get()
            slot.use_sendinput = self.use_sendinput_var.get()
            
        self.current_slot_index = new_index
        
        # Load new slot data
        if 0 <= self.current_slot_index < len(self.config.slots):
            slot = self.config.slots[self.current_slot_index]
            self.trigger_var.set(slot.trigger_key)
            self.output_var.set(slot.output_key)
            self.interval_var.set(slot.interval_ms)
            self.window_title_var.set(slot.window_title)
            self.pass_var.set(slot.pass_through)
            self.use_sendinput_var.set(slot.use_sendinput)
            self.ui_elements['enabled_check'].state(['selected' if slot.enabled else '!selected'])
    
    def _save_current_slot_to_config(self) -> None:
        """Save current UI values to the current slot in config."""
        if 0 <= self.current_slot_index < len(self.config.slots):
            slot = self.config.slots[self.current_slot_index]
            slot.trigger_key = self.trigger_var.get().strip().lower()
            slot.output_key = self.output_var.get().strip().lower()
            try:
                interval = max(MIN_INTERVAL_MS, min(MAX_INTERVAL_MS, self.interval_var.get()))
                slot.interval_ms = interval
            except (ValueError, tk.TclError):
                slot.interval_ms = 50
            slot.window_title = self.window_title_var.get().strip()
            slot.pass_through = self.pass_var.get()
            slot.use_sendinput = self.use_sendinput_var.get()
            
    def _add_slot(self) -> None:
        """Add a new slot."""
        # Save current slot first
        self._save_current_slot_to_config()
        
        # Create new slot
        new_slot = AutoFireSlot()
        self.config.slots.append(new_slot)
        self.current_slot_index = len(self.config.slots) - 1
        
        # Update UI
        self._update_slot_list()
        self._on_slot_select(None)  # Load new slot
        save_config(self.config)
    
    def _remove_slot(self) -> None:
        """Remove the currently selected slot."""
        if len(self.config.slots) <= 1:
            messagebox.showwarning("AutoFire", "Cannot remove the last slot.", parent=self.root)
            return
            
        if 0 <= self.current_slot_index < len(self.config.slots):
            del self.config.slots[self.current_slot_index]
            
            # Adjust current index
            if self.current_slot_index >= len(self.config.slots):
                self.current_slot_index = len(self.config.slots) - 1
            
            # Update UI
            self._update_slot_list()
            if self.config.slots:
                self._on_slot_select(None)  # Load adjusted slot
            save_config(self.config)
    
    def _toggle_slot_enabled(self) -> None:
        """Toggle the enabled state of the current slot."""
        if 0 <= self.current_slot_index < len(self.config.slots):
            slot = self.config.slots[self.current_slot_index]
            slot.enabled = not slot.enabled
            self._update_slot_list()
            save_config(self.config)

    def refresh_window_list(self) -> None:
        """Refresh the list of available windows in the dropdown."""
        windows = get_all_window_titles()
        self.window_combo['values'] = windows
        if not windows:
            t = self.translations[self.current_language]
            self.window_combo['values'] = [t["no_windows"]]
    
    def populate_from_config(self, config: AutoFireConfig) -> None:
        # Load current slot
        slot = config.slots[self.current_slot_index] if config.slots else AutoFireSlot()
        self.trigger_var.set(slot.trigger_key)
        self.output_var.set(slot.output_key)
        self.interval_var.set(slot.interval_ms)
        self.pass_var.set(slot.pass_through)
        self.window_title_var.set(slot.window_title)
        self.use_sendinput_var.set(slot.use_sendinput)
        self.current_language = config.language
        
        # Update enabled checkbox
        if hasattr(self, 'ui_elements') and 'enabled_check' in self.ui_elements:
            self.ui_elements['enabled_check'].state(['selected' if slot.enabled else '!selected'])
        
        self.engine.apply_slot(slot)
        self._update_status_display("Stopped", slot)
        self._set_button_states(running=False)

    def start(self) -> None:
        self.root.mainloop()

    def on_close(self) -> None:
        self.stop_autofire()
        self.engine.shutdown()
        self.root.destroy()

    def start_autofire(self) -> None:
        # Save current slot to config
        self._save_current_slot_to_config()
        
        config = self._build_config_from_inputs()
        if config is None:
            return

        # Apply ALL enabled slots to engine
        enabled_slots = [s for s in config.slots if s.enabled]
        if not enabled_slots:
            messagebox.showwarning("AutoFire", "No enabled slots. Please enable at least one slot.", parent=self.root)
            return
            
        self.engine.apply_slots(enabled_slots)
        self.config = config
        save_config(config)

        try:
            self.engine.bind_trigger_handlers()
        except RuntimeError as exc:
            messagebox.showerror("AutoFire Error", str(exc), parent=self.root)
            return

        t = self.translations[self.current_language]
        enabled_count = len(enabled_slots)
        status = f"{t['running']} ({enabled_count} slot{'s' if enabled_count > 1 else ''})"
        self._update_status_display(status, enabled_slots[0])
        self._set_button_states(running=True)

    def stop_autofire(self) -> None:
        self.engine.unbind_trigger_handlers()
        t = self.translations[self.current_language]
        self._update_status_display(t["stopped"], self.engine.slot)
        self._set_button_states(running=False)

    def _build_config_from_inputs(self) -> Optional[AutoFireConfig]:
        trigger = self.trigger_var.get().strip().lower()
        output = self.output_var.get().strip().lower()
        window_title = self.window_title_var.get().strip()

        if not all([trigger, output]):
            messagebox.showerror("AutoFire", "Trigger and Output keys must be filled.", parent=self.root)
            return None
        
        try:
            interval = int(self.interval_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("AutoFire", "Interval must be an integer.", parent=self.root)
            return None
        
        # Update current slot in config
        if 0 <= self.current_slot_index < len(self.config.slots):
            slot = self.config.slots[self.current_slot_index]
            slot.trigger_key = trigger
            slot.output_key = output
            slot.interval_ms = max(MIN_INTERVAL_MS, min(interval, MAX_INTERVAL_MS))
            slot.window_title = window_title
            slot.pass_through = bool(self.pass_var.get())
            slot.use_sendinput = bool(self.use_sendinput_var.get())
        
        self.config.language = self.current_language
        return self.config

    def _schedule_status_update(self, state: str, slot: AutoFireSlot) -> None:
        self.root.after(0, self._update_status_display, state, slot)

    def _immediate_status_update(self, state: str, slot: AutoFireSlot) -> None:
        """A thread-safe method for immediate status updates from errors in background threads."""
        # Directly set the internal Tkinter variable value without using .set()
        # This bypasses the Tk event loop and avoids blocking from background threads
        self.status_var._value = f"{slot.formatted()} [{state}]"

    def _update_status_display(self, state: str, slot: AutoFireSlot) -> None:
        self.status_var.set(f"{slot.formatted()} [{state}]")

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
