import os
import unittest

import prism_env  # noqa: F401  (Prism's Qt bindings, for the preview image check)
import prism_mcp.tools_create  # noqa: F401  (registers the tools)

from mcp_server.fake_core import call, make_project_core, make_session

LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}
NEW = {"type": "asset", "asset_path": "Props/Tea Cup"}
SH020 = {"type": "shot", "sequence": "sq01", "shot": "sh020"}


class CreateToolsTests(unittest.TestCase):
    def setUp(self):
        self.core = make_project_core()
        self.core.entities.add_asset("Props/Lotus")
        self.session = make_session(self.core)

    def _ok(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertTrue(r["ok"], r)
        return r["result"]

    def _err(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertFalse(r["ok"], r)
        return r["error"]

    def test_create_asset_then_again_is_created_false(self):
        r = self._ok("create_entity", entity=NEW, description="for the tea scene")
        self.assertTrue(r["created"])
        self.assertIn("Props/Tea Cup", self.core.entities.assets)
        self.assertEqual(self.core.entities.descriptions["Tea Cup"], "for the tea scene")
        r = self._ok("create_entity", entity=NEW)
        self.assertFalse(r["created"])
        self.assertEqual(self.core.entities.assets.count("Props/Tea Cup"), 1)

    def test_create_shot_with_frame_range(self):
        self.assertTrue(self._ok("create_entity", entity=SH020, frameRange=[1001, 1050])["created"])
        self.assertEqual(self.core.entities.ranges["sq01/sh020"], [1001, 1050])

    def test_create_existing_says_what_it_ignored(self):
        # M9: an existing asset keeps its description and tasks; the answer says so instead of staying silent.
        r = self._ok("create_entity", entity=LOTUS, description="new text", taskPreset="Prop")
        self.assertFalse(r["created"])
        self.assertEqual(r["ignored"], ["description", "taskPreset"])
        self.assertIn("set_description", r["note"])
        self.assertIn("apply_task_preset", r["note"])
        self.assertNotIn("Lotus", self.core.entities.descriptions)
        self.assertNotIn("ignored", self._ok("create_entity", entity=LOTUS))

    def test_create_existing_shot_ignores_frame_range_and_says_so(self):
        self.core.entities.add_shot("sq01", "sh020", frame_range=(1001, 1050))
        r = self._ok("create_entity", entity=SH020, frameRange=[1, 10])
        self.assertEqual(r["ignored"], ["frameRange"])
        self.assertIn("set_shot_range", r["note"])
        self.assertEqual(self.core.entities.ranges["sq01/sh020"], [1001, 1050])

    def test_create_existing_omitted_asset_reports_omitted(self):
        self.core.entities.add_asset("Props/Old Vase", omitted=True)
        r = self._ok("create_entity", entity={"type": "asset", "asset_path": "Props/Old Vase"})
        self.assertEqual((r["created"], r["omitted"]), (False, True))

    def test_invalid_asset_name_is_bad_args_not_dialog(self):
        for bad in ("Props/Export", "Props/Te:a", "Props//Cup", "Props/ "):
            self.assertEqual(self._err("create_entity", entity={"type": "asset", "asset_path": bad})["code"], "bad_args", bad)
        self.assertEqual(self.core.popups, [])
        self.assertEqual(self.core.entities.assets, ["Props/Lotus"])

    def test_category_folder_is_not_an_asset(self):
        # I3: "Props" holds assets; treating it as one would hide every asset under it from Prism.
        props = {"type": "asset", "asset_path": "Props"}
        self.assertEqual(self._err("create_entity", entity=props)["code"], "bad_args")
        self.assertEqual(self._err("create_department", entity=props, department="Modeling")["code"], "bad_args")
        self.assertFalse(os.path.exists(os.path.join(self.core.getEntityPath(entity=props), "Scenefiles")))

    def test_create_department_without_default_tasks_succeeds(self):
        # I4: Prism's createDepartment returns None when the department has no default tasks.
        original = self.core.entities.createDepartment
        self.core.entities.createDepartment = lambda *a, **k: (original(*a, **k), None)[1]
        r = self._ok("create_department", entity=LOTUS, department="Modeling")
        self.assertTrue(r["created"])

    def test_dot_segments_are_bad_args(self):
        # M5 (promoted): ".." must never walk out of the entity folders.
        self.assertEqual(self._err("create_entity", entity={"type": "asset", "asset_path": "Props/../Lotus"})["code"], "bad_args")
        self.assertEqual(self._err("create_entity", entity={"type": "shot", "sequence": "..", "shot": "03_Production"})["code"], "bad_args")
        self.assertEqual(self._err("create_entity", entity={"type": "shot", "sequence": "sq01", "shot": "a/b"})["code"], "bad_args")
        # Shots/../.. is the project folder itself: it exists, so only validation can stop it.
        e = self._err("create_department", entity={"type": "shot", "sequence": "..", "shot": ".."}, department="Animation")
        self.assertEqual(e["code"], "bad_args")
        self.assertFalse(os.path.exists(os.path.join(self.core.projectPath, "Scenefiles")))

    def test_create_with_task_preset(self):
        self._ok("create_entity", entity=NEW, taskPreset="Prop")
        self.assertEqual(self.core.entities.steps["Props/Tea Cup"], {"mod": ["Sculpt", "Retopo"], "surf": ["Surfacing"]})

    def test_unknown_task_preset_lists_names(self):
        e = self._err("create_entity", entity=NEW, taskPreset="Hero")
        self.assertEqual(e["code"], "bad_args")
        self.assertIn("Prop", e["message"])
        self.assertNotIn("Props/Tea Cup", self.core.entities.assets)

    def test_create_department_adds_default_tasks(self):
        r = self._ok("create_department", entity=LOTUS, department="Modeling")
        self.assertEqual((r["created"], r["department"], r["tasks"]), (True, "mod", ["Modeling"]))
        r = self._ok("create_department", entity=LOTUS, department="mod")
        self.assertFalse(r["created"])
        r = self._ok("create_department", entity=LOTUS, department="Surfacing", defaultTasks=False)
        self.assertEqual(r["tasks"], [])

    def test_unknown_department_lists_valid(self):
        e = self._err("create_department", entity=LOTUS, department="Lighting")
        self.assertEqual(e["code"], "bad_args")
        self.assertIn("Modeling", e["message"])
        self.assertIn("Surfacing", e["message"])

    def test_create_task(self):
        self._ok("create_department", entity=LOTUS, department="Modeling", defaultTasks=False)
        r = self._ok("create_task", entity=LOTUS, department="Modeling", task="Sculpt")
        self.assertTrue(r["created"])
        self.assertFalse(self._ok("create_task", entity=LOTUS, department="mod", task="Sculpt")["created"])
        self.assertEqual(self.core.entities.steps["Props/Lotus"]["mod"], ["Sculpt"])

    def test_create_task_without_department_needs_input(self):
        e = self._err("create_task", entity=LOTUS, department="Modeling", task="Sculpt")
        self.assertEqual(e["code"], "needs_input")
        self.assertEqual(e["details"]["missing"], ["department"])

    def test_create_on_missing_entity_is_bad_args(self):
        self.assertEqual(self._err("create_department", entity=NEW, department="Modeling")["code"], "bad_args")

    def test_apply_task_preset_dry_run_writes_nothing(self):
        r = self._ok("apply_task_preset", entity=LOTUS, preset="Prop", dryRun=True)
        self.assertEqual(r["departments"], [{"name": "Modeling", "tasks": ["Sculpt", "Retopo"]}, {"name": "Surfacing", "tasks": ["Surfacing"]}])
        self.assertEqual(r["created"], [])
        self.assertNotIn("Props/Lotus", self.core.entities.steps)
        r = self._ok("apply_task_preset", entity=LOTUS, preset="Prop")
        self.assertEqual(len(r["created"]), 3)

    def test_list_task_presets(self):
        self.assertEqual([p["name"] for p in self._ok("list_task_presets")], ["Prop"])

    def test_set_description_empty_writes_without_confirm(self):
        self._ok("set_description", entity=LOTUS, description="Pink lotus")
        self.assertEqual(self.core.entities.descriptions["Lotus"], "Pink lotus")

    def test_set_description_overwrite_needs_confirmation(self):
        self.core.entities.descriptions["Lotus"] = "Pink lotus"
        e = self._err("set_description", entity=LOTUS, description="White lotus")
        self.assertEqual(e["code"], "needs_confirmation")
        self.assertEqual(e["details"]["changes"], {"from": "Pink lotus", "to": "White lotus"})
        self.assertEqual(self.core.entities.descriptions["Lotus"], "Pink lotus")
        self._ok("set_description", entity=LOTUS, description="White lotus", confirm=e["details"]["confirmToken"])
        self.assertEqual(self.core.entities.descriptions["Lotus"], "White lotus")

    def test_set_description_on_shot_is_bad_args(self):
        self.core.entities.add_shot("sq01", "sh010")
        e = self._err("set_description", entity={"type": "shot", "sequence": "sq01", "shot": "sh010"}, description="x")
        self.assertEqual(e["code"], "bad_args")

    def test_set_metadata_adds_keys_and_confirms_changed_ones(self):
        self._ok("set_metadata", entity=LOTUS, metaData={"polycount": "12k"})
        self.assertEqual(self.core.entities.metadata["Props/Lotus"], {"polycount": {"value": "12k", "show": True}})
        self._ok("set_metadata", entity=LOTUS, metaData={"polycount": "12k", "artist": "mke"})  # nothing existing changes
        e = self._err("set_metadata", entity=LOTUS, metaData={"polycount": "8k"})
        self.assertEqual(e["code"], "needs_confirmation")
        self.assertEqual(e["details"]["changes"], {"polycount": {"from": "12k", "to": "8k"}})
        self._ok("set_metadata", entity=LOTUS, metaData={"polycount": "8k"}, confirm=e["details"]["confirmToken"])
        self.assertEqual(self.core.entities.metadata["Props/Lotus"]["polycount"]["value"], "8k")
        self.assertEqual(self.core.entities.metadata["Props/Lotus"]["artist"]["value"], "mke")

    def test_set_shot_range_overwrite_needs_confirmation(self):
        self.core.entities.add_shot("sq01", "sh010", frame_range=(1001, 1100))
        shot = {"type": "shot", "sequence": "sq01", "shot": "sh010"}
        e = self._err("set_shot_range", entity=shot, start=1001, end=1120)
        self.assertEqual(e["code"], "needs_confirmation")
        self.assertEqual(e["details"]["changes"], {"from": [1001, 1100], "to": [1001, 1120]})
        self._ok("set_shot_range", entity=shot, start=1001, end=1120, confirm=e["details"]["confirmToken"])
        self.assertEqual(self.core.entities.ranges["sq01/sh010"], [1001, 1120])
        self.assertEqual(self._err("set_shot_range", entity=shot, start=10, end=5)["code"], "bad_args")

    def test_set_preview_rejects_non_image(self):
        bogus = os.path.join(self.core.root, "notes.txt")
        with open(bogus, "w") as f:
            f.write("not an image")
        self.assertEqual(self._err("set_preview", entity=LOTUS, imagePath=bogus)["code"], "bad_args")
        self.assertEqual(self._err("set_preview", entity=LOTUS, imagePath=bogus + ".missing")["code"], "bad_args")


if __name__ == "__main__":
    unittest.main()
