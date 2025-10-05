"""Persistence helpers for profiles and macros."""
from __future__ import annotations

import json
from pathlib import Path
from .types import AppState


class StorageError(RuntimeError):
    pass


def load_state(path: Path) -> AppState:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - depends on filesystem
        raise StorageError(str(exc)) from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StorageError(f"Invalid JSON: {exc}") from exc
    try:
        return AppState.from_dict(payload)
    except ValueError as exc:
        raise StorageError(str(exc)) from exc


def save_state(path: Path, state: AppState) -> None:
    payload = state.to_dict()
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        raise StorageError(str(exc)) from exc