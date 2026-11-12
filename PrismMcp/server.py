"""Prism MCP server: Claude's tools for a Prism Pipeline 2 project, over stdio, without windows.

Run with Prism's Python:
    "<PrismRoot>\\Python313\\python.exe" PrismMcp\\server.py           (MCP over stdin/stdout)
    "<PrismRoot>\\Python313\\python.exe" PrismMcp\\server.py --check   (one-line health check)

Environment: PRISM_ROOT (default C:\\Program Files\\Prism2), PRISM_MCP_AUDIT_LOG (default Documents\\Prism2\\PrismMcp.log).
"""

import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PRISM_ROOT = os.environ.get("PRISM_ROOT", r"C:\Program Files\Prism2")

# Prism's embedded Python ignores PYTHONPATH (python313._pth), so the paths are added here.
for _p in reversed([
    HERE,
    os.path.join(REPO, "Unity", "Scripts"),
    os.path.join(PRISM_ROOT, "Scripts"),
    os.path.join(PRISM_ROOT, "PythonLibs", "Python313"),
    os.path.join(PRISM_ROOT, "PythonLibs", "Python3"),
    os.path.join(PRISM_ROOT, "PythonLibs", "Python3", "PySide"),
]):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unity_bridge.protocol import BridgeError  # noqa: E402

from prism_mcp import registry  # noqa: E402
from prism_mcp.mcp_stdio import McpServer, guard_stdout  # noqa: E402
from prism_mcp.session import Session  # noqa: E402

TOOL_MODULES = ("tools_session", "tools_query", "reports", "tools_create", "tools_versions", "tools_shots")


def load_tools():
    for name in TOOL_MODULES:
        importlib.import_module("prism_mcp." + name)
    return registry.TOOLS


def _line(out, text):
    out.write((text + "\n").encode("utf-8"))
    out.flush()


def check(session, out):
    """Boot Prism and print one summary line; 0 when Claude can use it, 1 otherwise."""
    load_tools()
    envelope, is_error = registry.call_tool(session, "status", {})
    if is_error:
        _line(out, "Prism MCP problem: %s" % envelope["error"]["message"])
        return 1
    status = envelope["result"]
    projects, _ = registry.call_tool(session, "list_projects", {})
    count = len(projects["result"]["items"]) if projects.get("ok") else 0
    text = "Prism MCP OK: Prism %s, user %s, %d projects" % (status["prismVersion"], status["user"], count)
    if status.get("warning"):
        text += " WARNING: " + status["warning"]
    _line(out, text)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = guard_stdout()  # from here on only `out` reaches the real stdout
    session = Session(audit_path=os.environ.get("PRISM_MCP_AUDIT_LOG") or None)
    if "--check" in argv:
        try:
            return check(session, out)
        except BridgeError as e:
            _line(out, "Prism MCP problem: %s" % e.message)
            return 1
    load_tools()
    McpServer(session).serve(sys.stdin.buffer, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
