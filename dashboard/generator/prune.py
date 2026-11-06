"""Remove everything that depends on a disabled optional feature (see settings.FEATURE_ENTITIES).

Rules, applied bottom-up:
- a dict whose own strings (entity, templates, JS) reference a disabled entity is removed;
- a conditional whose AND-ed conditions lose one is removed (an OR keeps its other branches);
- a card, card list or element list that becomes empty is removed, and so is a section with only headings.
"""
from __future__ import annotations

import settings

_DROP = object()
_CONTAINERS = ("cards", "elements", "series", "entities", "sections", "views")


def _bad(text: str, prefixes: tuple[str, ...]) -> bool:
    return any(m.group(0).startswith(prefixes) for m in settings.ENTITY_RE.finditer(text))


def _prune(o, prefixes):
    if isinstance(o, list):
        out = [x for x in (_prune(v, prefixes) for v in o) if x is not _DROP]
        return out
    if isinstance(o, str):
        return _DROP if _bad(o, prefixes) else o
    if not isinstance(o, dict):
        return o
    # own strings first (entity ids, markdown templates, JS series)
    for k, v in o.items():
        if isinstance(v, str) and _bad(v, prefixes):
            return _DROP
    out = {}
    for k, v in o.items():
        if k == "conditions" and isinstance(v, list):
            kept = [x for x in (_prune(c, prefixes) for c in v) if x is not _DROP]
            if o.get("condition") == "or":
                if not kept:
                    return _DROP
            elif len(kept) != len(v):
                return _DROP  # AND (explicit or implicit): a missing part changes the meaning
            out[k] = kept
            continue
        nv = _prune(v, prefixes)
        if nv is _DROP:
            if k in ("card",):
                return _DROP
            continue
        if k in _CONTAINERS and isinstance(v, list) and v and not nv:
            return _DROP
        out[k] = nv
    if o.get("type") == "grid" and all(c.get("type") == "heading" for c in out.get("cards", [])):
        return _DROP
    return out


def prune(config: dict) -> dict:
    prefixes = settings.disabled_prefixes()
    if not prefixes:
        return config
    result = _prune(config, prefixes)
    return {"title": config.get("title"), "views": []} if result is _DROP else result
