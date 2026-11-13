"""Tools that add to the project: entities, departments, tasks; descriptions, metadata, previews, frame ranges."""

import os

from unity_bridge.protocol import BridgeError

from . import confirm as confirmation
from . import entities
from .entities import ENTITY_SCHEMA
from .registry import CONFIRM_SENTENCE, tool

BAD_CHARS = set('<>:"/\\|?*')


def _schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required)}


CONFIRM = {"type": "string", "description": "confirmToken from the needs_confirmation answer, after the user said yes"}


def _check_name(name, what):
    if not isinstance(name, str) or not name.strip() or name != name.strip() or BAD_CHARS & set(name) or name.endswith("."):
        raise BridgeError("bad_args", "%r is not a valid %s name (no empty names, leading/trailing spaces or any of < > : \" / \\ | ? *)." % (name, what))


def _departments(core, kind):
    return list((core.projects.getAssetDepartments() if kind == "asset" else core.projects.getShotDepartments()) or [])


def _department(core, entity, department):
    """The folder (abbreviation) of a department given by name or abbreviation."""
    wanted = (department or "").casefold()
    for d in _departments(core, entity["type"]):
        if wanted in (d["name"].casefold(), d["abbreviation"].casefold()):
            return d["abbreviation"]
    raise BridgeError("bad_args", "%r is not a %s department of this project. Departments: %s" % (
        department, entity["type"], ", ".join("%s (%s)" % (d["name"], d["abbreviation"]) for d in _departments(core, entity["type"]))))


def _presets(core, kind):
    return list((core.projects.getAssetTaskPresets() if kind == "asset" else core.projects.getShotTaskPresets()) or [])


def _preset(core, kind, name):
    presets = _presets(core, kind)
    for p in presets:
        if p.get("name") == name:
            return p
    raise BridgeError("bad_args", "No %s task preset called %r. Presets: %s" % (kind, name, ", ".join(p.get("name", "?") for p in presets) or "none"))


def _tasks(core, entity):
    return {(dep, task) for dep in (core.entities.getSteps(entity) or []) for task in (core.entities.getCategories(entity, dep) or [])}


def _frame_range(value):
    if value is None:
        return None
    if not (isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, int) for v in value) and value[0] <= value[1]):
        raise BridgeError("bad_args", "frameRange must be [start, end] with whole numbers and start <= end.")
    return [value[0], value[1]]


@tool("create_entity",
      "Create an asset (folders in asset_path are created as needed) or a shot. Optional description (assets), "
      "frameRange [start, end] (shots) and taskPreset (a Prism task preset, see list_task_presets). "
      "If it exists already nothing changes and created=false.",
      _schema({"entity": ENTITY_SCHEMA, "description": {"type": "string"}, "frameRange": {"type": "array", "items": {"type": "integer"}},
               "taskPreset": {"type": "string"}}, ["entity"]),
      mutating=True)
def create_entity(ctx, entity, description=None, frameRange=None, taskPreset=None):
    entity = entities.validate(entity)
    core = ctx.require_project()
    if entity["type"] == "asset":
        for part in entity["asset_path"].split("/"):
            _check_name(part, "asset folder")
        if not core.entities.isValidAssetName(core.entities.getAssetNameFromPath(entity["asset_path"])):
            raise BridgeError("bad_args", "%r is a name Prism reserves for its own folders." % entity["asset_path"].split("/")[-1])
        if frameRange is not None:
            raise BridgeError("bad_args", "frameRange is for shots.")
    else:
        _check_name(entity["sequence"], "sequence")
        _check_name(entity["shot"], "shot")
        if description is not None:
            raise BridgeError("bad_args", "Prism keeps descriptions for assets only.")
    frame_range = _frame_range(frameRange)
    preset = _preset(core, entity["type"], taskPreset) if taskPreset else None

    if entities.is_category(ctx, entity):
        raise BridgeError("bad_args", "%s is a category folder that holds assets, not an asset." % entity["asset_path"])
    if entities.exists(ctx, entity):
        answer = {"created": False, "entity": entity, "omitted": bool(ctx.run(lambda c: c.entities.isEntityOmitted(entity)))}
        given = (("description", description, "set_description"), ("frameRange", frameRange, "set_shot_range"),
                 ("taskPreset", taskPreset, "apply_task_preset"))
        ignored = [(name, other) for name, value, other in given if value is not None]
        if ignored:
            answer["ignored"] = [name for name, _ in ignored]
            answer["note"] = "%s exists already and was not changed. To change it use %s." % (
                entities.label(entity), ", ".join(other for _, other in ignored))
        return answer

    def create(c):
        result = c.entities.createEntity(entity, frameRange=frame_range, silent=True, description=description)
        if not result or result.get("error"):
            raise BridgeError("internal", "Prism could not create %s: %s" % (entities.label(entity), (result or {}).get("error") or "no reason given"))
        if preset:
            c.entities.createTasksFromPreset(entity, preset=preset)

    ctx.run(create)
    return {"created": True, "entity": entity, "omitted": False}


