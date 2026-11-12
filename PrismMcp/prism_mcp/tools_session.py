"""status, list_projects, set_project."""

import os

from unity_bridge.projects import pin_project
from unity_bridge.protocol import BridgeError

from . import SERVER_VERSION
from . import confirm as confirmation
from .registry import CONFIRM_SENTENCE, tool
from .session import TEAM_PRISM_VERSION


def _norm(path):
    return os.path.normcase(os.path.abspath(path)) if path else ""


def _user(core):
    user = core.users.getUser()
    if not user:
        raise BridgeError("needs_input", "No Prism user name is set. Open Prism once and enter your name.", {"missing": ["prismUser"]})
    return user


def version_warning(version):
    if version != TEAM_PRISM_VERSION:
        return "This machine has Prism %s; the team uses Prism %s. Tools may not behave as documented." % (version, TEAM_PRISM_VERSION)
    return None


@tool("status", "Prism version, Prism user, active project and server version. Call this first when something seems off.",
      {"type": "object", "properties": {}})
def status(ctx):
    core = ctx.core
    user = _user(core)
    result = {
        "prismVersion": core.version,
        "teamVersion": TEAM_PRISM_VERSION,
        "user": user,
        "userAbbreviation": core.users.getUserAbbreviation(user),
        "serverVersion": SERVER_VERSION,
        "project": ctx.project_info(),
    }
    warning = version_warning(core.version)
    if warning:
        result["warning"] = warning
    return result


def _recent(core):
    return [p for p in (core.projects.getRecentProjects(includeCurrent=True) or []) if p.get("configPath")]


@tool("list_projects", "The Prism projects this user opened recently, with whether each one's drive is reachable.",
      {"type": "object", "properties": {"limit": {"type": "integer", "default": 200}}})
def list_projects(ctx, limit=200):
    core = ctx.core
    items = []
    for p in _recent(core):
        items.append({
            "name": p.get("name") or "",
            "configPath": p["configPath"].replace("\\", "/"),
            "reachable": os.path.isfile(p["configPath"]),
            "current": _norm(p["configPath"]) == _norm(core.prismIni),
        })
    return {"items": items[:limit], "truncated": len(items) > limit}


def _resolve(core, name, configPath):
    if bool(name) == bool(configPath):
        raise BridgeError("bad_args", "Give exactly one of name or configPath.")
    if configPath:
        if os.path.isdir(configPath):
            configPath = os.path.join(configPath, "00_Pipeline", "pipeline.json")
        if not os.path.isfile(configPath):
            raise BridgeError("source_unavailable", "No Prism project config at %s (wrong path, or the drive is not connected)." % configPath,
                              {"path": configPath})
        return configPath
    recent = _recent(core)
    matches = [p for p in recent if (p.get("name") or "").casefold() == name.casefold()]
    if not matches:
        raise BridgeError("bad_args", "No recent Prism project is called %r. Recent projects: %s" % (
            name, ", ".join(sorted({p.get("name") or "?" for p in recent})) or "none"))
    if len({_norm(p["configPath"]) for p in matches}) > 1:
        raise BridgeError("needs_input", "More than one recent project is called %r; pick one by configPath." % name,
                          {"candidates": [p["configPath"] for p in matches]})
    config = matches[0]["configPath"]
    if not os.path.isfile(config):
        raise BridgeError("source_unavailable", "Project %r is not reachable at %s (is the drive connected?)." % (name, config),
                          {"path": config})
    return config


def _project_name(core, config):
    return core.getConfig("globals", "project_name", configPath=config) or os.path.basename(os.path.dirname(os.path.dirname(config)))


@tool("set_project",
      "Switch the Prism project Claude works in, by recent-project name or by pipeline.json/project folder path. "
      "Only this Claude session switches; the user's own Prism keeps its project. With persist=true the user's Prism "
      "selection changes too (asks for confirmation first). " + CONFIRM_SENTENCE,
      {"type": "object", "properties": {
          "name": {"type": "string"}, "configPath": {"type": "string"},
          "persist": {"type": "boolean", "default": False}, "confirm": {"type": "string"}}},
      mutating=True)
def set_project(ctx, name=None, configPath=None, persist=False, confirm=None):
    core = ctx.core
    target = _resolve(core, name, configPath)
    args = {"name": name, "configPath": configPath, "persist": persist, "confirm": confirm}
    if persist:
        current = core.getConfig("globals", "current project") or ""
        confirmation.require(ctx, "set_project", args,
                             "Prism's selected project for this user changes from %s to %s." % (
                                   _project_name(core, current) if current else "none", _project_name(core, target)),
                               {"from": _project_name(core, current) if current else None, "to": _project_name(core, target)},
                               [_norm(current), _norm(target)])
        ctx.run(lambda c: c.changeProject(target, writeToConfig=True))
        return {"changed": True, "persisted": True, "project": ctx.project_info()}
    if _norm(core.prismIni) == _norm(target):
        return {"changed": False, "persisted": False, "project": ctx.project_info()}
    ctx.run(lambda c: pin_project(c, target))
    return {"changed": True, "persisted": False, "project": ctx.project_info()}

