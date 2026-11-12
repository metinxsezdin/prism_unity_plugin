"""The tool registry and the result envelope every tool answers with."""

import collections
import inspect
import logging

from unity_bridge.protocol import BridgeError

logger = logging.getLogger(__name__)

ToolSpec = collections.namedtuple("ToolSpec", "name description input_schema handler mutating")

TOOLS = {}

CONFIRM_SENTENCE = (
    "Never confirm on your own. Show the user details.summary and details.changes and ask; "
    "call again with confirm only after the user says yes."
)


def tool(name, description, schema, mutating=False):
    """Register handler(ctx, **args) as an MCP tool."""

    def register(handler):
        TOOLS[name] = ToolSpec(name, description, schema, handler, mutating)
        return handler

    return register


def _project(ctx):
    try:
        return ctx.project_info()
    except Exception:
        return None


def _error(code, message, details=None):
    return {"code": code, "message": message, "details": details or {}}


def call_tool(ctx, name, args, tools=None):
    """Run one tool; returns (envelope, is_error)."""
    tools = TOOLS if tools is None else tools
    spec = tools.get(name)
    args = dict(args or {})
    if spec is None:
        return {"ok": False, "project": _project(ctx), "error": _error("bad_args", "Unknown tool: %s" % name)}, True
    try:
        inspect.signature(spec.handler).bind(ctx, **args)
    except TypeError as e:
        return {"ok": False, "project": _project(ctx), "error": _error("bad_args", "%s: %s" % (name, e))}, True

    try:
        result = spec.handler(ctx, **args)
        envelope, is_error = {"ok": True, "project": _project(ctx), "result": result}, False
    except BridgeError as e:
        envelope, is_error = {"ok": False, "project": _project(ctx), "error": _error(e.code, e.message, e.details)}, True
    except Exception as e:
        logger.exception("tool %s failed", name)
        envelope, is_error = {"ok": False, "project": _project(ctx), "error": _error("internal", "%s: %s" % (type(e).__name__, e))}, True

    if spec.mutating:
        _audit(ctx, name, args, envelope)
    return envelope, is_error


def _audit(ctx, name, args, envelope):
    """Mutating calls that ran (or failed while running) go to the audit log; previews do not."""
    if not envelope["ok"] and envelope["error"]["code"] in ("needs_confirmation", "bad_args"):
        return
    audit = getattr(ctx, "audit", None)
    if audit is None:
        return
    try:
        audit(name, args, envelope)
    except Exception:
        logger.exception("could not write the audit log")
