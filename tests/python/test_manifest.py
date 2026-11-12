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

    # --- embedded packages (copied into the Unity project, shared through Git) ---

    def make_plugin(self):
        plugin = os.path.join(self.tmp, "Plugin Dir")
        for name in ("com.prism.unity", "com.prism.assets"):
            folder = os.path.join(plugin, "UnityPackage", name)
            os.makedirs(os.path.join(folder, "Editor"), exist_ok=True)
            with open(os.path.join(folder, "package.json"), "w") as f:
                json.dump({"name": name, "version": "0.2.0"}, f)
            with open(os.path.join(folder, "Editor", "Code.cs"), "w") as f:
                f.write("// code")
        return plugin

    def test_install_embedded_copies_both_packages(self):
        make_unity_project(self.project)
        installed = manifest.install_embedded(self.project, self.make_plugin())
        self.assertEqual(sorted(installed), ["com.prism.assets", "com.prism.unity"])
        for name in installed:
            self.assertTrue(os.path.isfile(os.path.join(self.project, "Packages", name, "package.json")))
            self.assertTrue(os.path.isfile(os.path.join(self.project, "Packages", name, "Editor", "Code.cs")))

    def test_install_embedded_removes_machine_specific_file_entry(self):
        make_unity_project(self.project)
        manifest.add_package(self.project, self.package)  # what v1 wrote
        manifest.install_embedded(self.project, self.make_plugin())
        deps = read_manifest(self.project)["dependencies"]
        self.assertNotIn("com.prism.unity", deps)
        self.assertNotIn("com.prism.assets", deps)
        self.assertEqual(deps["com.unity.timeline"], "1.8.12")

    def test_install_embedded_replaces_old_copy(self):
        make_unity_project(self.project)
        plugin = self.make_plugin()
        manifest.install_embedded(self.project, plugin)
        stale = os.path.join(self.project, "Packages", "com.prism.unity", "Editor", "Removed.cs")
        with open(stale, "w") as f:
            f.write("// from an older version")
        manifest.install_embedded(self.project, plugin)
        self.assertFalse(os.path.exists(stale))

    def test_install_embedded_turkish_path(self):
        project = os.path.join(self.tmp, "Wellness Proje Ğüşİ")
        make_unity_project(project)
        self.assertEqual(len(manifest.install_embedded(project, self.make_plugin())), 2)

    def test_remove_embedded(self):
        make_unity_project(self.project)
        manifest.install_embedded(self.project, self.make_plugin())
        self.assertTrue(manifest.remove_embedded(self.project))
        self.assertFalse(os.path.exists(os.path.join(self.project, "Packages", "com.prism.unity")))
        self.assertFalse(manifest.remove_embedded(self.project))

    def test_install_embedded_leaves_out_tests(self):
        # The package's tests delete Assets/Prism and the Addressables settings in their teardown:
        # they must never reach a team project.
        make_unity_project(self.project)
        plugin = self.make_plugin()
        tests = os.path.join(plugin, "UnityPackage", "com.prism.unity", "Tests")
        os.makedirs(os.path.join(tests, "Editor"))
        with open(os.path.join(tests, "Editor", "Danger.cs"), "w") as f:
            f.write("// deletes Assets/Prism")
        with open(tests + ".meta", "w") as f:
            f.write("guid: 1")
        manifest.install_embedded(self.project, plugin)
        target = os.path.join(self.project, "Packages", "com.prism.unity")
        self.assertFalse(os.path.exists(os.path.join(target, "Tests")))
        self.assertFalse(os.path.exists(os.path.join(target, "Tests.meta")))
        self.assertTrue(os.path.isfile(os.path.join(target, "Editor", "Code.cs")))

    def test_remove_embedded_keeps_runtime_package(self):
        # Game code references Prism.Assets; removing the integration must not break it.
        make_unity_project(self.project)
        manifest.install_embedded(self.project, self.make_plugin())
        manifest.remove_embedded(self.project)
        self.assertFalse(os.path.exists(os.path.join(self.project, "Packages", "com.prism.unity")))
        self.assertTrue(os.path.isfile(os.path.join(self.project, "Packages", "com.prism.assets", "package.json")))

    def test_write_project_binding_stores_project_name(self):
        make_unity_project(self.project)
        config = os.path.join(self.tmp, "Wellness", "00_Pipeline", "pipeline.json")
        os.makedirs(os.path.dirname(config))
        with open(config, "w", encoding="utf-8") as f:
            json.dump({"globals": {"project_name": "Wellness"}}, f)
        manifest.write_project_binding(self.project, config)
        path = os.path.join(self.project, "ProjectSettings", "PrismUnity", "project.json")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["projectName"], "Wellness")

    def test_write_project_binding(self):
        make_unity_project(self.project)
        manifest.write_project_binding(self.project, r"M:\Wellness\00_Pipeline\pipeline.json")
        path = os.path.join(self.project, "ProjectSettings", "PrismUnity", "project.json")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"prismProjectConfig": "M:/Wellness/00_Pipeline/pipeline.json"})


if __name__ == "__main__":
    unittest.main()
