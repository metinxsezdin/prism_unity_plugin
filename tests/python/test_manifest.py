import json
import os
import shutil
import tempfile
import unittest
from collections import OrderedDict

from unity_bridge import manifest


def make_unity_project(root, deps=None, extra=None):
    os.makedirs(os.path.join(root, "ProjectSettings"))
    os.makedirs(os.path.join(root, "Packages"))
    with open(os.path.join(root, "ProjectSettings", "ProjectVersion.txt"), "w") as f:
        f.write("m_EditorVersion: 6000.5.6f1\n")
    data = OrderedDict([("dependencies", OrderedDict(deps or [("com.unity.timeline", "1.8.12"), ("com.unity.ugui", "2.5.0")]))])
    for k, v in (extra or {}).items():
        data[k] = v
    with open(os.path.join(root, "Packages", "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_manifest(root):
    with open(os.path.join(root, "Packages", "manifest.json"), encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = os.path.join(self.tmp, "Proj")
        self.package = os.path.join(self.tmp, "Plugin", "UnityPackage", "com.prism.unity")
        os.makedirs(self.package)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_is_unity_project(self):
        self.assertFalse(manifest.is_unity_project(self.project))
        make_unity_project(self.project)
        self.assertTrue(manifest.is_unity_project(self.project))

    def test_add_package_preserves_other_entries(self):
        registries = [{"name": "Example", "url": "https://example.invalid", "scopes": ["com.example"]}]
        make_unity_project(self.project, extra={"scopedRegistries": registries})
        self.assertTrue(manifest.add_package(self.project, self.package))
        data = read_manifest(self.project)
        self.assertEqual(data["scopedRegistries"], registries)
        deps = data["dependencies"]
        self.assertEqual(list(deps)[1:], ["com.unity.timeline", "com.unity.ugui"])
        self.assertEqual(deps["com.unity.timeline"], "1.8.12")
        self.assertEqual(deps["com.prism.unity"], "file:" + os.path.abspath(self.package).replace("\\", "/"))

    def test_add_package_idempotent(self):
        make_unity_project(self.project)
        manifest.add_package(self.project, self.package)
        before = read_manifest(self.project)
        manifest.add_package(self.project, self.package)
        self.assertEqual(read_manifest(self.project), before)
        self.assertEqual(list(before["dependencies"]).count("com.prism.unity"), 1)

    def test_remove_package(self):
        make_unity_project(self.project)
        manifest.add_package(self.project, self.package)
        self.assertTrue(manifest.remove_package(self.project))
        self.assertNotIn("com.prism.unity", read_manifest(self.project)["dependencies"])
        self.assertFalse(manifest.remove_package(self.project))

    def test_rejects_non_unity_folder(self):
        os.makedirs(self.project)
        with self.assertRaises(ValueError):
            manifest.add_package(self.project, self.package)

    def test_paths_with_spaces_and_turkish_chars(self):
        project = os.path.join(self.tmp, "Wellness Proje Ğüşİ")
        make_unity_project(project)
        manifest.add_package(project, self.package)
        entry = read_manifest(project)["dependencies"]["com.prism.unity"]
        self.assertTrue(entry.startswith("file:"))
        self.assertNotIn("\\", entry)

    def test_write_project_binding(self):
        make_unity_project(self.project)
        manifest.write_project_binding(self.project, r"M:\Wellness\00_Pipeline\pipeline.json")
        path = os.path.join(self.project, "ProjectSettings", "PrismUnity", "project.json")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"prismProjectConfig": "M:/Wellness/00_Pipeline/pipeline.json"})


if __name__ == "__main__":
    unittest.main()
