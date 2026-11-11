import os
import shutil
import tempfile
import unittest

from fakes import FakeCore
from unity_bridge import protocol
from unity_bridge.commands import PrismCommands

LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}


class FakeProducts:
    """Versions v0001..v0003 of lotus_model, each with one FBX on disk."""

    def __init__(self, root):
        self.root = root
        self.latest_calls = []
        self.master_source = None
        self.versions = []
        for i, comment in enumerate(("first", "bigger petals", "stem renamed"), start=1):
            path = os.path.join(root, "v%04d" % i)
            os.makedirs(path)
            with open(os.path.join(path, "lotus_v%d.fbx" % i), "w") as f:
                f.write("fbx")
            self.versions.append({"type": "asset", "asset_path": "Props/Lotus", "product": "lotus_model",
                                  "version": "v%04d" % i, "path": path, "locations": {"global": path},
                                  "_comment": comment})

    def getProductsFromEntity(self, entity, locations=None):
        return [{"product": "lotus_model", "path": self.root}] if entity == LOTUS else []

    def getVersionsFromProduct(self, entity, product, locations="all"):
        return list(self.versions) if (entity == LOTUS and product == "lotus_model") else []

    def getLatestVersionFromProduct(self, product, entity=None, includeMaster=True, wedge=None, locations=None):
        self.latest_calls.append({"product": product, "includeMaster": includeMaster})
        versions = self.getVersionsFromProduct(entity, product)
        return versions[-1] if versions else None

    def getPreferredFileFromVersion(self, version, location=None):
        files = os.listdir(version["path"])
        if not files:
            raise OSError("no files in %s" % version["path"])  # like an offline network drive
        return os.path.join(version["path"], files[0])

    def getVersionInfoFromVersion(self, version):
        return {"comment": version["_comment"], "user": "adm", "date": "11.11.26, 18:00:00"}

    def getProductPreviewPath(self, productPath):
        return productPath + "/preview.jpg"

    def getMasterVersionNumber(self, masterPath, allowCache=True):
        return self.master_source

    def add_master(self, source):
        """Prism's default: 'master' is a copy of a numbered version and sorts as the latest."""
        path = os.path.join(self.root, "master")
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "lotus_master.fbx"), "w") as f:
            f.write("fbx")
        self.master_source = source
        self.versions.append({"type": "asset", "asset_path": "Props/Lotus", "product": "lotus_model", "version": "master",
                              "path": path, "locations": {"global": path}, "_comment": "master"})


class FakeEntities:
    def __init__(self, root):
        self.root = root

    def getEntityPreviewPath(self, entity):
        return os.path.join(self.root, "Assetinfo", entity["asset_path"].split("/")[-1] + "_preview.jpg")


class ProductCore(FakeCore):
    def __init__(self, root):
        super().__init__()
        self.products = FakeProducts(root)
        self.entities = FakeEntities(root)
        self.existing_entities = {"Props/Lotus"}

    def getEntityPath(self, entity=None, **kwargs):
        if entity and entity.get("asset_path") in self.existing_entities:
            return self.products.root
        return os.path.join(self.products.root, "does-not-exist")


class ProductCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.core = ProductCore(self.tmp)
        self.cmds = PrismCommands(self.core, unity=None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, cmd, **args):
        return self.cmds.dispatch(protocol.make_request(cmd, args, "t", False))

    def test_list_products(self):
        resp = self.call("listProducts", entity=LOTUS)
        self.assertEqual(resp["result"], [{"product": "lotus_model", "entity": LOTUS}])

    def test_list_versions(self):
        result = self.call("listVersions", entity=LOTUS, product="lotus_model")["result"]
        self.assertEqual([v["version"] for v in result], ["v0001", "v0002", "v0003"])
        self.assertEqual(result[1]["comment"], "bigger petals")
        self.assertEqual(result[1]["user"], "adm")
        self.assertEqual(result[1]["location"], "global")
        self.assertTrue(result[1]["filepath"].endswith("lotus_v2.fbx"))

    def test_resolve_latest_uses_include_master(self):
        result = self.call("resolveVersion", entity=LOTUS, product="lotus_model")["result"]
        self.assertEqual(result["version"], "v0003")
        self.assertTrue(result["filepath"].endswith("lotus_v3.fbx"))
        self.assertEqual(result["location"], "global")
        self.assertEqual(result["comment"], "stem renamed")
        self.assertEqual(self.core.products.latest_calls, [{"product": "lotus_model", "includeMaster": True}])

    def test_resolve_specific_version(self):
        result = self.call("resolveVersion", entity=LOTUS, product="lotus_model", version="v0002")["result"]
        self.assertEqual(result["version"], "v0002")
        self.assertTrue(result["filepath"].endswith("lotus_v2.fbx"))

    def test_resolve_missing_version_source_unavailable(self):
        resp = self.call("resolveVersion", entity=LOTUS, product="lotus_model", version="v0009")
        self.assertEqual(resp["error"]["code"], "source_unavailable")

    def test_resolve_unknown_product_source_unavailable(self):
        resp = self.call("resolveVersion", entity=LOTUS, product="nope")
        self.assertEqual(resp["error"]["code"], "source_unavailable")

    def test_resolve_file_missing_on_disk(self):
        shutil.rmtree(self.core.products.versions[2]["path"])
        os.makedirs(self.core.products.versions[2]["path"])
        with open(os.path.join(self.core.products.versions[2]["path"], "gone.fbx"), "w"):
            pass
        os.remove(os.path.join(self.core.products.versions[2]["path"], "gone.fbx"))
        resp = self.call("resolveVersion", entity=LOTUS, product="lotus_model")
        self.assertEqual(resp["error"]["code"], "source_unavailable")

    def test_check_versions_marks_outdated(self):
        records = [{"id": "Props__Lotus__lotus_model", "entity": LOTUS, "product": "lotus_model", "version": "v0001"}]
        result = self.call("checkVersions", records=records)["result"]
        self.assertEqual(result, [{"id": "Props__Lotus__lotus_model", "current": "v0001", "latest": "v0003",
                                   "currentContent": "v0001", "latestContent": "v0003",
                                   "entity": LOTUS, "product": "lotus_model"}])

    def test_check_versions_up_to_date_empty(self):
        records = [{"id": "Props__Lotus__lotus_model", "entity": LOTUS, "product": "lotus_model", "version": "v0003"}]
        self.assertEqual(self.call("checkVersions", records=records)["result"], [])

    def test_resolve_master_reports_its_content_version(self):
        self.core.products.add_master("v0002")
        result = self.call("resolveVersion", entity=LOTUS, product="lotus_model")["result"]
        self.assertEqual(result["version"], "master")
        self.assertEqual(result["contentVersion"], "v0002")

    def test_numbered_version_content_is_itself(self):
        result = self.call("resolveVersion", entity=LOTUS, product="lotus_model", version="v0002")["result"]
        self.assertEqual(result["contentVersion"], "v0002")

    def test_imported_master_is_outdated_when_master_moves(self):
        self.core.products.add_master("v0003")
        records = [{"id": "r", "entity": LOTUS, "product": "lotus_model", "version": "master", "contentVersion": "v0002"}]
        result = self.call("checkVersions", records=records)["result"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["latest"], "master")
        self.assertEqual(result[0]["latestContent"], "v0003")

    def test_imported_master_up_to_date(self):
        self.core.products.add_master("v0003")
        records = [{"id": "r", "entity": LOTUS, "product": "lotus_model", "version": "master", "contentVersion": "v0003"}]
        self.assertEqual(self.call("checkVersions", records=records)["result"], [])

    def test_numbered_import_equal_to_master_content_is_up_to_date(self):
        self.core.products.add_master("v0003")
        records = [{"id": "r", "entity": LOTUS, "product": "lotus_model", "version": "v0003"}]
        self.assertEqual(self.call("checkVersions", records=records)["result"], [])

    def write(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"jpg")
        return path

    def test_resolve_includes_product_preview(self):
        preview = self.write(os.path.join(self.core.products.versions[1]["path"], "preview.jpg"))
        result = self.call("resolveVersion", entity=LOTUS, product="lotus_model", version="v0002")["result"]
        self.assertEqual(result["previewPath"], preview.replace("\\", "/"))

    def test_resolve_falls_back_to_entity_preview(self):
        preview = self.write(os.path.join(self.tmp, "Assetinfo", "Lotus_preview.jpg"))
        result = self.call("resolveVersion", entity=LOTUS, product="lotus_model", version="v0002")["result"]
        self.assertEqual(result["previewPath"], preview.replace("\\", "/"))

    def test_resolve_without_preview_is_empty_string(self):
        result = self.call("resolveVersion", entity=LOTUS, product="lotus_model")["result"]
        self.assertEqual(result["previewPath"], "")

    def test_check_versions_reports_missing_product(self):
        records = [{"id": "Props__Lotus__gone", "entity": LOTUS, "product": "gone", "version": "v0001"}]
        result = self.call("checkVersions", records=records)["result"]
        self.assertEqual(result, [{"id": "Props__Lotus__gone", "missing": True, "entity": LOTUS, "product": "gone"}])

    def test_check_versions_skips_unreachable_project(self):
        offline = {"type": "asset", "asset_path": "Props/OnOfflineDrive"}
        records = [{"id": "x", "entity": offline, "product": "gone", "version": "v0001"}]
        self.assertEqual(self.call("checkVersions", records=records)["result"], [])

    def test_reachable_entity_without_the_product_is_reported_missing(self):
        # v1 skipped this case; a reachable entity without the product means it was removed from Prism.
        records = [{"id": "x", "entity": LOTUS, "product": "nope", "version": "v0001"}]
        self.assertEqual(self.call("checkVersions", records=records)["result"][0]["missing"], True)


if __name__ == "__main__":
    unittest.main()
