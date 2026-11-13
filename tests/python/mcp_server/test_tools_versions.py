import unittest

import prism_mcp.tools_versions  # noqa: F401  (registers the tools)

from mcp_server.fake_core import call, make_project_core, make_session

LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}
SH010 = {"type": "shot", "sequence": "sq01", "shot": "sh010"}


class VersionToolsTests(unittest.TestCase):
    def setUp(self):
        self.core = make_project_core()
        self.core.entities.add_asset("Props/Lotus")
        self.core.entities.add_shot("sq01", "sh010")
        self.core.products.add_product(LOTUS, "lotus_model", ["v0001", "v0002", "v0003"],
                                       comments={"v0002": "bigger petals"}, master="v0002")
        self.session = make_session(self.core)

    def _ok(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertTrue(r["ok"], r)
        return r["result"]

    def _err(self, tool, **args):
        r = call(self.session, tool, **args)
        self.assertFalse(r["ok"], r)
        return r["error"]

    def _confirmed(self, tool, **args):
        e = self._err(tool, **args)
        self.assertEqual(e["code"], "needs_confirmation", e)
        return self._ok(tool, confirm=e["details"]["confirmToken"], **args), e

    def test_set_master_needs_confirmation_then_updates(self):
        e = self._err("set_master", entity=LOTUS, product="lotus_model", version="v0003")
        self.assertEqual(e["code"], "needs_confirmation")
        self.assertEqual(e["details"]["changes"], {"from": "v0002", "to": "v0003"})
        self.assertIn("v0002", e["details"]["summary"])
        self.assertEqual(self.core.products.masters[("Props/Lotus", "lotus_model")], "v0002")
        r, _ = self._confirmed("set_master", entity=LOTUS, product="lotus_model", version="v0003")
        self.assertTrue(r["changed"])
        self.assertEqual(self.core.products.masters[("Props/Lotus", "lotus_model")], "v0003")

    def test_set_master_token_tracks_current_master(self):
        token = self._err("set_master", entity=LOTUS, product="lotus_model", version="v0003")["details"]["confirmToken"]
        self.core.products.masters[("Props/Lotus", "lotus_model")] = "v0001"  # someone else changed it meanwhile
        e = self._err("set_master", entity=LOTUS, product="lotus_model", version="v0003", confirm=token)
        self.assertEqual(e["code"], "needs_confirmation")
        self.assertEqual(e["details"]["changes"]["from"], "v0001")
        self.assertEqual(self.core.products.masters[("Props/Lotus", "lotus_model")], "v0001")

    def test_set_master_already_master_is_noop(self):
        self.assertFalse(self._ok("set_master", entity=LOTUS, product="lotus_model", version="v0002")["changed"])

    def test_set_master_missing_file_stops_before_asking(self):
        # M4: Prism would copy nothing and still call it the master.
        import os
        path = self.core.products.getPreferredFileFromVersion(dict(LOTUS, product="lotus_model", version="v0003"))
        os.remove(path)
        e = self._err("set_master", entity=LOTUS, product="lotus_model", version="v0003")
        self.assertEqual(e["code"], "source_unavailable")
        self.assertIn("v0003", e["message"])
        self.assertEqual(self.core.products.masters[("Props/Lotus", "lotus_model")], "v0002")

    def test_set_master_unknown_version_lists_versions(self):
        e = self._err("set_master", entity=LOTUS, product="lotus_model", version="v0009")
        self.assertEqual(e["code"], "bad_args")
        self.assertIn("v0003", e["message"])

    def test_set_master_needs_exactly_one_of_product_identifier(self):
        self.assertEqual(self._err("set_master", entity=LOTUS, version="v0001")["code"], "bad_args")
        self.assertEqual(self._err("set_master", entity=LOTUS, product="lotus_model", identifier="pb", version="v0001")["code"], "bad_args")

    def test_set_master_for_media(self):
        import os
        folders = [os.path.join(self.core.root, "pb", v) for v in ("v0001", "v0002")]
        for folder in folders:
            os.makedirs(folder)
        self.core.mediaProducts.add_media(SH010, "playblast", "Animation_pb", [
            {"version": "v0001", "path": folders[0], "comment": ""},
            {"version": "v0002", "path": folders[1], "comment": ""}])
        r, e = self._confirmed("set_master", entity=SH010, identifier="Animation_pb", version="v0002")
        self.assertEqual(e["details"]["changes"], {"from": None, "to": "v0002"})
        vs = self.core.mediaProducts.media["sq01/sh010"]["playblast"]["Animation_pb"]
        self.assertEqual(next(v for v in vs if v["version"] == "master")["content"], "v0002")

    def test_delete_master_without_master_is_noop(self):
        self.core.products.add_product(LOTUS, "lotus_rig", ["v0001"])
        self.assertFalse(self._ok("delete_master", entity=LOTUS, product="lotus_rig")["changed"])

    def test_delete_master(self):
        r, e = self._confirmed("delete_master", entity=LOTUS, product="lotus_model")
        self.assertEqual(e["details"]["changes"], {"master": "v0002"})
        self.assertTrue(r["changed"])
        self.assertNotIn(("Props/Lotus", "lotus_model"), self.core.products.masters)

    def test_delete_master_failure_is_internal(self):
        self.core.products.fail_delete = True
        e = self._err("delete_master", entity=LOTUS, product="lotus_model")
        e = self._err("delete_master", entity=LOTUS, product="lotus_model", confirm=e["details"]["confirmToken"])
        self.assertEqual(e["code"], "internal")

    def test_set_comment_on_empty_skips_confirmation(self):
        target = {"entity": LOTUS, "product": "lotus_model", "version": "v0001"}
        self.assertTrue(self._ok("set_comment", target=target, comment="first sculpt")["changed"])
        folder = self.core.products._folder(LOTUS, "lotus_model", "v0001")
        self.assertEqual(self.core.products.info[folder]["comment"], "first sculpt")

    def test_set_comment_overwrite_confirms_product_version(self):
        target = {"entity": LOTUS, "product": "lotus_model", "version": "v0002"}
        r, e = self._confirmed("set_comment", target=target, comment="bigger petals, approved")
        self.assertEqual(e["details"]["changes"], {"from": "bigger petals", "to": "bigger petals, approved"})
        folder = self.core.products._folder(LOTUS, "lotus_model", "v0002")
        self.assertEqual(self.core.products.info[folder]["comment"], "bigger petals, approved")

    def test_set_comment_overwrite_confirms_scenefile(self):
        path = self.core.entities.add_scenefile(LOTUS, "mod", "Sculpt", "Lotus_Sculpt_v0001.ma", comment="wip")
        r, e = self._confirmed("set_comment", target={"scenefile": path}, comment="final")
        self.assertEqual(self.core.entities.getScenefileData(path)["comment"], "final")

    def test_set_comment_media(self):
        self.core.mediaProducts.add_media(SH010, "playblast", "Animation_pb", [{"version": "v0001", "path": "X:/pb/v0001", "comment": ""}])
        self._ok("set_comment", target={"entity": SH010, "identifier": "Animation_pb", "version": "v0001"}, comment="for review")
        self.assertEqual(self.core.mediaProducts.media["sq01/sh010"]["playblast"]["Animation_pb"][0]["comment"], "for review")

    def test_set_comment_bad_target(self):
        self.assertEqual(self._err("set_comment", target={"entity": LOTUS}, comment="x")["code"], "bad_args")

    def test_omit_and_unomit(self):
        self._confirmed("omit", entity=LOTUS)
        self.assertIn("Props/Lotus", self.core.entities.omitted)
        self.assertFalse(self._ok("omit", entity=LOTUS)["changed"])
        self._confirmed("unomit", entity=LOTUS)
        self.assertNotIn("Props/Lotus", self.core.entities.omitted)

    def test_omit_sequence_is_bad_args(self):
        self.assertEqual(self._err("omit", entity={"type": "sequence", "sequence": "sq01"})["code"], "bad_args")


if __name__ == "__main__":
    unittest.main()
