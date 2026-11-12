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

    def test_each_tool_call_clears_prism_config_cache(self):
        # C1: Prism caches config files for the life of the process; a teammate's change must be seen.
        from prism_mcp import registry

        core = FakeCore()
        cleared = []
        core.configs = type("Configs", (), {"clearCache": lambda self, path=None: cleared.append(path)})()
        session = make_session(core)
        session.core
        tools = {"look": registry.ToolSpec("look", "", {"type": "object"}, lambda ctx: "ok", False)}
        registry.call_tool(session, "look", {}, tools=tools)
        registry.call_tool(session, "look", {}, tools=tools)
        self.assertEqual(cleared, [None, None])

    def test_run_turns_message_box_exec_into_needs_input(self):
        # C2: Prism's renameSequence shows a QMessageBox with exec_() directly; offscreen it would block forever.
        import prism_env  # noqa: F401
        from qtpy import QtWidgets

        original = QtWidgets.QMessageBox.exec_
        session = make_session(FakeCore())
        with self.assertRaises(BridgeError) as cm:
            session.run(lambda c: QtWidgets.QMessageBox.exec_(object()))
        self.assertEqual(cm.exception.code, "needs_input")
        with self.assertRaises(BridgeError):
            session.run(lambda c: QtWidgets.QDialog.exec_(object()))
        self.assertIs(QtWidgets.QMessageBox.exec_, original)

    def test_offline_current_project_is_source_unavailable(self):
        # I1: Prism leaves no project active when the user's project drive is offline at start.
        core = FakeCore()
        core.config["globals"]["current project"] = "Q:/Wellness/00_Pipeline/pipeline.json"
        with self.assertRaises(BridgeError) as cm:
            make_session(core).require_project()
        self.assertEqual(cm.exception.code, "source_unavailable")
        self.assertIn("Q:/Wellness", cm.exception.message)

    def test_missing_user_name_stops_before_prism_starts(self):
        # I2: PrismCore.create would write the Windows login into Prism.json as the user's name.
        import tempfile
        from prism_mcp import session as session_module

        prefs = tempfile.mkdtemp()
        with open(os.path.join(prefs, "Prism.json"), "w", encoding="utf-8") as f:
            json.dump({"globals": {"current project": ""}}, f)
        old = os.environ.get("PRISM_USER_PREFS")
        os.environ["PRISM_USER_PREFS"] = prefs
        try:
            with self.assertRaises(BridgeError) as cm:
                session_module.create_core()
        finally:
            if old is None:
                os.environ.pop("PRISM_USER_PREFS")
            else:
                os.environ["PRISM_USER_PREFS"] = old
        self.assertEqual(cm.exception.code, "needs_input")
        self.assertEqual(cm.exception.details["missing"], ["prismUser"])
        with open(os.path.join(prefs, "Prism.json"), encoding="utf-8") as f:
            self.assertNotIn("username", json.load(f)["globals"])

    def test_audit_log_follows_prism_user_prefs(self):
        # I7: Prism finds Documents through the Shell API or PRISM_USER_PREFS, not USERPROFILE\Documents.
        from prism_mcp import audit

        old = os.environ.get("PRISM_USER_PREFS")
        os.environ["PRISM_USER_PREFS"] = os.path.join("X:", "prefs", "Prism2")
        try:
            self.assertEqual(audit.default_path(), os.path.join("X:", "prefs", "Prism2", "PrismMcp.log"))
        finally:
            if old is None:
                os.environ.pop("PRISM_USER_PREFS")
            else:
                os.environ["PRISM_USER_PREFS"] = old

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
