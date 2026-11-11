"""Unity → Prism commands. Only names in COMMANDS can ever be dispatched."""

import inspect

from . import protocol
from .headless import headless
from .protocol import BridgeError

COMMANDS = frozenset(
    {
        "ping",
        "projectBrowser",
        "settings",
        "saveVersion",
        "saveComment",
        "importDialog",
        "listProducts",
        "listVersions",
        "resolveVersion",
        "checkVersions",
        "checkVersionsDialog",
        "playblastDialog",
        "playblastTarget",
        "playblastDone",
    }
)


class PrismCommands(object):
    def __init__(self, core, unity):
        self.core = core
        self.unity = unity

    def dispatch(self, request):
        """Run one request and return a protocol response dict (never raises)."""
        request_id = request.get("id")
        cmd = request.get("cmd")
        fn = getattr(self, cmd, None) if cmd in COMMANDS else None
        if fn is None:
            return protocol.err(request_id, "unknown_command", "Unknown command: %s" % cmd)

        args = {k: v for k, v in (request.get("args") or {}).items() if not k.startswith("_")}
        try:
            inspect.signature(fn).bind(**args)
        except TypeError as e:
            return protocol.err(request_id, "bad_args", "Bad arguments for %s: %s" % (cmd, e))

        try:
            if request.get("interactive"):
                result = fn(**args)
            else:
                with headless(self.core):
                    result = fn(**args)
        except BridgeError as e:
            return e.to_response(request_id)
        return protocol.ok(request_id, result)

    # --- general -------------------------------------------------------------

    def ping(self):
        return {
            "prismVersion": getattr(self.core, "version", ""),
            "checkImportVersions": bool(self.core.getConfig("globals", "check_import_versions", dft=True)),
        }

    def projectBrowser(self):
        self.core.projectBrowser()
        return True

    def settings(self):
        self.core.prismSettings()
        return True
