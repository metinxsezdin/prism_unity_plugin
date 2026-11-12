"""Renaming shots and sequences, and deleting shots into the project's Trash folder."""

import datetime
import os
import re

from unity_bridge.protocol import BridgeError

from . import confirm as confirmation
from . import entities
from .entities import ENTITY_SCHEMA
from .registry import CONFIRM_SENTENCE, tool
from .reports import find_dependents
from .tools_create import _check_name

CONFIRM = {"type": "string", "description": "confirmToken from the needs_confirmation answer, after the user said yes"}
UNITY_NOTE = "Unity imports are not in this list; Unity's Check for updates will show them as removed from Prism."


def _slash(path):
    return path.replace("\\", "/")


def _folders(core, entity):
    """[(location, folder)] of the entity that exist: the project folder, and the local copy when Prism uses local files."""
    glob = os.path.normpath(core.getEntityPath(entity=entity))
    out = [("global", glob)]
    local_root = getattr(core, "localProjectPath", "") if getattr(core, "useLocalFiles", False) else ""
    if local_root:
        root = os.path.normpath(core.projectPath)
        if os.path.normcase(glob).startswith(os.path.normcase(root) + os.sep):
            out.append(("local", os.path.join(os.path.normpath(local_root), glob[len(root) + 1:])))
    return [(loc, path) for loc, path in out if os.path.isdir(path)]


def _state(folders):
    return [[_slash(p), os.path.getmtime(p)] for _, p in folders]


def _dependents_summary(dependents):
    if not dependents:
        return "No other scene uses its products."
    return "%d scene(s) use its products; their links will break." % len(dependents)


def _check_unlocked(folders):
    """Every folder can be renamed (nothing inside is open), or nothing happens and the locked one is named."""
    for _, path in folders:
        probe = path + ".mcp-lockcheck"
        try:
            os.rename(path, probe)
        except OSError as e:
            raise BridgeError("internal", "%s is open in another program; nothing was changed. (%s)" % (_slash(path), e),
                              {"locked": _slash(path)})
        os.rename(probe, path)


def _renamed_names(folders, old, new):
    """What Prism's rename will do: it renames every file and folder below the entity whose name contains `old`.

    Returns [(old name, new name)]; bad_args when `old` appears inside a longer word in some name (shot 010 in
    version folder v0010), because Prism would rename that too.
    """
    token = re.compile(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(old))
    renames, partial = [], []
    for _, top in folders:
        names = [os.path.basename(top)]
        for root, dirs, files in os.walk(top):
            names.extend(dirs)
            names.extend(files)
        for name in names:
            if old not in name:
                continue
            if name.count(old) != len(token.findall(name)):
                partial.append(name)
            else:
                renames.append((name, name.replace(old, new)))
    if partial:
        raise BridgeError("bad_args", "Prism would also rename names that only contain %r inside a longer word, e.g. %s. "
                          "Pick a name that is not part of other names, or rename by hand in Prism." % (old, ", ".join(sorted(set(partial))[:5])),
                          {"partialMatches": sorted(set(partial))[:20]})
    return renames


def _target(entity, new_name):
    if entity["type"] == "shot":
        return dict(entity, shot=new_name)
    return {"type": "sequence", "sequence": new_name}


@tool("rename",
      "Rename a shot {type: shot, sequence, shot} or a sequence {type: sequence, sequence} to newName. Assets cannot be "
      "renamed (Prism does not support it). The confirmation lists the folders and the scenes that use the entity's "
      "products; their links break. Nothing is renamed while a file inside is open. " + CONFIRM_SENTENCE,
      {"type": "object", "properties": {"entity": ENTITY_SCHEMA, "newName": {"type": "string"}, "confirm": CONFIRM},
       "required": ["entity", "newName"]},
      mutating=True)
