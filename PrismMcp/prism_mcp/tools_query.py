"""Read-only tools: entities, scene files, products, versions, media, dependencies."""

import datetime
import os

from unity_bridge.commands import PrismCommands
from unity_bridge.protocol import BridgeError

from . import entities
from .entities import ENTITY_SCHEMA, page
from .registry import tool

APPS = {".ma": "Maya", ".mb": "Maya", ".blend": "Blender", ".unity": "Unity", ".hip": "Houdini", ".hiplc": "Houdini"}
LIMIT = {"type": "integer", "default": 200, "description": "Maximum number of items; truncated=true when there were more."}


def _schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required)}


def _mtime_iso(path):
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds")
    except OSError:
        return ""


# --- helpers shared with reports.py ---------------------------------------------------


def all_entities(core, kind="asset", include_omitted=False):
    """[(entity, omitted)] for every asset or every shot of the active project."""
    if kind == "asset":
        every = core.entities.getAssets(includeOmitted=True) or []
        visible = core.entities.getAssets(includeOmitted=False) or []
    else:
        every = core.entities.getShots(includeOmitted=True) or []
        visible = core.entities.getShots(includeOmitted=False) or []
    shown = {entities.label(entities.from_prism(e)) for e in visible}
    out = []
    for e in every:
        clean = entities.from_prism(e)
        omitted = entities.label(clean) not in shown
        if include_omitted or not omitted:
            out.append((clean, omitted))
    return out


def departments(core, entity):
    return [{"name": step, "tasks": list(core.entities.getCategories(entity, step) or [])}
            for step in (core.entities.getSteps(entity) or [])]


def scenefiles(core, entity, department=None, task=None):
    out = []
    for path in core.entities.getScenefiles(entity=entity, step=department, category=task) or []:
        data = core.getScenefileData(path) or {}
        ext = os.path.splitext(path)[1].lower()
        out.append({
            "path": path.replace("\\", "/"),
            "entity": entity,
            "department": data.get("department") or department or "",
            "task": data.get("task") or task or "",
            "version": data.get("version") or "",
            "comment": data.get("comment") or "",
            "user": data.get("user") or data.get("username") or "",
            "date": data.get("date") or _mtime_iso(path),
            "app": APPS.get(ext, ext.lstrip(".")),
        })
    return out


def versions(core, entity, product):
    items = PrismCommands(core, unity=None).listVersions(entity, product)
    master = next((v["contentVersion"] for v in items if v["version"] == "master"), None)
    for v in items:
        v["isMaster"] = v["version"] == "master" or (master is not None and v["version"] == master)
    return items


def products(core, entity):
    return PrismCommands(core, unity=None).listProducts(entity)


# --- tools ----------------------------------------------------------------------------


@tool("list_entities",
      "List the project's assets (type=asset, default) or shots (type=shot). path: asset folder prefix like 'Props'; "
      "contains: text the asset path or sequence/shot contains. Omitted (hidden) entities only with includeOmitted.",
      _schema({"type": {"type": "string", "enum": ["asset", "shot"], "default": "asset"}, "path": {"type": "string"},
               "contains": {"type": "string"}, "includeOmitted": {"type": "boolean", "default": False}, "limit": LIMIT}))
def list_entities(ctx, type="asset", path="", contains="", includeOmitted=False, limit=200):
    if type not in ("asset", "shot"):
        raise BridgeError("bad_args", "type must be asset or shot.")
    core = ctx.require_project()
    prefix = (path or "").replace("\\", "/").strip("/").casefold()
    needle = (contains or "").casefold()
    items = []
    for entity, omitted in ctx.run(lambda c: all_entities(c, type, includeOmitted)):
        text = entities.label(entity).casefold()
        if prefix and not (text == prefix or text.startswith(prefix + "/")):
            continue
        if needle and needle not in text:
            continue
        items.append({"entity": entity, "omitted": omitted})
    return page(items, limit)


@tool("get_entity",
      "Everything about one asset or shot: description, metadata, preview image path, frame range (shots), omitted, "
      "and its departments with their tasks.",
      _schema({"entity": ENTITY_SCHEMA}, ["entity"]))
def get_entity(ctx, entity):
    entity = entities.require(ctx, entity)

    def read(core):
        e = core.entities
        preview = e.getEntityPreviewPath(entity)
        result = {
            "entity": entity,
            "omitted": bool(e.isEntityOmitted(entity)),
            "description": e.getAssetDescription(e.getAssetNameFromPath(entity["asset_path"])) if entity["type"] == "asset" else None,
            "metaData": e.getMetaData(entity) or {},
            "previewPath": preview.replace("\\", "/") if preview and os.path.isfile(preview) else None,
            "departments": departments(core, entity),
        }
        if entity["type"] == "shot":
            result["frameRange"] = e.getShotRange(entity)
        return result

    return ctx.run(read)


@tool("list_scenefiles",
      "Scene files (Maya, Blender, Unity...) of an entity, optionally of one department/task: version, comment, user, date, app, path.",
      _schema({"entity": ENTITY_SCHEMA, "department": {"type": "string"}, "task": {"type": "string"}, "limit": LIMIT}, ["entity"]))
def list_scenefiles(ctx, entity, department=None, task=None, limit=200):
    entity = entities.require(ctx, entity)
    return page(ctx.run(lambda c: scenefiles(c, entity, department, task)), limit)


@tool("list_products", "The products (exports such as models) of an entity.",
      _schema({"entity": ENTITY_SCHEMA, "limit": LIMIT}, ["entity"]))
def list_products(ctx, entity, limit=200):
    entity = entities.require(ctx, entity)
    return page(ctx.run(lambda c: products(c, entity)), limit)


@tool("list_versions",
      "Versions of a product: version, comment, user, date, file, location. isMaster marks the master entry and the version it copies.",
      _schema({"entity": ENTITY_SCHEMA, "product": {"type": "string"}, "limit": LIMIT}, ["entity", "product"]))
def list_versions(ctx, entity, product, limit=200):
    entity = entities.require(ctx, entity)
    return page(ctx.run(lambda c: versions(c, entity, product)), limit)


@tool("list_media", "Playblasts, renders and other media of an entity, with their versions.",
      _schema({"entity": ENTITY_SCHEMA, "limit": LIMIT}, ["entity"]))
def list_media(ctx, entity, limit=200):
    entity = entities.require(ctx, entity)

    def read(core):
        out = []
        for kind, identifiers in (core.mediaProducts.getIdentifiersByType(entity) or {}).items():
            for identifier in identifiers or []:
                vs = core.mediaProducts.getVersionsFromIdentifier(identifier) or []
                out.append({"kind": kind, "identifier": identifier.get("identifier"), "versions": [{
                    "version": v.get("version"),
                    "comment": v.get("comment") or "",
                    "user": v.get("user") or v.get("username") or "",
                    "date": v.get("date") or "",
                    "path": (v.get("path") or "").replace("\\", "/"),
                } for v in vs]})
        return out

    return page(ctx.run(read), limit)


@tool("get_dependencies", "The product files a scene file uses, as Prism recorded them when the scene was saved.",
      _schema({"scenefile": {"type": "string"}}, ["scenefile"]))
def get_dependencies(ctx, scenefile):
    ctx.require_project()
    if not os.path.isfile(scenefile or ""):
        raise BridgeError("source_unavailable", "Scene file not found: %s" % scenefile, {"path": scenefile})
    deps = ctx.run(lambda c: c.entities.getDependencies(os.path.normpath(scenefile))) or []
    return {"scenefile": scenefile.replace("\\", "/"), "dependencies": [d.replace("\\", "/") for d in deps]}
