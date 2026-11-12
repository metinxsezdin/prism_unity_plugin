import os
import unittest

import prism_mcp.tools_session  # noqa: F401  (registers the tools)

from mcp_server.fake_core import FakeCore, call, make_session


class SessionToolsTests(unittest.TestCase):
    def setUp(self):
        self.core = FakeCore()
        self.wellness = self.core.make_project("Wellness", current=True)
        self.other = self.core.make_project("Meditation")
        self.session = make_session(self.core)

    def test_status_reports_versions_and_user(self):
        r = call(self.session, "status")
        self.assertTrue(r["ok"], r)
        status = r["result"]
        self.assertEqual(status["prismVersion"], "v2.1.2.1")
        self.assertEqual(status["teamVersion"], "v2.1.2.1")
        self.assertEqual(status["user"], "Ayse Kaya")
        self.assertEqual(status["userAbbreviation"], "aka")
        self.assertIn("serverVersion", status)
        self.assertNotIn("warning", status)
        self.assertEqual(r["project"]["name"], "Wellness")

    def test_status_warns_on_other_prism_version(self):
        self.core.version = "v2.1.3"
        warning = call(self.session, "status")["result"]["warning"]
        self.assertIn("v2.1.3", warning)
        self.assertIn("v2.1.2.1", warning)

    def test_status_without_user_is_needs_input(self):
        self.core.config["globals"]["username"] = ""
        r = call(self.session, "status")
        self.assertEqual(r["error"]["code"], "needs_input")
        self.assertEqual(r["error"]["details"]["missing"], ["prismUser"])

    def test_list_projects_marks_unreachable(self):
        self.core.projects.recent.append({"configPath": "Q:/gone/00_Pipeline/pipeline.json", "name": "Gone"})
        items = {p["name"]: p for p in call(self.session, "list_projects")["result"]["items"]}
        self.assertTrue(items["Wellness"]["reachable"])
        self.assertTrue(items["Wellness"]["current"])
        self.assertFalse(items["Meditation"]["current"])
        self.assertFalse(items["Gone"]["reachable"])

    def test_set_project_by_name_is_session_only(self):
        r = call(self.session, "set_project", name="meditation")
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["result"]["changed"])
        self.assertFalse(r["result"]["persisted"])
        self.assertEqual(r["project"]["name"], "Meditation")
        self.assertEqual(self.core.config["globals"]["current project"], self.wellness)

    def test_set_project_by_folder_path(self):
        r = call(self.session, "set_project", configPath=os.path.dirname(os.path.dirname(self.other)))
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.core.prismIni, self.other)

    def test_set_project_needs_exactly_one_of_name_and_path(self):
        self.assertEqual(call(self.session, "set_project")["error"]["code"], "bad_args")
        self.assertEqual(call(self.session, "set_project", name="x", configPath="y")["error"]["code"], "bad_args")

    def test_set_project_unknown_name_lists_projects(self):
        r = call(self.session, "set_project", name="Nope")
        self.assertEqual(r["error"]["code"], "bad_args")
        self.assertIn("Meditation", r["error"]["message"])

    def test_set_project_ambiguous_name_needs_input(self):
        twin = FakeCore(root=os.path.join(self.core.root, "twin")).make_project("Wellness", recent=False)
        self.core.projects.recent.append({"configPath": twin, "name": "Wellness"})
        r = call(self.session, "set_project", name="Wellness")
        self.assertEqual(r["error"]["code"], "needs_input")
        self.assertEqual(sorted(r["error"]["details"]["candidates"]), sorted([self.wellness, twin]))

    def test_set_project_unreachable_path_is_source_unavailable(self):
        r = call(self.session, "set_project", configPath="Q:/gone/00_Pipeline/pipeline.json")
        self.assertEqual(r["error"]["code"], "source_unavailable")

    def test_set_project_persist_needs_confirmation_then_writes(self):
        r = call(self.session, "set_project", name="Meditation", persist=True)
        self.assertEqual(r["error"]["code"], "needs_confirmation")
        self.assertEqual(r["error"]["details"]["changes"], {"from": "Wellness", "to": "Meditation"})
        self.assertEqual(self.core.config["globals"]["current project"], self.wellness)
        token = r["error"]["details"]["confirmToken"]
        r = call(self.session, "set_project", name="Meditation", persist=True, confirm=token)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["result"]["persisted"])
        self.assertEqual(self.core.config["globals"]["current project"], self.other)


if __name__ == "__main__":
    unittest.main()
