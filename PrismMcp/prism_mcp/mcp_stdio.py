"""MCP over stdio: JSON-RPC 2.0, one UTF-8 JSON object per line."""

import json
import logging
import os
import sys

from . import SERVER_VERSION, registry

logger = logging.getLogger(__name__)

SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_VERSION = SUPPORTED_VERSIONS[0]


def guard_stdout():
    """Keep fd 1 for MCP only: returns a binary stream on the real stdout, sends everything else to stderr.

    Prism logs and prints while it loads and works; a stray line on stdout breaks the MCP client.
    """
    sys.stdout.flush()
    fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return os.fdopen(fd, "wb", buffering=0)


def _error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


class McpServer(object):
    def __init__(self, ctx, tools=None):
        self.ctx = ctx
        self.tools = registry.TOOLS if tools is None else tools

    def handle(self, message):
        """Answer one JSON-RPC message; notifications get None."""
        if not isinstance(message, dict) or not isinstance(message.get("method"), str):
            return _error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid request")
        method = message["method"]
        if "id" not in message:
            return None
        rid = message["id"]
        params = message.get("params") or {}

        if method == "initialize":
            requested = params.get("protocolVersion")
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": requested if requested in SUPPORTED_VERSIONS else LATEST_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "prism", "version": SERVER_VERSION},
            }}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": rid, "result": {}}
        if method == "tools/list":
            tools = [{"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                     for t in sorted(self.tools.values(), key=lambda t: t.name)]
            return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}
        if method == "tools/call":
            envelope, is_error = registry.call_tool(self.ctx, params.get("name"), params.get("arguments"), tools=self.tools)
            text = json.dumps(envelope, ensure_ascii=False, default=str)
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}], "isError": is_error}}
        return _error(rid, -32601, "Method not found: %s" % method)

    def serve(self, instream, outstream):
        for raw in instream:
            if not raw.strip():
                continue
            try:
                message = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                response = _error(None, -32700, "Parse error")
            else:
                try:
                    response = self.handle(message)
                except Exception as e:  # never let one request kill the server
                    logger.exception("request failed")
                    response = _error(message.get("id") if isinstance(message, dict) else None, -32603, str(e))
            if response is not None:
                outstream.write(json.dumps(response, ensure_ascii=False, default=str).encode("utf-8") + b"\n")
                outstream.flush()
