"""Version management: master versions, comments, omitting entities. Every change is confirmed first."""

import os

from unity_bridge.protocol import BridgeError

from . import confirm as confirmation
from . import entities
from .entities import ENTITY_SCHEMA
from .registry import CONFIRM_SENTENCE, tool
from .tools_query import versions

CONFIRM = {"type": "string", "description": "confirmToken from the needs_confirmation answer, after the user said yes"}


def _schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required)}


# --- lookups --------------------------------------------------------------------------


def _product_versions(core, entity, product):
    """[(raw Prism version dict, described version)] in Prism's order."""
    raw = core.products.getVersionsFromProduct(entity, product) or []
    if not raw:
        raise BridgeError("bad_args", "%s has no product %r." % (entities.label(entity), product))
    return list(zip(raw, versions(core, entity, product)))


def _pick(pairs, version, what):
    for raw, described in pairs:
        if described["version"] == version and version != "master":
            return raw, described
    names = [d["version"] for _, d in pairs if d["version"] != "master"]
    raise BridgeError("bad_args", "%s has no version %r. Versions: %s" % (what, version, ", ".join(names)))


def _product_master(pairs):
    return next(((raw, d) for raw, d in pairs if d["version"] == "master"), (None, None))


def _media(core, entity, identifier, kind=None):
    """(identifier dict, [raw versions]) of one media identifier of entity."""
    found = []
    for k, identifiers in (core.mediaProducts.getIdentifiersByType(entity) or {}).items():
        for ident in identifiers or []:
            if ident.get("identifier") == identifier and kind in (None, k):
                found.append(ident)
    if not found:
        raise BridgeError("bad_args", "%s has no media %r%s." % (entities.label(entity), identifier, " of kind %s" % kind if kind else ""))
    if len(found) > 1:
        raise BridgeError("bad_args", "%s has more than one media called %r; give kind too." % (entities.label(entity), identifier))
    return found[0], core.mediaProducts.getVersionsFromIdentifier(found[0]) or []


def _media_master(core, vs):
    master = next((v for v in vs if v.get("version") == "master"), None)
    if master is None:
        return None
    return core.mediaProducts.getMasterVersionNumber(master.get("path")) or "master"


def _one_of(product, identifier):
    if bool(product) == bool(identifier):
        raise BridgeError("bad_args", "Give exactly one of product (exports such as models) or identifier (media such as playblasts).")


# --- tools ----------------------------------------------------------------------------


@tool("set_master",
      "Make a version the master of a product (product=...) or of a media identifier (identifier=..., optional kind). "
      "Always asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"entity": ENTITY_SCHEMA, "product": {"type": "string"}, "identifier": {"type": "string"}, "kind": {"type": "string"},
               "version": {"type": "string"}, "confirm": CONFIRM}, ["entity", "version"]),
      mutating=True)
def set_master(ctx, entity, version, product=None, identifier=None, kind=None, confirm=None):
    entity = entities.require(ctx, entity)
    _one_of(product, identifier)
    args = {"entity": entity, "product": product, "identifier": identifier, "kind": kind, "version": version, "confirm": confirm}
    core = ctx.core
    if product:
        pairs = ctx.run(lambda c: _product_versions(c, entity, product))
        raw, described = _pick(pairs, version, "%s/%s" % (entities.label(entity), product))
        current = (_product_master(pairs)[1] or {}).get("contentVersion")
        name = product
    else:
        ident, vs = ctx.run(lambda c: _media(c, entity, identifier, kind))
        raw = next((v for v in vs if v.get("version") == version and version != "master"), None)
        if raw is None:
            raise BridgeError("bad_args", "%s/%s has no version %r. Versions: %s" % (
                entities.label(entity), identifier, version, ", ".join(v.get("version") for v in vs if v.get("version") != "master")))
        current = ctx.run(lambda c: _media_master(c, vs))
        name = identifier
    if current == version:
        return {"changed": False, "master": version}
    confirmation.require(ctx, "set_master", args,
                         "%s/%s master: %s → %s" % (entities.label(entity), name, current or "none", version),
                         {"from": current, "to": version}, current)
    if product:
        result = ctx.run(lambda c: c.products.updateMasterVersion(described["filepath"] or raw.get("path")))
    else:
        result = ctx.run(lambda c: c.mediaProducts.updateMasterVersion(context=dict(raw), isFilepath=False))
    if not result:
        raise BridgeError("internal", "Prism could not update the master of %s/%s." % (entities.label(entity), name))
    return {"changed": True, "master": version}


@tool("delete_master",
      "Remove the master version of a product. The versions themselves stay. Always asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"entity": ENTITY_SCHEMA, "product": {"type": "string"}, "confirm": CONFIRM}, ["entity", "product"]),
      mutating=True)
