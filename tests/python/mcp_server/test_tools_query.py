import os
import unittest

import prism_mcp.tools_query  # noqa: F401  (registers the tools)

from mcp_server.fake_core import call, make_project_core, make_session

LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}
CAY = {"type": "asset", "asset_path": "Props/Çay Bardağı"}
SH010 = {"type": "shot", "sequence": "sq01", "shot": "sh010"}


class QueryToolsTests(unittest.TestCase):
    def setUp(self):
        self.core = make_project_core()
        e = self.core.entities
        e.add_asset("Props/Lotus")
        e.add_asset("Props/Çay Bardağı")
        e.add_asset("Props/Old Vase", omitted=True)
        e.add_shot("sq01", "sh010", frame_range=(1001, 1100))
        self.core.products.add_product(LOTUS, "lotus_model", ["v0001", "v0002", "v0003"],
                                       comments={"v0002": "bigger petals"}, master="v0002")
        self.session = make_session(self.core)

    def _ok(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertTrue(r["ok"], r)
        return r["result"]

    def test_list_entities_assets_hides_omitted_by_default(self):
        items = self._ok("list_entities")["items"]
        self.assertEqual([i["entity"]["asset_path"] for i in items], ["Props/Lotus", "Props/Çay Bardağı"])
        self.assertTrue(all(i["omitted"] is False for i in items))
        items = self._ok("list_entities", includeOmitted=True)["items"]
        self.assertEqual({i["entity"]["asset_path"]: i["omitted"] for i in items}["Props/Old Vase"], True)

    def test_list_entities_filters_by_path_and_contains(self):
        self.core.entities.add_asset("Chars/Monk")
        self.assertEqual([i["entity"]["asset_path"] for i in self._ok("list_entities", path="chars")["items"]], ["Chars/Monk"])
        self.assertEqual([i["entity"]["asset_path"] for i in self._ok("list_entities", contains="çay")["items"]], ["Props/Çay Bardağı"])

    def test_list_entities_shots(self):
        items = self._ok("list_entities", type="shot")["items"]
        self.assertEqual(items, [{"entity": SH010, "omitted": False}])

    def test_list_limit_truncates(self):
        r = self._ok("list_entities", limit=1)
        self.assertEqual(len(r["items"]), 1)
        self.assertTrue(r["truncated"])
        self.assertFalse(self._ok("list_entities")["truncated"])

    def test_get_entity_collects_departments_and_tasks(self):
        e = self.core.entities
        e.add_scenefile(LOTUS, "Modeling", "Sculpt", "Lotus_Sculpt_v0001.ma")
        e.add_scenefile(LOTUS, "Modeling", "Retopo", "Lotus_Retopo_v0001.blend")
        e.descriptions["Lotus"] = "Pink lotus for the meditation room"
        e.metadata["Props/Lotus"] = {"polycount": {"value": "12k"}}
        r = self._ok("get_entity", entity=LOTUS)
        self.assertEqual(r["entity"], LOTUS)
        self.assertEqual(r["departments"], [{"name": "Modeling", "tasks": ["Sculpt", "Retopo"]}])
        self.assertEqual(r["description"], "Pink lotus for the meditation room")
        self.assertEqual(r["metaData"], {"polycount": {"value": "12k"}})
        self.assertIsNone(r["previewPath"])
        self.assertFalse(r["omitted"])
        self.assertEqual(self._ok("get_entity", entity=SH010)["frameRange"], [1001, 1100])

    def test_get_entity_unknown_is_bad_args(self):
        r = call(self.session, "get_entity", entity={"type": "asset", "asset_path": "Props/Nope"})
        self.assertEqual(r["error"]["code"], "bad_args")

    def test_list_scenefiles_detects_app_from_extension(self):
        e = self.core.entities
        e.add_scenefile(LOTUS, "Modeling", "Sculpt", "Lotus_Sculpt_v0001.ma", comment="blockout", user="mke")
        e.add_scenefile(LOTUS, "Modeling", "Retopo", "Lotus_Retopo_v0002.blend", version="v0002")
        items = self._ok("list_scenefiles", entity=LOTUS)["items"]
        self.assertEqual([(i["task"], i["app"], i["version"]) for i in items], [("Sculpt", "Maya", "v0001"), ("Retopo", "Blender", "v0002")])
        self.assertEqual(items[0]["comment"], "blockout")
        self.assertEqual(items[0]["user"], "mke")
        self.assertTrue(items[0]["date"])
        self.assertEqual([i["task"] for i in self._ok("list_scenefiles", entity=LOTUS, task="Retopo")["items"]], ["Retopo"])

    def test_list_products(self):
        self.assertEqual(self._ok("list_products", entity=LOTUS)["items"], [{"product": "lotus_model", "entity": LOTUS}])

    def test_list_versions_marks_master(self):
        items = self._ok("list_versions", entity=LOTUS, product="lotus_model")["items"]
        self.assertEqual({i["version"]: i["isMaster"] for i in items},
                         {"v0001": False, "v0002": True, "v0003": False, "master": True})
        self.assertEqual(next(i for i in items if i["version"] == "v0002")["comment"], "bigger petals")

    def test_list_media_flattens_identifiers(self):
        self.core.mediaProducts.add_media(SH010, "playblast", "Animation_pb", [
            {"version": "v0001", "comment": "first pass", "user": "aka", "date": "02.11.26", "path": "X:/pb/v0001"}])
        items = self._ok("list_media", entity=SH010)["items"]
        self.assertEqual(items, [{"kind": "playblast", "identifier": "Animation_pb", "versions": [
            {"version": "v0001", "comment": "first pass", "user": "aka", "date": "02.11.26", "path": "X:/pb/v0001"}]}])

    def test_get_dependencies(self):
        path = self.core.entities.add_scenefile(LOTUS, "Modeling", "Sculpt", "Lotus_Sculpt_v0001.ma", deps=["X:/a.fbx"])
        self.assertEqual(self._ok("get_dependencies", scenefile=path)["dependencies"], ["X:/a.fbx"])

    def test_get_dependencies_missing_file_is_source_unavailable(self):
        r = call(self.session, "get_dependencies", scenefile=os.path.join(self.core.root, "gone.ma"))
        self.assertEqual(r["error"]["code"], "source_unavailable")

    def test_bad_entity_shape_is_bad_args(self):
        self.assertEqual(call(self.session, "get_entity", entity={"type": "asset"})["error"]["code"], "bad_args")
        self.assertEqual(call(self.session, "list_products", entity="Props/Lotus")["error"]["code"], "bad_args")


if __name__ == "__main__":
    unittest.main()
