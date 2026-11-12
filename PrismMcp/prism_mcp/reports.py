"""Project-wide reports, and the scene files that depend on an entity."""

import collections
import datetime
import fnmatch
import os

from unity_bridge.protocol import BridgeError

from . import entities
from .entities import page
from .registry import tool
from .tools_query import LIMIT, all_entities, departments, products, scenefiles, versions

KINDS = ("recent_activity", "missing_products", "master_behind", "empty_tasks")


def _every_entity(core, include_omitted=False):
    return [e for e, _ in all_entities(core, "asset", include_omitted)] + [e for e, _ in all_entities(core, "shot", include_omitted)]


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _iso(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def _since(value):
    if not value:
        return datetime.datetime.combine(datetime.date.today() - datetime.timedelta(days=7), datetime.time())
    try:
        return datetime.datetime.combine(datetime.date.fromisoformat(value), datetime.time())
    except (TypeError, ValueError):
        raise BridgeError("bad_args", "since must be a date like 2026-11-05, not %r." % value)


def _latest(items):
    real = [v["version"] for v in items if v["version"] != "master"]
    return max(real) if real else None


def recent_activity(core, since):
    cutoff = since.timestamp()
    found = []
    for entity in _every_entity(core):
        for s in scenefiles(core, entity):
            t = _mtime(s["path"])
            if t is not None and t >= cutoff:
                found.append((t, {"kind": "scenefile", "entity": entity, "name": "%s/%s" % (s["department"], s["task"]),
                                  "version": s["version"], "user": s["user"], "comment": s["comment"], "path": s["path"]}))
        for p in products(core, entity):
            for v in versions(core, entity, p["product"]):
                if v["version"] == "master" or not v.get("filepath"):
                    continue
                folder = os.path.dirname(v["filepath"])
                t = _mtime(folder)
                if t is not None and t >= cutoff:
                    found.append((t, {"kind": "product", "entity": entity, "name": p["product"], "version": v["version"],
                                      "user": v["user"], "comment": v["comment"], "path": folder.replace("\\", "/")}))
        for kind, identifiers in (core.mediaProducts.getIdentifiersByType(entity) or {}).items():
            for identifier in identifiers or []:
                for v in core.mediaProducts.getVersionsFromIdentifier(identifier) or []:
                    t = _mtime(v.get("path") or "")
                    if t is not None and t >= cutoff:
                        found.append((t, {"kind": "media", "entity": entity, "name": "%s/%s" % (kind, identifier.get("identifier")),
                                          "version": v.get("version"), "user": v.get("user") or v.get("username") or "",
                                          "comment": v.get("comment") or "", "path": (v.get("path") or "").replace("\\", "/")}))
    found.sort(key=lambda pair: pair[0], reverse=True)
    items = []
    for t, item in found:
        item["date"] = _iso(t)
        items.append(item)
    return items, dict(collections.Counter(i["user"] or "?" for i in items))


def missing_products(core, pattern, category):
    prefix = (category or "").replace("\\", "/").strip("/").casefold()
    items = []
    for entity, _ in all_entities(core, "asset"):
        path = entity["asset_path"].casefold()
        if prefix and not (path == prefix or path.startswith(prefix + "/")):
            continue
        names = [p["product"] for p in products(core, entity)]
        if not any(fnmatch.fnmatch(n, pattern or "*") for n in names):
            items.append({"entity": entity, "products": names})
    return items


def master_behind(core):
    items = []
    for entity in _every_entity(core):
        for p in products(core, entity):
            vs = versions(core, entity, p["product"])
            latest = _latest(vs)
            master = next((v["contentVersion"] for v in vs if v["version"] == "master"), None)
            if latest and master != latest:
                items.append({"entity": entity, "product": p["product"], "latest": latest, "master": master})
    return items


def empty_tasks(core):
    items = []
    for entity in _every_entity(core):
        for dep in departments(core, entity):
            for task in dep["tasks"]:
                if not scenefiles(core, entity, dep["name"], task):
                    items.append({"entity": entity, "department": dep["name"], "task": task})
    return items


def _under(path, root):
    norm = os.path.normcase(os.path.normpath(path))
    base = os.path.normcase(os.path.normpath(root))
    return norm == base or norm.startswith(base + os.sep)


def find_dependents(ctx, entity_root):
    """Scene files outside entity_root that use files under it (scene files inside move or go with it)."""

    def scan(core):
        out = []
        for entity in _every_entity(core, include_omitted=True):
            for s in scenefiles(core, entity):
                if _under(s["path"], entity_root):
                    continue
                deps = core.entities.getDependencies(os.path.normpath(s["path"])) or []
                if any(_under(d, entity_root) for d in deps):
                    out.append({"entity": entity, "scenefile": s["path"], "version": s["version"], "user": s["user"]})
        return out

    return ctx.run(scan)


@tool("report",
      "Project reports. kind: recent_activity (scene files, product versions and media saved since `since`, "
      "default the last 7 days, newest first, with counts per user); missing_products (assets, optionally under "
      "`category`, with no product matching the `product` pattern, e.g. *_model); master_behind (products whose "
      "master is missing or not the latest version); empty_tasks (tasks with no scene file yet).",
      {"type": "object", "properties": {
          "kind": {"type": "string", "enum": list(KINDS)},
          "since": {"type": "string", "description": "YYYY-MM-DD (recent_activity)"},
          "product": {"type": "string", "default": "*", "description": "product name pattern (missing_products)"},
          "category": {"type": "string", "description": "asset folder prefix (missing_products)"},
          "limit": LIMIT}, "required": ["kind"]})
def report(ctx, kind, since=None, product="*", category="", limit=200):
    if kind not in KINDS:
        raise BridgeError("bad_args", "kind must be one of %s." % ", ".join(KINDS))
    ctx.require_project()
    if kind == "recent_activity":
        cutoff = _since(since)
        items, by_user = ctx.run(lambda c: recent_activity(c, cutoff))
        result = page(items, limit)
        result["since"] = cutoff.date().isoformat()
        result["byUser"] = by_user
        return result
    if kind == "missing_products":
        return page(ctx.run(lambda c: missing_products(c, product, category)), limit)
    if kind == "master_behind":
        return page(ctx.run(master_behind), limit)
    return page(ctx.run(empty_tasks), limit)