def delete_master(ctx, entity, product, confirm=None):
    entity = entities.require(ctx, entity)
    pairs = ctx.run(lambda c: _product_versions(c, entity, product))
    raw, described = _product_master(pairs)
    if raw is None:
        return {"changed": False}
    content = described.get("contentVersion")
    confirmation.require(ctx, "delete_master", {"entity": entity, "product": product, "confirm": confirm},
                         "The master of %s/%s (a copy of %s) is deleted; %s itself stays." % (entities.label(entity), product, content, content),
                         {"master": content}, content)
    path = described.get("filepath") or raw.get("path")
    try:
        removed = ctx.run(lambda c: c.products.deleteMasterVersion(path))
    except BridgeError as e:
        if e.code != "needs_input":
            raise
        raise BridgeError("internal", "Prism could not delete the master (a file may be open in another program): %s" % e.message)
    if not removed:
        raise BridgeError("internal", "Prism could not delete the master of %s/%s (a file may be open in another program)." % (
            entities.label(entity), product))
    return {"changed": True}


def _comment_target(ctx, target):
    """(label, current comment, setter(core, comment)) for a product version, media version or scene file."""
    if not isinstance(target, dict):
        raise BridgeError("bad_args", "target must be an object.")
    if target.get("scenefile"):
        path = target["scenefile"]
        ctx.require_project()
        if not os.path.isfile(path):
            raise BridgeError("source_unavailable", "Scene file not found: %s" % path, {"path": path})
        path = os.path.normpath(path)
        current = ctx.run(lambda c: (c.getScenefileData(path) or {}).get("comment") or "")
        return os.path.basename(path), current, lambda c, comment: c.entities.setComment(path, comment)
    if not target.get("version") or bool(target.get("product")) == bool(target.get("identifier")):
        raise BridgeError("bad_args", "target is {entity, product, version}, {entity, identifier, version} or {scenefile}.")
    entity = entities.require(ctx, target.get("entity"))
    if target.get("product"):
        pairs = ctx.run(lambda c: _product_versions(c, entity, target["product"]))
        raw, described = _pick(pairs, target["version"], "%s/%s" % (entities.label(entity), target["product"]))
        return ("%s/%s %s" % (entities.label(entity), target["product"], target["version"]), described.get("comment") or "",
                lambda c, comment: c.products.setComment(raw["path"], comment))
    _, vs = ctx.run(lambda c: _media(c, entity, target["identifier"], target.get("kind")))
    raw = next((v for v in vs if v.get("version") == target["version"]), None)
    if raw is None:
        raise BridgeError("bad_args", "%s/%s has no version %r." % (entities.label(entity), target["identifier"], target["version"]))
    return ("%s/%s %s" % (entities.label(entity), target["identifier"], target["version"]), raw.get("comment") or "",
            lambda c, comment: c.mediaProducts.setComment(raw["path"], comment))


@tool("set_comment",
      "Set the comment of a product version {entity, product, version}, a media version {entity, identifier, version} "
      "or a scene file {scenefile}. Replacing an existing comment asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"target": {"type": "object"}, "comment": {"type": "string"}, "confirm": CONFIRM}, ["target", "comment"]),
      mutating=True)
def set_comment(ctx, target, comment, confirm=None):
    label, current, setter = _comment_target(ctx, target)
    if current == comment:
        return {"changed": False}
    if current:
        confirmation.require(ctx, "set_comment", {"target": target, "comment": comment, "confirm": confirm},
                             "The comment of %s changes." % label, {"from": current, "to": comment}, current)
    ctx.run(lambda c: setter(c, comment))
    return {"changed": True}


def _omit(ctx, tool_name, entity, omit, confirm):
    entity = entities.require(ctx, entity)
    if bool(ctx.run(lambda c: c.entities.isEntityOmitted(entity))) == omit:
        return {"changed": False}
    confirmation.require(ctx, tool_name, {"entity": entity, "confirm": confirm},
                         ("%s is hidden in Prism (its files stay)." if omit else "%s is shown in Prism again.") % entities.label(entity),
                         {"entity": entity, "omitted": omit}, not omit)
    ctx.run(lambda c: c.entities.omitEntity(entity, omit=omit))
    return {"changed": True}


@tool("omit", "Hide an asset or shot in Prism (omit). Files are not touched. Asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"entity": ENTITY_SCHEMA, "confirm": CONFIRM}, ["entity"]), mutating=True)
def omit(ctx, entity, confirm=None):
    return _omit(ctx, "omit", entity, True, confirm)


@tool("unomit", "Show an omitted asset or shot in Prism again. Asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"entity": ENTITY_SCHEMA, "confirm": CONFIRM}, ["entity"]), mutating=True)
def unomit(ctx, entity, confirm=None):
    return _omit(ctx, "unomit", entity, False, confirm)
