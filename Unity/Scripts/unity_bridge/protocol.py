"""Wire protocol shared by the Prism process and the Unity editor.

One UTF-8 JSON object per line. Requests carry a session token and a command
name from a fixed set; nothing received over the wire is ever executed as code.
"""

import json
import uuid

PROTOCOL_VERSION = 1

ERROR_CODES = frozenset(
    {
        "unknown_command",
        "bad_token",
        "bad_request",
        "bad_args",
        "needs_input",
        "needs_confirmation",
        "prism_unavailable",
        "unity_busy",
        "missing_package",
        "source_unavailable",
        "timeout",
        "internal",
    }
)


class BridgeError(Exception):
    """An error that travels over the bridge as {code, message, details}."""

    def __init__(self, code, message="", details=None):
        if code not in ERROR_CODES:
            raise ValueError("Unknown bridge error code: %s" % code)
        super().__init__("%s: %s" % (code, message))
        self.code = code
        self.message = message
        self.details = details or {}

    def to_response(self, request_id):
        return err(request_id, self.code, self.message, self.details)


def encode(msg):
    return (json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def decode(line):
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError:
            raise BridgeError("bad_request", "Message is not valid UTF-8.")
    try:
        msg = json.loads(line)
    except ValueError:
        raise BridgeError("bad_request", "Message is not valid JSON.")
    if not isinstance(msg, dict):
        raise BridgeError("bad_request", "Message must be a JSON object.")
    if msg.get("v") != PROTOCOL_VERSION:
        raise BridgeError("bad_request", "Unsupported protocol version: %r" % msg.get("v"))
    if "ok" not in msg and not isinstance(msg.get("cmd"), str):
        raise BridgeError("bad_request", "Request has no command.")
    return msg


def make_request(cmd, args, token, interactive):
    return {
        "v": PROTOCOL_VERSION,
        "id": uuid.uuid4().hex,
        "token": token,
        "cmd": cmd,
        "args": args or {},
        "interactive": bool(interactive),
    }


def ok(request_id, result):
    return {"v": PROTOCOL_VERSION, "id": request_id, "ok": True, "result": result}


def err(request_id, code, message, details=None):
    if code not in ERROR_CODES:
        raise ValueError("Unknown bridge error code: %s" % code)
    return {
        "v": PROTOCOL_VERSION,
        "id": request_id,
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
    }
