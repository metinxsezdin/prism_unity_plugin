"""Where each side of the bridge is listening, published in the Unity project's Library folder.

Ports are never reserved ahead of time: each side binds what is free and publishes the real port.
- Unity writes Library/PrismUnity/session.json {unityPort, token, ...} (PrismSession.cs).
- Prism writes Library/PrismUnity/prism.json {port, pid} once its server listens.
"""

import json
import os


def _folder(project):
    return os.path.join(project, "Library", "PrismUnity")


def write_prism_endpoint(project, port, pid):
    folder = _folder(project)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "prism.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"port": int(port), "pid": int(pid)}, f)
    os.replace(tmp, path)


def read_unity_endpoint(project):
    """(unityPort, token) from Unity's session.json, or None when it cannot be read."""
    try:
        with open(os.path.join(_folder(project), "session.json"), encoding="utf-8") as f:
            data = json.load(f)
        return int(data["unityPort"]), data["token"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
