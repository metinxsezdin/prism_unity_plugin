"""Two-step confirmation for tools that change or remove existing data.

The first call returns needs_confirmation with a token derived from the arguments and from the
state the change is based on. Only a second call with that token goes ahead; if the state moved in
between (someone else changed the master), the token no longer matches and a fresh preview is shown.
"""

import hashlib
import json

from unity_bridge.protocol import BridgeError


def token(tool, args, state):
    payload = [tool, {k: v for k, v in (args or {}).items() if k != "confirm"}, state]
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def require(ctx, tool, args, summary, changes, state):
    """Return only if args carries the token for this exact preview; otherwise ask for confirmation."""
    expected = token(tool, args, state)
    if (args or {}).get("confirm") == expected:
        return
    raise BridgeError("needs_confirmation", summary, {"summary": summary, "changes": changes, "confirmToken": expected})
