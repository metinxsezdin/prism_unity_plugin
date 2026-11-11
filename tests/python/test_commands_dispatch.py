import unittest

from fakes import FakeCore
from unity_bridge import protocol
from unity_bridge.commands import PrismCommands
from unity_bridge.protocol import BridgeError


class PingCore(FakeCore):
    version = "v2.1.2.1"

    def __init__(self):
        super().__init__()
        self.silent_seen = None

    def getConfig(self, cat=None, param=None, dft=None, **kwargs):
        self.silent_seen = "silent" in self.prismArgs
        return False if param == "check_import_versions" else dft


def req(cmd, args=None, interactive=False):
    return protocol.make_request(cmd, args, "tok", interactive)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.core = PingCore()
        self.cmds = PrismCommands(self.core, unity=None)

    def test_dispatch_unknown_command(self):
        resp = self.cmds.dispatch(req("__import__", {"name": "os"}))
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "unknown_command")

    def test_dispatch_rejects_private_methods(self):
        resp = self.cmds.dispatch(req("dispatch"))
        self.assertEqual(resp["error"]["code"], "unknown_command")

    def test_ping_result(self):
        resp = self.cmds.dispatch(req("ping"))
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["result"], {"prismVersion": "v2.1.2.1", "checkImportVersions": False})

    def test_dispatch_headless_wraps_noninteractive(self):
        self.cmds.dispatch(req("ping", interactive=False))
        self.assertTrue(self.core.silent_seen)
        self.assertNotIn("silent", self.core.prismArgs)

    def test_dispatch_interactive_is_not_silent(self):
        self.cmds.dispatch(req("ping", interactive=True))
        self.assertFalse(self.core.silent_seen)

    def test_bad_args(self):
        resp = self.cmds.dispatch(req("ping", {"unexpected": 1}))
        self.assertEqual(resp["error"]["code"], "bad_args")

    def test_private_args_are_stripped(self):
        resp = self.cmds.dispatch(req("ping", {"_timeoutSec": 30}))
        self.assertTrue(resp["ok"])

    def test_bridge_error_becomes_error_response(self):
        def fail(**kwargs):
            raise BridgeError("needs_input", "Pick a task", {"missing": ["task"]})

        self.cmds.saveVersion = fail
        resp = self.cmds.dispatch(req("saveVersion"))
        self.assertEqual(resp["error"]["code"], "needs_input")
        self.assertEqual(resp["error"]["details"], {"missing": ["task"]})

    def test_headless_turns_error_dialog_into_error(self):
        # Prism's err_catcher swallows exceptions and calls core.writeErrorLog (a dialog).
        def swallowed(**kwargs):
            try:
                raise BridgeError("source_unavailable", "M: is offline")
            except Exception:
                self.core.writeErrorLog("traceback text")
                return None

        self.core.writeErrorLog = lambda text, data=None: None
        self.cmds.ping = swallowed
        resp = self.cmds.dispatch(req("ping", interactive=False))
        self.assertEqual(resp["error"]["code"], "source_unavailable")


if __name__ == "__main__":
    unittest.main()
