import io
import os
import unittest

import server
from prism_mcp import registry

from mcp_server.fake_core import FakeCore, make_session

SPEC_TOOLS = (
    "status list_projects set_project list_entities get_entity list_scenefiles list_products list_versions list_media "
    "get_dependencies report create_entity create_department create_task apply_task_preset list_task_presets "
    "set_description set_metadata set_preview set_shot_range set_master delete_master set_comment omit unomit rename delete_shot"
).split()


class ServerTests(unittest.TestCase):
    def test_all_spec_tools_registered(self):
        server.load_tools()
        self.assertEqual(sorted(registry.TOOLS), sorted(SPEC_TOOLS))

    def test_mutating_tools_carry_confirmation_sentence(self):
        server.load_tools()
        for spec in registry.TOOLS.values():
            if "confirm" in spec.input_schema.get("properties", {}):
                self.assertTrue(spec.mutating, spec.name)
                self.assertIn(registry.CONFIRM_SENTENCE, spec.description, spec.name)

    def test_read_only_tools_are_not_mutating(self):
        server.load_tools()
        for name in ("status", "list_projects", "list_entities", "get_entity", "list_scenefiles", "list_products",
                     "list_versions", "list_media", "get_dependencies", "report", "list_task_presets"):
            self.assertFalse(registry.TOOLS[name].mutating, name)

    def test_tools_md_documents_every_tool(self):
        server.load_tools()
        with open(os.path.join(server.HERE, "TOOLS.md"), encoding="utf-8") as f:
            headings = {line[4:].strip() for line in f if line.startswith("### ")}
        self.assertEqual(sorted(set(registry.TOOLS) - headings), [])

    def test_check_reports_ok(self):
        core = FakeCore()
        core.make_project("Wellness", current=True)
        core.make_project("Meditation")
        out = io.BytesIO()
        self.assertEqual(server.check(make_session(core), out), 0)
        self.assertEqual(out.getvalue().decode("utf-8").strip(), "Prism MCP OK: Prism v2.1.2.1, user Ayse Kaya, 2 projects")

    def test_check_warns_on_other_prism_version(self):
        core = FakeCore()
        core.version = "v2.1.3"
        out = io.BytesIO()
        self.assertEqual(server.check(make_session(core), out), 0)
        self.assertIn("WARNING", out.getvalue().decode("utf-8"))
        self.assertIn("v2.1.2.1", out.getvalue().decode("utf-8"))

    def test_check_reports_missing_user(self):
        core = FakeCore()
        core.config["globals"]["username"] = ""
        out = io.BytesIO()
        self.assertEqual(server.check(make_session(core), out), 1)
        self.assertEqual(out.getvalue().decode("utf-8").strip(),
                         "Prism MCP problem: No Prism user name is set. Open Prism once and enter your name.")

    def test_check_reports_prism_that_does_not_start(self):
        from prism_mcp.session import Session

        def broken():
            raise ImportError("No module named 'PrismCore'")

        out = io.BytesIO()
        self.assertEqual(server.check(Session(core_factory=broken, audit_path=os.devnull), out), 1)
        self.assertIn("Prism could not start", out.getvalue().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
