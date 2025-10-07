"""
Multi-Slot Simultaneous Usage Demo

This script demonstrates how multiple slots work simultaneously in AutoFire.

BEFORE THE FIX:
- Only ONE slot could be active at a time
- When you clicked START, only the currently selected slot would work
- You had to stop and restart to switch between different trigger keys

AFTER THE FIX:
- ALL enabled slots work simultaneously
- When you click START, ALL enabled slots are activated
- You can press different trigger keys and they will all fire their outputs independently
- Each slot runs in its own thread

Example Setup:
1. Slot 1: Q → W (50ms interval)
2. Slot 2: E → R (50ms interval)  
3. Slot 3: A → S (100ms interval)

When you click START:
- Press and hold Q: Outputs W repeatedly at 50ms intervals
- Press and hold E: Outputs R repeatedly at 50ms intervals
- Press and hold A: Outputs S repeatedly at 100ms intervals
- You can press Q and E together: Both W and R will fire simultaneously!

Architecture Changes:
1. Engine now stores multiple slots instead of a single slot
2. Engine binds keyboard handlers for ALL enabled slots
3. Each slot has its own active state tracking
4. Each slot runs in its own separate thread
5. Status display shows which slots are currently active

Benefits:
- More flexible configuration
- Can have different intervals for different keys
- Can target different windows with different slots
- Can mix SendInput and PostMessage methods
"""

print(__doc__)

# Example of how the engine tracks multiple slots internally:
example_slots = [
    {"trigger": "q", "output": "w", "interval": 50, "enabled": True},
    {"trigger": "e", "output": "r", "interval": 50, "enabled": True},
    {"trigger": "a", "output": "s", "interval": 100, "enabled": True},
    {"trigger": "z", "output": "x", "interval": 75, "enabled": False},  # Disabled
]

print("\n" + "="*60)
print("EXAMPLE CONFIGURATION:")
print("="*60)
for i, slot in enumerate(example_slots, 1):
    status = "✓ Enabled" if slot["enabled"] else "✗ Disabled"
    print(f"Slot {i}: {slot['trigger'].upper()} → {slot['output'].upper()} "
          f"@{slot['interval']}ms [{status}]")

enabled_count = sum(1 for s in example_slots if s["enabled"])
print(f"\nWhen you click START, {enabled_count} slots will be active simultaneously!")
print("\nPress CTRL+C to exit.")

try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nDemo ended.")
