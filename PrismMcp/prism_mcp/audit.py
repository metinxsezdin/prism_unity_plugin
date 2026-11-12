"""A per-user log of every change the Prism MCP made: one JSON object per line."""

import datetime
import json
import os

DEFAULT_PATH = os.path.join(os.path.expanduser("~"), "Documents", "Prism2", "PrismMcp.log")


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
