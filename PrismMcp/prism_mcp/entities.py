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


def _name(entity, key, what):
    """A single folder name: no separators, never . or .. (they would walk out of the entity folders)."""
    value = _text(entity.get(key))
    if not value:
        raise BridgeError("bad_args", "A %s entity needs %s." % (what, key))
    if value in (".", "..") or "/" in value or "\\" in value:
        raise BridgeError("bad_args", "%s %r is not a valid name." % (key, value))
    return value


def validate(entity, allowed=("asset", "shot")):
    """A clean copy of entity; bad_args if its shape is wrong or its type is not allowed."""
    if not isinstance(entity, dict):
        raise BridgeError("bad_args", "entity must be an object like %s" % ENTITY_SCHEMA["description"])
    kind = entity.get("type")
    if kind not in allowed:
        raise BridgeError("bad_args", "entity type must be one of %s, not %r" % (", ".join(allowed), kind))
    clean = {"type": kind}
    if kind == "asset":
        raw = entity.get("asset_path") if isinstance(entity.get("asset_path"), str) else ""
        path = raw.replace("\\", "/").strip("/")
        if not path.strip():
            raise BridgeError("bad_args", "An asset entity needs asset_path, e.g. Props/Lotus.")
        if any(not part.strip() or part != part.strip() or part in (".", "..") for part in path.split("/")):
            raise BridgeError("bad_args", "asset_path %r has an empty, '.' or '..' folder name, or a name with leading/trailing spaces." % raw)
        clean["asset_path"] = path
    elif kind == "shot":
        for key in ("sequence", "shot"):
            clean[key] = _name(entity, key, "shot")
    elif kind == "sequence":
        clean["sequence"] = _name(entity, "sequence", "sequence")
    elif kind == "episode":
        _name(entity, "episode", "episode")
    if _text(entity.get("episode")):
        clean["episode"] = _name(entity, "episode", "episode")
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
    """The entity's folder exists; for assets it must also be an asset to Prism, not a category folder like Props."""
    entity_path = path(ctx, entity)
    if not entity_path or not os.path.isdir(entity_path):
        return False
    if entity.get("type") == "asset":
        return ctx.core.entities.getTypeFromAssetPath(entity_path) == "asset"
    return True


def is_category(ctx, entity):
    """An asset_path that is an existing folder Prism does not see as an asset (a category such as Props)."""
    entity_path = path(ctx, entity)
    return entity.get("type") == "asset" and bool(entity_path) and os.path.isdir(entity_path) and not exists(ctx, entity)


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
