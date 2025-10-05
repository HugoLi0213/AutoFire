# Test Suite Changes - AHK-Only Mode

## Deprecated Tests

`test_autofire_ui_tk.py.deprecated` - These tests validated Python keyboard hook behavior in the Tkinter UI. Since we removed Python keyboard injection and switched to AHK-only mode, these tests are no longer applicable.

### What was tested (no longer relevant):
- Python keyboard hook registration
- Trigger press/release with keyboard library
- Pass-through mode blocking via keyboard.block_key()
- Keyboard capture functionality
- Python-based timing loops

## Active Tests

### `test_autofire_runner.py` ✅
Tests the core AutoFire engine logic with mocked keyboard:
- Interval accuracy
- Pass-through behavior
- Emergency stop
- Config validation
- Teardown safety

**Status**: Still relevant - these test the business logic

### `test_autofire_refactor.py` ✅  
Additional runner tests with different configurations

**Status**: Still relevant

### `test_autofire_ui.py` ✅
Tests the original PySide6 macro studio UI (unrelated to AutoFire)

**Status**: Still relevant if maintaining macro studio

### `test_autofire_unit.py` ✅
Unit tests for core engine components

**Status**: Still relevant

## Future Testing

To test the new AHK-only UI, we would need tests that verify:
- AHK script generation from config
- Subprocess management (launching/terminating autofire.ahk)
- Config persistence
- UI state management

These would NOT require mocking `keyboard` library since we don't use it anymore.
