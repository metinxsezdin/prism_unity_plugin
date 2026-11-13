"""A per-user log of every change the Prism MCP made: one JSON object per line."""

import datetime
import json
import os

from . import prefs

# A result longer than this (as JSON) is shortened in the log; the change itself is not affected.
MAX_RESULT_CHARS = 4000


def default_path():
    """Next to the user's Prism settings (Documents\\Prism2), wherever Windows keeps Documents."""
    return os.path.join(prefs.user_prefs_dir(), "PrismMcp.log")


def _kept(outcome, key, value):
    """outcome[key] = value, or its first MAX_RESULT_CHARS characters as text when it is very long."""
    if value in (None, {}, []):
        return
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= MAX_RESULT_CHARS:
        outcome[key] = value
    else:
        outcome[key] = text[:MAX_RESULT_CHARS]
        outcome[key + "Truncated"] = True


def write(path, user, project, tool, args, envelope):
    """What changed and where it went (trash folder, renamed names, a stopped rename's renamed/remaining)."""
    if envelope.get("ok"):
        outcome = {"ok": True}
        _kept(outcome, "result", envelope.get("result"))
    else:
        error = envelope.get("error") or {}
        outcome = {"ok": False, "code": error.get("code"), "message": error.get("message")}
        _kept(outcome, "details", error.get("details"))
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
