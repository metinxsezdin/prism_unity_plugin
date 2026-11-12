import datetime
import os
import time
import unittest

import prism_mcp.reports  # noqa: F401  (registers the tool)

from mcp_server.fake_core import call, make_project_core, make_session

LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}
CAY = {"type": "asset", "asset_path": "Props/Çay Bardağı"}
ROOM = {"type": "asset", "asset_path": "Scenes/MeditationRoom"}
SH010 = {"type": "shot", "sequence": "sq01", "shot": "sh010"}


def age(path, days):
    t = time.time() - days * 86400
    os.utime(path, (t, t))


class ReportsTests(unittest.TestCase):
    def setUp(self):
        self.core = make_project_core()
        e = self.core.entities
        for a in ("Props/Lotus", "Props/Çay Bardağı", "Scenes/MeditationRoom"):
            e.add_asset(a)
        e.add_shot("sq01", "sh010")
        p = self.core.products
        p.add_product(LOTUS, "lotus_model", ["v0001", "v0002", "v0003"], master="v0002")
        p.add_product(CAY, "cay_model", ["v0001"], master="v0001")
        p.add_product(CAY, "cay_rig", ["v0001", "v0002"])
        for folder in p.info:
            age(folder, 40)
        self.session = make_session(self.core)

    def _report(self, **args):
        r = call(self.session, "report", **args)
        self.assertTrue(r["ok"], r)
        return r["result"]

    def test_unknown_kind_is_bad_args(self):
        r = call(self.session, "report", kind="everything")
        self.assertEqual(r["error"]["code"], "bad_args")
        for kind in ("recent_activity", "missing_products", "master_behind", "empty_tasks"):
            self.assertIn(kind, r["error"]["message"])

    def test_recent_activity_uses_mtime_and_groups_by_user(self):
        e = self.core.entities
        fresh = e.add_scenefile(LOTUS, "Modeling", "Sculpt", "Lotus_Sculpt_v0002.ma", version="v0002", user="mke", comment="petals")
        old = e.add_scenefile(LOTUS, "Modeling", "Sculpt", "Lotus_Sculpt_v0001.ma", user="mke")
        age(fresh, 2)
        age(old, 30)
        age(os.path.dirname(self.core.products.getPreferredFileFromVersion(dict(LOTUS, product="lotus_model", version="v0003"))), 1)
        r = self._report(kind="recent_activity")
        self.assertEqual([(i["kind"], i["version"]) for i in r["items"]], [("product", "v0003"), ("scenefile", "v0002")])
        self.assertEqual(r["items"][1]["comment"], "petals")
        self.assertEqual(r["items"][0]["name"], "lotus_model")
        self.assertEqual(r["byUser"], {"aka": 1, "mke": 1})

    def test_recent_activity_since(self):
        old = self.core.entities.add_scenefile(LOTUS, "Modeling", "Sculpt", "Lotus_Sculpt_v0001.ma")
        age(old, 30)
        since = (datetime.date.today() - datetime.timedelta(days=35)).isoformat()
        self.assertEqual([i["kind"] for i in self._report(kind="recent_activity", since=since)["items"]], ["scenefile"])
        self.assertEqual(call(self.session, "report", kind="recent_activity", since="last week")["error"]["code"], "bad_args")

    def test_missing_products_pattern(self):
        items = self._report(kind="missing_products", product="*_model")["items"]
        self.assertEqual(items, [{"entity": ROOM, "products": []}])
        items = self._report(kind="missing_products", product="*_rig", category="Props")["items"]
        self.assertEqual(items, [{"entity": LOTUS, "products": ["lotus_model"]}])

    def test_master_behind_lists_missing_and_old_masters(self):
        items = self._report(kind="master_behind")["items"]
        self.assertEqual(items, [
            {"entity": LOTUS, "product": "lotus_model", "latest": "v0003", "master": "v0002"},
            {"entity": CAY, "product": "cay_rig", "latest": "v0002", "master": None},
        ])

    def test_empty_tasks(self):
        e = self.core.entities
        e.add_scenefile(LOTUS, "Modeling", "Sculpt", "Lotus_Sculpt_v0001.ma")
        e.steps["Props/Lotus"]["Modeling"].append("Retopo")
        e.steps["sq01/sh010"] = {"Animation": ["Blocking"]}
        items = self._report(kind="empty_tasks")["items"]
        self.assertEqual(items, [
            {"entity": LOTUS, "department": "Modeling", "task": "Retopo"},
            {"entity": SH010, "department": "Animation", "task": "Blocking"},
        ])

    def test_find_dependents_matches_entity_root_case_insensitively(self):
        from prism_mcp.reports import find_dependents

        shot_root = self.core.getEntityPath(entity=SH010)
        used = os.path.join(shot_root, "Export", "cam", "v0001", "cam.abc").upper()
        e = self.core.entities
        e.add_scenefile(ROOM, "Layout", "Layout", "Room_Layout_v0003.ma", version="v0003", user="mke", deps=[used])
        e.add_scenefile(LOTUS, "Modeling", "Sculpt", "Lotus_Sculpt_v0001.ma", deps=["X:/elsewhere/a.fbx"])
        e.add_scenefile(SH010, "Animation", "Blocking", "sh010_v0001.ma", deps=[used])  # inside the shot: moves with it
        found = find_dependents(self.session, shot_root)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["entity"], ROOM)
        self.assertEqual(found[0]["version"], "v0003")
        self.assertEqual(found[0]["user"], "mke")
        self.assertTrue(found[0]["scenefile"].endswith("Room_Layout_v0003.ma"))


if __name__ == "__main__":
    unittest.main()
