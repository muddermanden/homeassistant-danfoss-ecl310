"""Settings shared by the generator modules, loaded from config.local.yaml (or config.example.yaml).

build.py calls load() before importing the other modules, because they read their switches at import time.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

CONFIG: dict = {}
BASE: Path = Path(".")

# Entities each optional feature adds. With the feature off, every card, element, condition or series that
# references one of these is left out of the dashboard.
FEATURE_ENTITIES = {
    "heat_meter": ("sensor.heat_meter_", "binary_sensor.heat_meter_", "sensor.radiator_loop_return_estimated",
                   "sensor.return_limit_deviation", "sensor.pipe_scale_"),
    "circulation_pump": ("sensor.circulation_pump_", "binary_sensor.circulation_pump_", "button.circulation_pump_"),
    "rooms": ("sensor.heated_rooms_", "sensor.coldest_heated_room", "sensor.warmest_heated_room"),
}
ENTITY_RE = re.compile(r"\b(?:sensor|binary_sensor|button|weather|media_player|device_tracker)\.[a-z0-9_]+")


def load(path: str | Path) -> dict:
    global BASE
    path = Path(path).resolve()
    BASE = path.parent
    CONFIG.clear()
    CONFIG.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return CONFIG


def get(key: str, default=None):
    """Dotted lookup, e.g. get('variant.direct_heating', False)."""
    node = CONFIG
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return default if node is None else node


def path(key: str, default: str) -> Path:
    """A path from the config, relative to the config file."""
    return (BASE / get(key, default)).resolve()


def feature(name: str) -> bool:
    return bool(get(f"features.{name}", False))


def disabled_prefixes() -> tuple[str, ...]:
    out: list[str] = []
    for name, prefixes in FEATURE_ENTITIES.items():
        if not feature(name):
            out.extend(prefixes)
    if not get("weather"):
        out.append("weather.")
    return tuple(out)


def enabled(entity: str) -> bool:
    return not entity.startswith(disabled_prefixes())


def rename(text: str) -> str:
    """Map the generator's generic entity ids to your own (config 'entities': exact ids, then prefixes)."""
    exact = get("entities.exact", {}) or {}
    prefixes = sorted((get("entities.prefixes", {}) or {}).items(), key=lambda kv: -len(kv[0]))

    def one(match: re.Match) -> str:
        e = match.group(0)
        if e in exact:
            return exact[e]
        for old, new in prefixes:
            if e.startswith(old):
                return new + e[len(old):]
        return e

    return ENTITY_RE.sub(one, text)