@tool("create_department",
      "Add a department (by name, e.g. Modeling, or abbreviation, e.g. mod) to an asset or shot. "
      "Prism's default tasks for that department are created too unless defaultTasks=false.",
      _schema({"entity": ENTITY_SCHEMA, "department": {"type": "string"}, "defaultTasks": {"type": "boolean", "default": True}},
              ["entity", "department"]),
      mutating=True)
def create_department(ctx, entity, department, defaultTasks=True):
    entity = entities.require(ctx, entity)
    abbr = _department(ctx.core, entity, department)
    if os.path.isdir(ctx.core.getEntityPath(entity=entity, step=abbr)):
        return {"created": False, "entity": entity, "department": abbr, "tasks": []}

    def create(c):
        before = _tasks(c, entity)
        c.entities.createDepartment(abbr, entity, createCat=bool(defaultTasks))  # returns None when there are no default tasks
        if not os.path.isdir(c.getEntityPath(entity=entity, step=abbr)):
            raise BridgeError("internal", "Prism could not create the department %s." % abbr)
        return sorted(task for dep, task in _tasks(c, entity) - before if dep == abbr)

    tasks = ctx.run(create)
    return {"created": True, "entity": entity, "department": abbr, "tasks": tasks}


@tool("create_task",
      "Add a task to a department of an asset or shot. The department must exist (create_department).",
      _schema({"entity": ENTITY_SCHEMA, "department": {"type": "string"}, "task": {"type": "string"}}, ["entity", "department", "task"]),
      mutating=True)
def create_task(ctx, entity, department, task):
    entity = entities.require(ctx, entity)
    abbr = _department(ctx.core, entity, department)
    _check_name(task, "task")
    if not os.path.isdir(ctx.core.getEntityPath(entity=entity, step=abbr)):
        raise BridgeError("needs_input", "%s has no %s department yet; create it first (create_department)." % (entities.label(entity), abbr),
                          {"missing": ["department"], "department": abbr})
    if os.path.isdir(ctx.core.getEntityPath(entity=entity, step=abbr, category=task)):
        return {"created": False, "entity": entity, "department": abbr, "task": task}
    if not ctx.run(lambda c: c.entities.createCategory(entity, abbr, task)):
        raise BridgeError("internal", "Prism could not create the task %s/%s." % (abbr, task))
    return {"created": True, "entity": entity, "department": abbr, "task": task}


@tool("list_task_presets", "The project's task presets for assets (type=asset) or shots: their departments and tasks.",
      _schema({"type": {"type": "string", "enum": ["asset", "shot"], "default": "asset"}}))
def list_task_presets(ctx, type="asset"):
    if type not in ("asset", "shot"):
        raise BridgeError("bad_args", "type must be asset or shot.")
    core = ctx.require_project()
    return [{"name": p.get("name"), "departments": p.get("departments", [])} for p in _presets(core, type)]


@tool("apply_task_preset",
      "Create the departments and tasks of a task preset on an asset or shot. dryRun=true only lists them.",
      _schema({"entity": ENTITY_SCHEMA, "preset": {"type": "string"}, "dryRun": {"type": "boolean", "default": False}}, ["entity", "preset"]),
      mutating=True)
def apply_task_preset(ctx, entity, preset, dryRun=False):
    entity = entities.require(ctx, entity)
    p = _preset(ctx.core, entity["type"], preset)
    departments = [{"name": d["name"], "tasks": list(d.get("tasks", []))} for d in p.get("departments", [])]
    if dryRun:
        return {"departments": departments, "created": []}

    def apply(c):
        before = _tasks(c, entity)
        c.entities.createTasksFromPreset(entity, preset=p)
        return [{"department": dep, "task": task} for dep, task in sorted(_tasks(c, entity) - before)]

    return {"departments": departments, "created": ctx.run(apply)}


@tool("set_description",
      "Set an asset's description. Replacing an existing description asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"entity": ENTITY_SCHEMA, "description": {"type": "string"}, "confirm": CONFIRM}, ["entity", "description"]),
      mutating=True)
def set_description(ctx, entity, description, confirm=None):
    entity = entities.require(ctx, entity)
    if entity["type"] != "asset":
        raise BridgeError("bad_args", "Prism keeps descriptions for assets only.")
    name = ctx.core.entities.getAssetNameFromPath(entity["asset_path"])
    current = ctx.run(lambda c: c.entities.getAssetDescription(name)) or ""
    if current == description:
        return {"changed": False}
    if current:
        confirmation.require(ctx, "set_description", {"entity": entity, "description": description, "confirm": confirm},
                             "The description of %s changes." % entities.label(entity), {"from": current, "to": description}, current)
    ctx.run(lambda c: c.entities.setAssetDescription(name, description))
    return {"changed": True}


