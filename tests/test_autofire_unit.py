"""QA regression tests for the AutoFire "While Held" behaviour."""
from __future__ import annotations

import math
import time

from core.bindings_autofire import AutoFireBindingRegistry, AutoFireBindingRunner
from core.types import AutoFireBinding


def _wait_until(condition, timeout: float = 0.5) -> None:
    start = time.time()
    while not condition():
        if time.time() - start > timeout:
            raise TimeoutError("Condition not satisfied in time")
        time.sleep(0.001)


def _release_after(fake_clock, fake_keyboard_backend, key: str, threshold_ms: int) -> None:
    def listener(current_time: float) -> None:
        if int(current_time * 1000) >= threshold_ms:
            fake_keyboard_backend.simulate_keyup(key)
            fake_clock.unregister_listener(listener)

    fake_clock.register_listener(listener)


def test_whileheld_interval_accuracy(fake_keyboard_backend, fake_clock):
    runner = AutoFireBindingRunner(
        trigger_key="e",
        output_key="r",
        interval_ms=10,
        pass_through_trigger=False,
        now=fake_clock.now,
        sleep=fake_clock.sleep,
        keyboard_module=fake_keyboard_backend,
    )
    fake_keyboard_backend.simulate_keydown("e")
    _release_after(fake_clock, fake_keyboard_backend, "e", 100)

    runner.start()
    _wait_until(lambda: not runner.running, timeout=1.0)

    runner.stop()

    pulses = [key for key in fake_keyboard_backend.press_history if key == "r"]
    expected = 10
    tolerance = max(1, math.ceil(expected * 0.05))
    assert expected - tolerance <= len(pulses) <= expected + tolerance
    assert fake_keyboard_backend.block_calls.count("e") == 1
    assert fake_keyboard_backend.unblock_calls.count("e") == 1


def test_stop_on_release_fast(fake_keyboard_backend, fake_clock):
    runner = AutoFireBindingRunner(
        trigger_key="e",
        output_key="r",
        interval_ms=15,
        pass_through_trigger=False,
        now=fake_clock.now,
        sleep=fake_clock.sleep,
        keyboard_module=fake_keyboard_backend,
    )

    fake_keyboard_backend.simulate_keydown("e")
    _release_after(fake_clock, fake_keyboard_backend, "e", 30)

    runner.start()
    fake_clock.advance_ms(100)
    _wait_until(lambda: not runner.running, timeout=1.0)
    runner.stop()
    before = len(fake_keyboard_backend.press_history)
    fake_clock.advance_ms(20)
    after = len(fake_keyboard_backend.press_history)
    assert before == after


def test_pass_through_on(fake_keyboard_backend, fake_clock):
    runner = AutoFireBindingRunner(
        trigger_key="e",
        output_key="r",
        interval_ms=20,
        pass_through_trigger=True,
        now=fake_clock.now,
        sleep=fake_clock.sleep,
        keyboard_module=fake_keyboard_backend,
    )

    fake_keyboard_backend.simulate_keydown("e")
    _release_after(fake_clock, fake_keyboard_backend, "e", 60)

    runner.start()
    fake_clock.advance_ms(30)
    fake_clock.advance_ms(60)
    _wait_until(lambda: not runner.running, timeout=1.0)
    runner.stop()

    assert fake_keyboard_backend.block_calls == []
    assert fake_keyboard_backend.unblock_calls == []
    pulses = [key for key in fake_keyboard_backend.press_history if key == "r"]
    assert len(pulses) > 0


def test_teardown_unhooks(fake_keyboard_backend, fake_clock):
    status_messages: list[str] = []
    registry = AutoFireBindingRegistry(
        keyboard_module=fake_keyboard_backend,
        now=fake_clock.now,
        sleep=fake_clock.sleep,
        status_callback=status_messages.append,
        register_emergency=True,
    )

    binding = AutoFireBinding(
        id="binding-1",
        trigger_key="e",
        output_key="r",
        interval_ms=12,
        pass_through_trigger=False,
        mode="whileHeld",
    )

    registry.register(binding)
    assert fake_keyboard_backend._press_hooks

    handle = registry._handles[binding.trigger_key]

    fake_keyboard_backend.simulate_keydown("e")
    _release_after(fake_clock, fake_keyboard_backend, "e", 40)
    fake_clock.advance_ms(40)
    _wait_until(lambda: not handle.runner.running, timeout=1.0)

    registry.clear()

    assert handle.runner._thread is None
    assert not handle.runner.running
    assert not fake_keyboard_backend._press_hooks
    assert not fake_keyboard_backend._release_hooks
    assert registry._handles == {}
    assert registry._emergency_hotkey_id is None
    assert not fake_keyboard_backend._handlers
