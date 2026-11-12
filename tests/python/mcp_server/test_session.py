import json
import os
import unittest

from unity_bridge.protocol import BridgeError

from mcp_server.fake_core import FakeCore, make_session


class SessionTests(unittest.TestCase):
    def test_core_is_lazy(self):
        from prism_mcp.session import Session

        made = []
        session = Session(core_factory=lambda: made.append(1) or FakeCore(), audit_path=os.devnull)
        self.assertEqual(made, [])
        self.assertIsNone(session.project_info())
        session.core
        session.core
        self.assertEqual(made, [1])

    def test_factory_failure_is_prism_unavailable(self):
        from prism_mcp.session import Session

        def broken():
            raise ImportError("No module named PrismCore")

        with self.assertRaises(BridgeError) as cm:
            Session(core_factory=broken, audit_path=os.devnull).core
        self.assertEqual(cm.exception.code, "prism_unavailable")
        self.assertIn("PrismCore", cm.exception.message)

    def test_run_turns_popup_question_into_needs_input(self):
        core = FakeCore()
        original = core.popupQuestion
        session = make_session(core)
        with self.assertRaises(BridgeError) as cm:
            session.run(lambda c: c.popupQuestion("Retry?", buttons=["Retry", "Cancel"]))
        self.assertEqual(cm.exception.code, "needs_input")
        self.assertEqual(core.popupQuestion, original)
        self.assertEqual(core.popups, [])

    def test_unreachable_project_is_source_unavailable(self):
        core = FakeCore()
        core.make_project("Wellness", current=True)
        core.projectPath = os.path.join(core.root, "offline M drive")
        with self.assertRaises(BridgeError) as cm:
            make_session(core).require_project()
        self.assertEqual(cm.exception.code, "source_unavailable")

    def test_no_project_is_needs_input(self):
        with self.assertRaises(BridgeError) as cm:
            make_session(FakeCore()).require_project()
        self.assertEqual(cm.exception.code, "needs_input")
        self.assertEqual(cm.exception.details["missing"], ["prismProject"])

    def _mutating_tools(self, handler):
        from prism_mcp import registry

        return {"touch": registry.ToolSpec("touch", "", {"type": "object"}, handler, True)}

    def test_mutating_call_is_audited(self):
        from prism_mcp import registry

        core = FakeCore()
        core.make_project("Wellness", current=True)
        session = make_session(core)
        session.core
        registry.call_tool(session, "touch", {"what": "Lotus"}, tools=self._mutating_tools(lambda ctx, what: "done"))
        with open(session.audit_path, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["tool"], "touch")
        self.assertEqual(lines[0]["user"], "Ayse Kaya")
        self.assertEqual(lines[0]["project"]["name"], "Wellness")
        self.assertEqual(lines[0]["args"], {"what": "Lotus"})
        self.assertTrue(lines[0]["outcome"]["ok"])
        self.assertIn("time", lines[0])

    def test_needs_confirmation_is_not_audited(self):
        from prism_mcp import registry

        session = make_session(FakeCore())

        def preview(ctx):
            raise BridgeError("needs_confirmation", "sure?")

        registry.call_tool(session, "touch", {}, tools=self._mutating_tools(preview))
        self.assertFalse(os.path.exists(session.audit_path))


if __name__ == "__main__":
    unittest.main()
