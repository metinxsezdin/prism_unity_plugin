"""Entity dicts in Prism's own shape, checked before they reach Prism."""

import os

from unity_bridge.protocol import BridgeError

ENTITY_SCHEMA = {
    "type": "object",
    "description": 'Prism entity: {"type":"asset","asset_path":"Props/Lotus"} or {"type":"shot","sequence":"sq01","shot":"sh010"}',
    "properties": {
        "type": {"type": "string", "enum": ["asset", "shot", "sequence", "episode"]},
        "asset_path": {"type": "string"},
        "sequence": {"type": "string"},
        "shot": {"type": "string"},
        "episode": {"type": "string"},
    },
    "required": ["type"],
}


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def validate(entity, allowed=("asset", "shot")):
    """A clean copy of entity; bad_args if its shape is wrong or its type is not allowed."""
    if not isinstance(entity, dict):
        raise BridgeError("bad_args", "entity must be an object like %s" % ENTITY_SCHEMA["description"])
    kind = entity.get("type")
    if kind not in allowed:
        raise BridgeError("bad_args", "entity type must be one of %s, not %r" % (", ".join(allowed), kind))
    clean = {"type": kind}
    if kind == "asset":
        path = _text(entity.get("asset_path")).replace("\\", "/").strip("/")
        if not path:
            raise BridgeError("bad_args", "An asset entity needs asset_path, e.g. Props/Lotus.")
        clean["asset_path"] = path
    elif kind == "shot":
        for key in ("sequence", "shot"):
            if not _text(entity.get(key)):
                raise BridgeError("bad_args", "A shot entity needs sequence and shot.")
            clean[key] = _text(entity.get(key))
    elif kind == "sequence":
        if not _text(entity.get("sequence")):
            raise BridgeError("bad_args", "A sequence entity needs sequence.")
        clean["sequence"] = _text(entity.get("sequence"))
    elif kind == "episode":
        if not _text(entity.get("episode")):
            raise BridgeError("bad_args", "An episode entity needs episode.")
    if _text(entity.get("episode")):
        clean["episode"] = _text(entity.get("episode"))
    return clean


def label(entity):
    kind = entity.get("type")
    if kind == "asset":
        return entity.get("asset_path", "")
    if kind == "shot":
        return "%s/%s" % (entity.get("sequence"), entity.get("shot"))
    if kind == "sequence":
        return entity.get("sequence", "")
    return entity.get("episode", "")


def path(ctx, entity):
    return ctx.core.getEntityPath(entity=entity)


def exists(ctx, entity):
    entity_path = path(ctx, entity)
    return bool(entity_path) and os.path.isdir(entity_path)


def require(ctx, entity, allowed=("asset", "shot")):
    """validate() plus: the project is reachable and the entity exists in it."""
    clean = validate(entity, allowed)
    ctx.require_project()
    if not exists(ctx, clean):
        raise BridgeError("bad_args", "The project has no %s %s." % (clean["type"], label(clean)))
    return clean


def from_prism(entity):
    """Prism's entity dicts carry extra keys and backslashes; keep the shape the tools use."""
    if entity.get("type") == "asset":
        return {"type": "asset", "asset_path": (entity.get("asset_path") or "").replace("\\", "/")}
    clean = {"type": "shot", "sequence": entity.get("sequence"), "shot": entity.get("shot")}
    if entity.get("episode"):
        clean["episode"] = entity["episode"]
    return clean


def page(items, limit):
    limit = max(int(limit or 0), 1)
    return {"items": items[:limit], "truncated": len(items) > limit}
