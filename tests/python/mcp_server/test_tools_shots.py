import os
import unittest

import prism_mcp.tools_shots  # noqa: F401  (registers the tools)

from mcp_server.fake_core import call, make_project_core, make_session

SH010 = {"type": "shot", "sequence": "sq01", "shot": "sh010"}
ROOM = {"type": "asset", "asset_path": "Scenes/MeditationRoom"}


class ShotToolsTests(unittest.TestCase):
    def setUp(self):
        self.core = make_project_core()
        self.core.entities.add_shot("sq01", "sh010", frame_range=(1001, 1100))
        self.core.entities.add_asset("Scenes/MeditationRoom")
        self.shot_dir = self.core.getEntityPath(entity=SH010)
        with open(os.path.join(self.shot_dir, "notes.txt"), "w") as f:
            f.write("x")
        self.session = make_session(self.core)

    def _local(self):
        """Give the project a local copy of the shot (Prism's 'local files')."""
        self.core.useLocalFiles = True
        self.core.localProjectPath = os.path.join(self.core.root, "local", "Wellness")
        local = self.shot_dir.replace(self.core.projectPath, self.core.localProjectPath)
        os.makedirs(local)
        with open(os.path.join(local, "cache.txt"), "w") as f:
            f.write("x")
        return local

    def _ok(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertTrue(r["ok"], r)
        return r["result"]

    def _err(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertFalse(r["ok"], r)
        return r["error"]

    def _token(self, tool, **args):
        e = self._err(tool, **args)
        self.assertEqual(e["code"], "needs_confirmation", e)
        return e

    def test_rename_asset_is_bad_args(self):
        e = self._err("rename", entity=ROOM, newName="Room")
        self.assertEqual(e["code"], "bad_args")
        self.assertIn("asset", e["message"])

    def test_rename_to_existing_shot_is_bad_args(self):
        self.core.entities.add_shot("sq01", "sh020")
        self.assertEqual(self._err("rename", entity=SH010, newName="sh020")["code"], "bad_args")

    def test_rename_preview_lists_folders_and_dependents(self):
        used = os.path.join(self.shot_dir, "Export", "cam", "v0001", "cam.abc")
        self.core.entities.add_scenefile(ROOM, "Layout", "Layout", "Room_Layout_v0003.ma", version="v0003", deps=[used])
        e = self._token("rename", entity=SH010, newName="sh011")
        changes = e["details"]["changes"]
        self.assertEqual((changes["from"], changes["to"]), ("sq01/sh010", "sq01/sh011"))
        self.assertEqual(changes["folders"], [self.shot_dir.replace("\\", "/")])
        self.assertEqual([d["entity"] for d in changes["dependents"]], [ROOM])
        self.assertIn("Unity", changes["note"])
        self.assertIn("1 scene", e["details"]["summary"])
        self.assertTrue(os.path.isdir(self.shot_dir))

    def test_rename_preview_counts_renamed_names(self):
        # I5: Prism renames every file and folder whose name contains the old name.
        os.makedirs(os.path.join(self.shot_dir, "Scenefiles", "anm"))
        with open(os.path.join(self.shot_dir, "Scenefiles", "anm", "sq01-sh010_anm_v0001.ma"), "w") as f:
            f.write("x")
        changes = self._token("rename", entity=SH010, newName="sh011")["details"]["changes"]
        self.assertEqual(changes["renamedNames"], 2)  # the shot folder and the scene file
        self.assertIn("sq01-sh010_anm_v0001.ma → sq01-sh011_anm_v0001.ma", changes["sample"])

    def test_rename_refuses_partial_name_matches(self):
        # I5: renaming shot "010" would also turn version folder v0010 into v0020.
        self.core.entities.add_shot("sq01", "010")
        shot = {"type": "shot", "sequence": "sq01", "shot": "010"}
        os.makedirs(os.path.join(self.core.getEntityPath(entity=shot), "Export", "cam", "v0010"))
        e = self._err("rename", entity=shot, newName="020")
        self.assertEqual(e["code"], "bad_args")
        self.assertIn("v0010", e["message"])

    def test_rename_shot(self):
        e = self._token("rename", entity=SH010, newName="sh011")
        r = self._ok("rename", entity=SH010, newName="sh011", confirm=e["details"]["confirmToken"])
        self.assertEqual(r["to"], {"type": "shot", "sequence": "sq01", "shot": "sh011"})
        self.assertFalse(os.path.exists(self.shot_dir))
        self.assertTrue(os.path.isdir(self.core.getEntityPath(entity=r["to"])))

    def test_rename_sequence(self):
        seq = {"type": "sequence", "sequence": "sq01"}
        e = self._token("rename", entity=seq, newName="sq10")
        self._ok("rename", entity=seq, newName="sq10", confirm=e["details"]["confirmToken"])
        self.assertTrue(os.path.isdir(self.core.getEntityPath(entity={"type": "shot", "sequence": "sq10", "shot": "sh010"})))

    def test_rename_episode_is_not_supported(self):
        self.assertEqual(self._err("rename", entity={"type": "episode", "episode": "ep01"}, newName="ep02")["code"], "bad_args")

    def test_rename_locked_folder_touches_nothing(self):
        local = self._local()
        e = self._token("rename", entity=SH010, newName="sh011")
        with open(os.path.join(local, "cache.txt"), "rb"):  # an open file blocks renaming its folder on Windows
            e = self._err("rename", entity=SH010, newName="sh011", confirm=e["details"]["confirmToken"])
        self.assertEqual(e["code"], "internal")
        self.assertEqual(os.path.normcase(e["details"]["locked"]), os.path.normcase(local.replace("\\", "/")))
        self.assertTrue(os.path.isdir(self.shot_dir))
        self.assertTrue(os.path.isdir(local))
        leftovers = [n for n in os.listdir(os.path.dirname(self.shot_dir)) + os.listdir(os.path.dirname(local)) if "mcp-lockcheck" in n]
        self.assertEqual(leftovers, [])

    def test_rename_partial_failure_reports_renamed_and_remaining(self):
        local = self._local()
        self.core.entities.fail_rename_after_first = True
        e = self._token("rename", entity=SH010, newName="sh011")
        e = self._err("rename", entity=SH010, newName="sh011", confirm=e["details"]["confirmToken"])
        self.assertEqual(e["code"], "internal")
        new_global = self.core.getEntityPath(entity={"type": "shot", "sequence": "sq01", "shot": "sh011"})
        self.assertEqual(e["details"]["renamed"], [new_global.replace("\\", "/")])
        self.assertEqual(e["details"]["remaining"], [local.replace("\\", "/")])

    def test_delete_shot_moves_to_trash(self):
        e = self._token("delete_shot", entity=SH010)
        self.assertIn("Trash", e["details"]["changes"]["trash"])
        r = self._ok("delete_shot", entity=SH010, confirm=e["details"]["confirmToken"])
        self.assertFalse(os.path.exists(self.shot_dir))
        trashed = os.path.join(r["trash"], "global", "notes.txt")
        self.assertTrue(os.path.isfile(trashed), trashed)
        self.assertTrue(os.path.normcase(r["trash"]).startswith(os.path.normcase(os.path.join(self.core.projectPath, "00_Pipeline", "Trash"))))
        self.assertTrue(os.path.basename(r["trash"]).endswith("_sq01-sh010"))

    def test_delete_shot_forgets_its_shot_info_and_keeps_a_copy_in_trash(self):
        # M9: a new shot with the same name must not inherit the deleted one's range, metadata or preview.
        self.core.entities.setMetaData(SH010, {"mood": {"value": "calm", "show": True}})
        self.core.entities.add_shot("sq01", "sh020", frame_range=(1, 50))
        preview = self.core.entities.getEntityPreviewPath(SH010)
        os.makedirs(os.path.dirname(preview), exist_ok=True)
        with open(preview, "wb") as f:
            f.write(b"jpg")
        e = self._token("delete_shot", entity=SH010)
        self.assertEqual(e["details"]["changes"]["shotInfo"],
                         {"frameRange": [1001, 1100], "metaData": {"mood": {"value": "calm", "show": True}}, "preview": True})
        r = self._ok("delete_shot", entity=SH010, confirm=e["details"]["confirmToken"])
        self.assertIsNone(self.core.entities.getShotRange(SH010))
        self.assertEqual(self.core.entities.getMetaData(SH010), {})
        self.assertFalse(os.path.exists(preview))
        self.assertEqual(self.core.entities.getShotRange({"type": "shot", "sequence": "sq01", "shot": "sh020"}), [1, 50])
        import json
        with open(os.path.join(r["trash"], "shotinfo.json"), encoding="utf-8") as f:
            kept = json.load(f)
        self.assertEqual(kept["frameRange"], [1001, 1100])
        self.assertEqual(kept["metaData"], {"mood": {"value": "calm", "show": True}})
        self.assertTrue(os.path.isfile(os.path.join(r["trash"], os.path.basename(preview))))

    def test_delete_shot_never_calls_prism_delete(self):
        e = self._token("delete_shot", entity=SH010)
        self._ok("delete_shot", entity=SH010, confirm=e["details"]["confirmToken"])  # FakeEntities.deleteShot raises if called

    def test_delete_shot_second_location_failure_rolls_back(self):
        local = self._local()
        e = self._token("delete_shot", entity=SH010)
        with open(os.path.join(local, "cache.txt"), "rb"):
            e = self._err("delete_shot", entity=SH010, confirm=e["details"]["confirmToken"])
        self.assertEqual(e["code"], "internal")
        self.assertEqual(os.path.normcase(e["details"]["locked"]), os.path.normcase(local.replace("\\", "/")))
        self.assertTrue(os.path.isfile(os.path.join(self.shot_dir, "notes.txt")))
        self.assertTrue(os.path.isdir(local))

    def test_delete_shot_lists_dependents_and_unity_note(self):
        used = os.path.join(self.shot_dir, "Export", "cam", "v0001", "cam.abc")
        self.core.entities.add_scenefile(ROOM, "Layout", "Layout", "Room_Layout_v0003.ma", deps=[used])
        changes = self._token("delete_shot", entity=SH010)["details"]["changes"]
        self.assertEqual(len(changes["dependents"]), 1)
        self.assertIn("Unity", changes["note"])

    def test_delete_asset_is_bad_args(self):
        self.assertEqual(self._err("delete_shot", entity=ROOM)["code"], "bad_args")


if __name__ == "__main__":
    unittest.main()
