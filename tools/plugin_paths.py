"""Add or remove a plugin folder in Prism's PluginPaths.json (used by deploy_dev.ps1).

Usage: python plugin_paths.py <PluginPaths.json> <plugin folder> add|remove
"""

import json
import os
import sys


def main():
    cfg, plugin, action = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(cfg, encoding="utf-8") as f:
        data = json.load(f)

    def norm(p):
        return os.path.normcase(os.path.abspath(p))

    plugins = data.setdefault("plugins", [])
    others = [p for p in plugins if norm(p.get("path", "")) != norm(plugin)]
    if action == "add":
        others.append({"path": plugin})
    data["plugins"] = others
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(("registered " if action == "add" else "removed ") + plugin)


if __name__ == "__main__":
    main()
