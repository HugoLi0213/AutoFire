# AutoFire Architecture (AHK-Only)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │    app.py (entry)     │
                    │  python app.py        │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   autofire_ui.py      │
                    │   (Tkinter GUI)       │
                    │                       │
                    │  ┌─────────────────┐  │
                    │  │ AutoFireUI      │  │
                    │  │ - Trigger key   │  │
                    │  │ - Output key    │  │
                    │  │ - Interval (ms) │  │
                    │  │ - Pass-through  │  │
                    │  │ - Start/Stop    │  │
                    │  └────────┬────────┘  │
                    │           │           │
                    │  ┌────────▼────────┐  │
                    │  │ AutoFireEngine  │  │
                    │  │ - apply_config  │  │
                    │  │ - bind_trigger  │  │
                    │  │ - shutdown      │  │
                    │  └────────┬────────┘  │
                    └───────────┼───────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐
        │  _generate_ahk()  │   │   _start_ahk()    │
        │  Creates script   │   │  Launch process   │
        └─────────┬─────────┘   └─────────┬─────────┘
                  │                       │
                  ▼                       │
        ┌───────────────────┐             │
        │  autofire.ahk     │◄────────────┘
        │  (generated)      │
        │                   │
        │  TriggerKey: "`"  │
        │  OutputKey: "e"   │
        │  IntervalMs: 100  │
        │  PassThrough: no  │
        │                   │
        │  ┌─────────────┐  │
        │  │SetTimer loop│  │
        │  │Send output  │  │
        │  └─────────────┘  │
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │   GAME / APP      │
        │   Receives "e"    │
        │   every 100ms     │
        └───────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     CONFIGURATION FLOW                           │
└─────────────────────────────────────────────────────────────────┘

 User Input (UI)
      │
      ├──► save_config() ──► autofire.json
      │                           │
      └──► Click Start ───────────┼──► load_config()
                                  │
                                  ▼
                          _generate_ahk_script()
                                  │
                                  ▼
                          Write autofire.ahk
                                  │
                                  ▼
                          subprocess.Popen()
                                  │
                                  ▼
                          AHK Process Running
                                  │
                          ┌───────┴───────┐
                          │               │
                     Hold "`"        Release "`"
                          │               │
                    Send "e" 10/sec    Stop timer

┌─────────────────────────────────────────────────────────────────┐
│                        DATA STRUCTURES                           │
└─────────────────────────────────────────────────────────────────┘

AutoFireConfig
├── trigger_key: str     (e.g., "`")
├── output_key: str      (e.g., "e")
├── interval_ms: int     (e.g., 100)
└── pass_through: bool   (e.g., false)

AutoFireEngine
├── _config: AutoFireConfig
├── _status_callback: Callable
└── _ahk_process: Optional[Popen]

AutoFireUI
├── trigger_var: StringVar
├── output_var: StringVar
├── interval_var: IntVar
├── pass_var: BooleanVar
├── status_var: StringVar
└── engine: AutoFireEngine

┌─────────────────────────────────────────────────────────────────┐
│                       REMOVED COMPONENTS                         │
└─────────────────────────────────────────────────────────────────┘

❌ Python keyboard hooks (on_press_key, on_release_key)
❌ Threading (RLock, Event, worker thread, _run_loop)
❌ Time module (perf_counter, sleep)
❌ Keyboard blocking (block_key, unblock_key)
❌ Scancode SendInput (ctypes, KEYBDINPUT, INPUT)
❌ Emergency hotkey registration (keyboard.add_hotkey)
❌ Keyboard capture (keyboard.hook)
❌ Mode selection UI (Python vs AHK radio buttons)
❌ use_ahk config field

┌─────────────────────────────────────────────────────────────────┐
│                         TEST COVERAGE                            │
└─────────────────────────────────────────────────────────────────┘

test_autofire_refactor.py (7 tests)
├── Arbitrary keys and intervals
├── Pass-through toggle
├── Stop on release
├── Config validation
└── Hot reload

test_autofire_runner.py (9 tests)
├── While-held interval accuracy
├── Stop on release immediate
├── Pass-through blocking behavior
├── Parameter validation
├── Emergency stop
└── Teardown unhooks

test_autofire_ui.py (3 tests)
├── Editor and status feedback
├── Conflict dialog
└── Emergency stop

test_autofire_unit.py (4 tests)
├── While-held interval accuracy
├── Stop on release fast
├── Pass-through on
└── Teardown unhooks

Total: 23 tests, all passing ✅

┌─────────────────────────────────────────────────────────────────┐
│                         DEPENDENCIES                             │
└─────────────────────────────────────────────────────────────────┘

Before:
- Python 3.x
- keyboard library (Python)
- tkinter (Python)
- AutoHotkey v2 (optional)

After:
- Python 3.x
- tkinter (Python)
- AutoHotkey v2 (REQUIRED) ⭐

Reduction: Removed Python keyboard library dependency!
```
