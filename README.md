# AutoFire Toolkit

Lightweight Windows automation utilities built around a deterministic auto-fire engine, a Tkinter UI, and a comprehensive pytest suite.

## AutoFire Core (`autofire.py`)

The core module exposes `AutoFireConfig` and `AutoFireApp` for managing while-held key presses with precise millisecond intervals.

- **Key features**: trigger/output mapping, optional pass-through, interval clamping, emergency stop, and configuration persistence.
- **Dependencies**: [`keyboard`](https://pypi.org/project/keyboard/) for global hooks. Administrator privileges are recommended when running outside of tests.

### Quick start

```cmd
python -m autofire
```

This launches the headless engine with default settings (`e -> r` every 50 ms). Adjust the generated `autofire.json` to change keys or timing.

## AutoFire UI (`autofire_ui.py`)

Tkinter front-end that wraps the core engine with a simple form for configuring trigger/output keys, interval, and pass-through behaviour.

- Start/Stop buttons map directly to engine lifecycle calls and reflect current status.
- Capture buttons temporarily hook the keyboard to record the next key press into the corresponding entry.
- Status bar always displays the active configuration in a human-readable format.

### Run the UI

```cmd
python -m autofire_ui
```

Use an elevated Command Prompt on Windows so keyboard hooks can be registered successfully.

## AutoFire Tests (`tests/`)

Pytest suite covering both the engine and Tk UI with deterministic fakes for keyboard hooks and clocks.

- `tests/test_autofire_runner.py`: exercises timing accuracy, pass-through behaviour, emergency stop, and teardown safety using `FakeKeyboard`/`FakeClock`.
- `tests/test_autofire_ui_tk.py`: drives the Tkinter UI through its widgets, validating capture buttons, button state transitions, interval validation, and cleanup.

### Run tests

```cmd
python -m pytest
```

All tests run headlessly; no real keyboard input is required because the suite patches the global `keyboard` module with the fakes from the runner tests.
