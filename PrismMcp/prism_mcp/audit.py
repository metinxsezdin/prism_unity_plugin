"""A per-user log of every change the Prism MCP made: one JSON object per line."""

import datetime
import json
import os

from . import prefs


def default_path():
    """Next to the user's Prism settings (Documents\Prism2), wherever Windows keeps Documents."""
    return os.path.join(prefs.user_prefs_dir(), "PrismMcp.log")


def write(path, user, project, tool, args, envelope):
    if envelope.get("ok"):
        outcome = {"ok": True}
    else:
        error = envelope.get("error") or {}
        outcome = {"ok": False, "code": error.get("code"), "message": error.get("message")}
    entry = {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "user": user,
        "project": project,
        "tool": tool,
        "args": {k: v for k, v in args.items() if k != "confirm"},
        "outcome": outcome,
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