@tool("set_metadata",
      "Add or change metadata fields of an asset or shot: metaData is {field: value}. New fields are added directly; "
      "changing a field that has a value asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"entity": ENTITY_SCHEMA, "metaData": {"type": "object"}, "confirm": CONFIRM}, ["entity", "metaData"]),
      mutating=True)
def set_metadata(ctx, entity, metaData, confirm=None):
    entity = entities.require(ctx, entity)
    if not isinstance(metaData, dict) or not metaData:
        raise BridgeError("bad_args", "metaData must be a non-empty object like {\"polycount\": \"12k\"}.")
    existing = ctx.run(lambda c: c.entities.getMetaData(entity)) or {}
    values = {k: v if isinstance(v, str) else str(v) for k, v in metaData.items()}
    changes = {k: {"from": existing[k].get("value"), "to": v} for k, v in values.items()
               if k in existing and existing[k].get("value") not in (None, "") and existing[k].get("value") != v}
    if changes:
        confirmation.require(ctx, "set_metadata", {"entity": entity, "metaData": metaData, "confirm": confirm},
                             "%d metadata field(s) of %s change." % (len(changes), entities.label(entity)), changes,
                             {k: existing[k].get("value") for k in changes})
    merged = {k: dict(v) for k, v in existing.items()}
    for k, v in values.items():
        merged[k] = {"value": v, "show": existing.get(k, {}).get("show", True)}
    if merged == existing:
        return {"changed": False, "metaData": existing}
    ctx.run(lambda c: c.entities.setMetaData(entity, merged))
    return {"changed": True, "metaData": merged}


def _load_image(path):
    """A QPixmap of path; bad_args when it is not an image Qt can read."""
    if not path or not os.path.isfile(path):
        raise BridgeError("bad_args", "Image not found: %s" % path)
    from qtpy.QtGui import QImage, QPixmap

    image = QImage(path)
    if image.isNull():
        raise BridgeError("bad_args", "%s is not an image Prism can read (use .jpg or .png)." % path)
    return QPixmap.fromImage(image)


@tool("set_preview",
      "Set the preview picture of an asset or shot from a local image file (.jpg/.png). Replacing an existing preview "
      "asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"entity": ENTITY_SCHEMA, "imagePath": {"type": "string"}, "confirm": CONFIRM}, ["entity", "imagePath"]),
      mutating=True)
def set_preview(ctx, entity, imagePath, confirm=None):
    entity = entities.require(ctx, entity)
    if not imagePath or not os.path.isfile(imagePath):
        raise BridgeError("bad_args", "Image not found: %s" % imagePath)
    from qtpy.QtGui import QImage

    if QImage(imagePath).isNull():
        raise BridgeError("bad_args", "%s is not an image Prism can read (use .jpg or .png)." % imagePath)
    current = ctx.core.entities.getEntityPreviewPath(entity)
    if current and os.path.isfile(current):
        confirmation.require(ctx, "set_preview", {"entity": entity, "imagePath": imagePath, "confirm": confirm},
                             "The preview picture of %s is replaced." % entities.label(entity),
                             {"from": current.replace("\\", "/"), "to": imagePath.replace("\\", "/")}, os.path.getmtime(current))
    ctx.run(lambda c: c.entities.setEntityPreview(entity, _load_image(imagePath)))
    return {"changed": True}


@tool("set_shot_range",
      "Set a shot's frame range. Changing an existing range asks for confirmation. " + CONFIRM_SENTENCE,
      _schema({"entity": ENTITY_SCHEMA, "start": {"type": "integer"}, "end": {"type": "integer"}, "confirm": CONFIRM},
              ["entity", "start", "end"]),
      mutating=True)
def set_shot_range(ctx, entity, start, end, confirm=None):
    entity = entities.require(ctx, entity, allowed=("shot",))
    new = _frame_range([start, end])
    current = ctx.run(lambda c: c.entities.getShotRange(entity))
    current = list(current) if current else None
    if current == new:
        return {"changed": False}
    if current:
        confirmation.require(ctx, "set_shot_range", {"entity": entity, "start": start, "end": end, "confirm": confirm},
                             "The frame range of %s changes from %s-%s to %s-%s." % (entities.label(entity), current[0], current[1], new[0], new[1]),
                             {"from": current, "to": new}, current)
    ctx.run(lambda c: c.entities.setShotRange(entity, new[0], new[1]))
    return {"changed": True}