def rename(ctx, entity, newName, confirm=None):
    entity = entities.validate(entity, allowed=("shot", "sequence", "episode", "asset"))
    if entity["type"] == "asset":
        raise BridgeError("bad_args", "Prism cannot rename assets.")
    if entity["type"] == "episode":
        raise BridgeError("bad_args", "Renaming episodes is not supported.")
    entity = entities.require(ctx, entity, allowed=("shot", "sequence"))
    _check_name(newName, entity["type"])
    new = _target(entity, newName)
    if entities.exists(ctx, new):
        raise BridgeError("bad_args", "%s exists already." % entities.label(new))
    core = ctx.core
    folders = _folders(core, entity)
    old_token = entity["shot"] if entity["type"] == "shot" else entity["sequence"]
    renames = _renamed_names(folders, old_token, newName)
    dependents = find_dependents(ctx, folders[0][1])
    confirmation.require(
        ctx, "rename", {"entity": entity, "newName": newName, "confirm": confirm},
        "%s is renamed to %s. %s" % (entities.label(entity), entities.label(new), _dependents_summary(dependents)),
        {"from": entities.label(entity), "to": entities.label(new), "folders": [_slash(p) for _, p in folders],
         "renamedNames": len(renames), "sample": ["%s → %s" % pair for pair in renames[:10]],
         "dependents": dependents, "note": UNITY_NOTE},
        _state(folders))
    _check_unlocked(folders)

    def do_rename(c):
        if entity["type"] == "shot":
            c.entities.renameShot({"type": "shot", "sequence": entity["sequence"], "shot": entity["shot"]},
                                  {"type": "shot", "sequence": entity["sequence"], "shot": newName})
        else:
            c.entities.renameSequence(entity["sequence"], newName)

    try:
        ctx.run(do_rename)
    except Exception as e:
        message = e.message if isinstance(e, BridgeError) else str(e)
        new_folders = [os.path.normpath(p) for p in [core.getEntityPath(entity=new)]]
        if len(folders) > 1:
            root = os.path.normpath(core.projectPath)
            new_folders.append(os.path.join(os.path.normpath(core.localProjectPath), new_folders[0][len(root) + 1:]))
        raise BridgeError("internal", "The rename stopped halfway: %s" % message, {
            "renamed": [_slash(p) for p in new_folders if os.path.isdir(p)],
            "remaining": [_slash(p) for _, p in folders if os.path.isdir(p)],
        })
    return {"from": entity, "to": new}


@tool("delete_shot",
      "Delete a shot by moving its folders into the project's Trash folder (00_Pipeline/Trash); nothing is erased and "
      "the folders can be moved back by hand. The confirmation lists the scenes that use the shot's products; their links "
      "break. Nothing moves while a file inside is open. " + CONFIRM_SENTENCE,
      {"type": "object", "properties": {"entity": ENTITY_SCHEMA, "confirm": CONFIRM}, "required": ["entity"]},
      mutating=True)
def delete_shot(ctx, entity, confirm=None):
    entity = entities.validate(entity, allowed=("shot", "asset", "sequence"))
    if entity["type"] != "shot":
        raise BridgeError("bad_args", "delete_shot deletes shots only.")
    entity = entities.require(ctx, entity, allowed=("shot",))
    core = ctx.core
    folders = _folders(core, entity)
    dependents = find_dependents(ctx, folders[0][1])
    name_pattern = "<YYYYMMDD-HHMMSS>_%s-%s" % (entity["sequence"], entity["shot"])
    trash_root = os.path.join(os.path.normpath(core.projectPath), "00_Pipeline", "Trash")
    confirmation.require(
        ctx, "delete_shot", {"entity": entity, "confirm": confirm},
        "%s is moved to the project's Trash folder. %s" % (entities.label(entity), _dependents_summary(dependents)),
        {"folders": [_slash(p) for _, p in folders], "trash": _slash(os.path.join(trash_root, name_pattern)),
         "dependents": dependents, "note": UNITY_NOTE},
        _state(folders))

    name = "%s_%s-%s" % (datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), entity["sequence"], entity["shot"])
    moved = []
    for loc, src in folders:
        # Each location goes into its own project's Trash, so a move never crosses drives.
        root = trash_root if loc == "global" else os.path.join(os.path.normpath(core.localProjectPath), "00_Pipeline", "Trash")
        dst = os.path.join(root, name, loc)
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
        except OSError as e:
            for back_src, back_dst in reversed(moved):
                os.rename(back_dst, back_src)
            for _, d in moved + [(src, dst)]:
                parent = os.path.dirname(d)
                if os.path.isdir(parent) and not os.listdir(parent):
                    os.rmdir(parent)
            raise BridgeError("internal", "%s is open in another program; nothing was deleted. (%s)" % (_slash(src), e),
                              {"locked": _slash(src)})
        moved.append((src, dst))
    return {"deleted": entity, "trash": _slash(os.path.join(trash_root, name)), "folders": [_slash(d) for _, d in moved]}
