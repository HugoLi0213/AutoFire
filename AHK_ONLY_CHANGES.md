# AutoFire - AHK-Only Mode

## What Changed

Removed all Python keyboard injection code. AutoFire now uses **AutoHotkey v2 exclusively** for better game compatibility.

## Before vs After

### Before (Dual Mode)
- Python keyboard hooks (required admin, limited game support)
- AutoHotkey mode (better compatibility)
- Mode selection UI
- Keyboard capture buttons

### After (AHK-Only)
- ✅ **AutoHotkey v2 only** - superior game compatibility
- ✅ **Simpler UI** - no mode selection needed
- ✅ **Auto-generated scripts** - `autofire.ahk` created from UI settings
- ✅ **Cleaner code** - removed `keyboard` library dependency from engine
- ✅ **No admin required** - AHK doesn't need elevation for most cases

## Removed Components

- Python keyboard library imports
- `keyboard` module dependency from core engine
- Mode selection radio buttons
- Keyboard capture functionality
- `use_ahk` configuration field
- Python-specific methods: `_emit_output()`, `_send_scancode_key()`, `_run_loop()`, etc.

## What Remains

- ✅ **Tkinter UI** - simple configuration interface
- ✅ **AutoHotkey integration** - generates and manages `.ahk` scripts
- ✅ **Config persistence** - saves to `autofire.json`
- ✅ **Emergency stop** - `Ctrl+Alt+Esc` hotkey
- ✅ **Test suite** - pytest tests still work

## Requirements

**Before**: Python 3.x + `keyboard` library + optional AutoHotkey v2
**After**: Python 3.x + **AutoHotkey v2 (required)**

## Usage

1. Install [AutoHotkey v2](https://www.autohotkey.com/)
2. Run `python app.py`
3. Configure keys and interval
4. Click **Start** - UI generates `autofire.ahk` and launches it
5. Hold trigger key to spam output
6. Click **Stop** or press `Ctrl+Alt+Esc`

## File Changes

### Modified
- `autofire_ui.py` - removed Python keyboard code, simplified to AHK-only
- `README.md` - updated to reflect AHK-only approach
- `autofire.json` - removed `useAhk` field

### Unchanged
- `autofire.ahk` - generated script (auto-created by UI)
- `app.py` - entry point
- `tests/` - test suite (still uses mocked keyboard for unit tests)

## Benefits

1. **Better game support** - AHK works where Python injection fails
2. **Simpler codebase** - removed 500+ lines of keyboard hook code
3. **No admin required** - AHK doesn't need elevation for most scenarios
4. **Cleaner UI** - removed mode selection and capture buttons
5. **Easier to understand** - single execution path instead of dual modes
