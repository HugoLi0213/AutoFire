"""Core data types and schema utilities for the macro application."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

SchemaVersion = int
SCHEMA_VERSION: SchemaVersion = 1


class EventKind(str, Enum):
    KEY = "key"
    MOUSE = "mouse"


class KeyAction(str, Enum):
    DOWN = "down"
    UP = "up"


class MouseAction(str, Enum):
    MOVE = "move"
    DOWN = "down"
    UP = "up"
    WHEEL = "wheel"


class DelayStrategy(str, Enum):
    ACTUAL = "actual"
    FIXED = "fixed"


class PlaybackMode(str, Enum):
    ONCE = "once"
    WHILE_HELD = "while_held"
    TOGGLE_LOOP = "toggle_loop"
    REPEAT_N = "repeat_n"


class BindingType(str, Enum):
    MACRO = "macro"
    SYSTEM = "system"
    TEXT = "text"
    PROGRAM = "program"
    AUTOFIRE = "autofire"


@dataclass(slots=True)
class BaseEvent:
    id: str
    kind: EventKind
    delay_ms: int
    timestamp_ns: int

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["type"] = self.__class__.__name__
        return payload


@dataclass(slots=True)
class KeyEvent(BaseEvent):
    key: str
    scan_code: Optional[int]
    action: KeyAction

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "KeyEvent":
        return KeyEvent(
            id=str(data.get("id")) or generate_id(),
            kind=EventKind.KEY,
            delay_ms=int(data.get("delay_ms", 0)),
            timestamp_ns=int(data.get("timestamp_ns", 0)),
            key=str(data.get("key", "")),
            scan_code=data.get("scan_code"),
            action=KeyAction(data.get("action", KeyAction.DOWN.value)),
        )


@dataclass(slots=True)
class MouseEvent(BaseEvent):
    action: MouseAction
    button: Optional[str]
    x: Optional[int]
    y: Optional[int]
    delta: Optional[int]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "MouseEvent":
        return MouseEvent(
            id=str(data.get("id")) or generate_id(),
            kind=EventKind.MOUSE,
            delay_ms=int(data.get("delay_ms", 0)),
            timestamp_ns=int(data.get("timestamp_ns", 0)),
            action=MouseAction(data.get("action", MouseAction.MOVE.value)),
            button=data.get("button"),
            x=data.get("x"),
            y=data.get("y"),
            delta=data.get("delta"),
        )


MacroEvent = Union[KeyEvent, MouseEvent]


def event_from_dict(data: Dict[str, Any]) -> MacroEvent:
    kind_value = data.get("kind") or data.get("type")
    if kind_value in (EventKind.KEY.value, "KeyEvent"):
        return KeyEvent.from_dict(data)
    if kind_value in (EventKind.MOUSE.value, "MouseEvent"):
        return MouseEvent.from_dict(data)
    raise ValueError(f"Unsupported event kind: {kind_value}")


@dataclass(slots=True)
class PlaybackOptions:
    mode: PlaybackMode = PlaybackMode.ONCE
    repeat_count: int = 1
    speed_multiplier: float = 1.0
    delay_strategy: DelayStrategy = DelayStrategy.ACTUAL
    fixed_delay_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "repeat_count": self.repeat_count,
            "speed_multiplier": self.speed_multiplier,
            "delay_strategy": self.delay_strategy.value,
            "fixed_delay_ms": self.fixed_delay_ms,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PlaybackOptions":
        return PlaybackOptions(
            mode=PlaybackMode(data.get("mode", PlaybackMode.ONCE.value)),
            repeat_count=int(data.get("repeat_count", 1)),
            speed_multiplier=float(data.get("speed_multiplier", 1.0)),
            delay_strategy=DelayStrategy(data.get("delay_strategy", DelayStrategy.ACTUAL.value)),
            fixed_delay_ms=data.get("fixed_delay_ms"),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.mode, PlaybackMode):
            try:
                self.mode = PlaybackMode(self.mode)
            except Exception:  # noqa: BLE001
                self.mode = PlaybackMode.ONCE
        if not isinstance(self.delay_strategy, DelayStrategy):
            try:
                self.delay_strategy = DelayStrategy(self.delay_strategy)
            except Exception:  # noqa: BLE001
                self.delay_strategy = DelayStrategy.ACTUAL


@dataclass(slots=True)
class Macro:
    id: str
    name: str
    events: List[MacroEvent] = field(default_factory=list)
    playback: PlaybackOptions = field(default_factory=PlaybackOptions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "events": [event.to_dict() for event in self.events],
            "playback": self.playback.to_dict(),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Macro":
        events = [event_from_dict(raw) for raw in data.get("events", [])]
        playback = PlaybackOptions.from_dict(data.get("playback", {}))
        return Macro(
            id=str(data.get("id")) or generate_id(),
            name=str(data.get("name", "Untitled Macro")),
            events=events,
            playback=playback,
        )


@dataclass(slots=True)
class Binding:
    id: str
    hotkey: str
    binding_type: BindingType
    target_id: Optional[str]
    payload: Optional[str]
    playback: PlaybackOptions
    suppress: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "hotkey": self.hotkey,
            "binding_type": self.binding_type.value,
            "target_id": self.target_id,
            "payload": self.payload,
            "playback": self.playback.to_dict(),
            "suppress": self.suppress,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Binding":
        return Binding(
            id=str(data.get("id")) or generate_id(),
            hotkey=str(data.get("hotkey", "")),
            binding_type=BindingType(data.get("binding_type", BindingType.MACRO.value)),
            target_id=data.get("target_id"),
            payload=data.get("payload"),
            playback=PlaybackOptions.from_dict(data.get("playback", {})),
            suppress=bool(data.get("suppress", True)),
        )


@dataclass(slots=True)
class AutoFireBinding:
    id: str
    trigger_key: str
    output_key: str
    interval_ms: int = 50
    pass_through_trigger: bool = False
    mode: str = "whileHeld"

    def __post_init__(self) -> None:
        self.trigger_key = str(self.trigger_key or "").lower()
        self.output_key = str(self.output_key or "").lower()
        if not self.trigger_key:
            raise ValueError("AutoFire binding requires a trigger key")
        if not self.output_key:
            raise ValueError("AutoFire binding requires an output key")
        self.interval_ms = max(1, int(self.interval_ms or 1))
        self.pass_through_trigger = bool(self.pass_through_trigger)
        if self.mode != "whileHeld":
            raise ValueError("AutoFire mode must be 'whileHeld'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": BindingType.AUTOFIRE.value,
            "trigger_key": self.trigger_key,
            "output_key": self.output_key,
            "interval_ms": self.interval_ms,
            "pass_through_trigger": self.pass_through_trigger,
            "mode": self.mode,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AutoFireBinding":
        return AutoFireBinding(
            id=str(data.get("id")) or generate_id(),
            trigger_key=str(data.get("trigger_key", "")),
            output_key=str(data.get("output_key", "")),
            interval_ms=int(data.get("interval_ms", 50)),
            pass_through_trigger=bool(data.get("pass_through_trigger", False)),
            mode=str(data.get("mode", "whileHeld")),
        )


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    macros: List[Macro] = field(default_factory=list)
    bindings: List[Binding] = field(default_factory=list)
    auto_fire_bindings: List["AutoFireBinding"] = field(default_factory=list)
    blocklist: List[str] = field(default_factory=lambda: ["f9", "f10"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "macros": [macro.to_dict() for macro in self.macros],
            "bindings": [binding.to_dict() for binding in self.bindings],
            "auto_fire_bindings": [binding.to_dict() for binding in self.auto_fire_bindings],
            "blocklist": self.blocklist,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Profile":
        return Profile(
            id=str(data.get("id")) or generate_id(),
            name=str(data.get("name", "Default Profile")),
            macros=[Macro.from_dict(m) for m in data.get("macros", [])],
            bindings=[Binding.from_dict(b) for b in data.get("bindings", [])],
            auto_fire_bindings=[AutoFireBinding.from_dict(b) for b in data.get("auto_fire_bindings", [])],
            blocklist=[str(x).lower() for x in data.get("blocklist", ["f9", "f10"])],
        )


@dataclass(slots=True)
class AppState:
    profiles: List[Profile]
    active_profile_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "profiles": [profile.to_dict() for profile in self.profiles],
            "active_profile_id": self.active_profile_id,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "AppState":
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema version {payload.get('schema_version')}, expected {SCHEMA_VERSION}"
            )
        profiles = [Profile.from_dict(p) for p in payload.get("profiles", [])]
        if not profiles:
            default_profile = Profile(id=generate_id(), name="Default Profile")
            profiles = [default_profile]
        active_profile_id = payload.get("active_profile_id") or profiles[0].id
        return AppState(profiles=profiles, active_profile_id=active_profile_id)


def generate_id() -> str:
    return uuid4().hex


def find_profile(state: AppState, profile_id: str) -> Profile:
    for profile in state.profiles:
        if profile.id == profile_id:
            return profile
    raise KeyError(f"Profile {profile_id} not found")