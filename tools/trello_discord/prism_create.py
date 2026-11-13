"""Creates Prism assets with the Prism MCP's own tools, without windows. Called by trello_discord.py.

Run with Prism's Python; reads JSON from stdin and writes JSON to stdout:
    in:  {"mcp": "<repo>/PrismMcp", "project": "<Prism project folder>",
          "assets": [{"asset_path": "Props/Lotus", "taskPreset": "" , "description": ""}]}
    out: {"ok": true, "results": [{"asset_path": ..., "ok": true, "created": true} | {"asset_path": ..., "ok": false, "error": "..."}]}
         {"ok": false, "error": "..."} when Prism or the project cannot be opened.
"""

import json
import os
import sys


def main():
    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    real_out = sys.stdout.buffer
    sys.stdout = sys.stderr  # Prism prints while booting; only the answer goes to stdout

    def answer(data):
        real_out.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        real_out.flush()

    mcp = os.path.abspath(request["mcp"])
    sys.path.insert(0, mcp)
    import server  # PrismMcp/server.py: sets up Prism's import paths

    from prism_mcp import registry
    from prism_mcp.session import Session

    server.load_tools()
    session = Session(audit_path=os.environ.get("PRISM_MCP_AUDIT_LOG") or None)
    envelope, is_error = registry.call_tool(session, "set_project", {"configPath": request["project"]})
    if is_error:
        answer({"ok": False, "error": envelope["error"]["message"]})
        return 1
    results = []
    for item in request["assets"]:
        args = {"entity": {"type": "asset", "asset_path": item["asset_path"]}}
        if item.get("taskPreset"):
            args["taskPreset"] = item["taskPreset"]
        if item.get("description"):
            args["description"] = item["description"]
        envelope, is_error = registry.call_tool(session, "create_entity", args)
        if is_error:
            results.append({"asset_path": item["asset_path"], "ok": False, "error": envelope["error"]["message"]})
        else:
            results.append({"asset_path": item["asset_path"], "ok": True, "created": envelope["result"].get("created", True)})
    answer({"ok": True, "results": results})
    return 0


if __name__ == "__main__":
    sys.exit(main())
