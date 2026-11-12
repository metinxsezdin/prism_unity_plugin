"""Creates the Prism test project used by the integration and E2E tests.

Run with Prism's Python:
    "C:\\Program Files\\Prism2\\Python313\\python.exe" tools/make_test_prism_project.py ["<target folder>"]

Default target: %USERPROFILE%\\PrismUnityTest Project (the space is intentional).
Creates assets Props/Lotus, Props/Çay Bardağı and Scenes/MeditationRoom, and publishes
lotus_model v0001..v0003 and cay_model v0001 from the fixture FBX files.
The user's "current project" setting is restored afterwards.
Prints the project's pipeline.json path on the last line.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "Unity", "UnityPackage", "com.prism.unity", "Tests", "Editor", "Fixtures~")
PRISM_ROOT = os.environ.get("PRISM_ROOT", r"C:\Program Files\Prism2")
sys.path.insert(0, os.path.join(PRISM_ROOT, "Scripts"))

import PrismCore  # noqa: E402
from qtpy.QtWidgets import QApplication  # noqa: E402

PROJECT_NAME = "PrismUnityTest"
LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}
CAY = {"type": "asset", "asset_path": "Props/Çay Bardağı"}
ROOM = {"type": "asset", "asset_path": "Scenes/MeditationRoom"}


def main():
    target = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "PrismUnityTest Project"))
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841  (Prism needs a Qt app)
    core = PrismCore.create(app="Standalone", prismArgs=["noUI", "silent"])
    previous = core.getConfig("globals", "current project")

    try:
        config = os.path.join(target, "00_Pipeline", "pipeline.json")
        if not os.path.exists(config):
            result = core.projects.createProject(name=PROJECT_NAME, path=target)
            if not result:
                raise SystemExit("Prism could not create the project at %s" % target)
        core.changeProject(config)

        for entity in (LOTUS, CAY, ROOM):
            if not os.path.exists(core.getEntityPath(entity=entity)):
                core.entities.createEntity(entity, silent=True)

        def publish(entity, product, files, comment):
            have = [v.get("version") for v in core.products.getVersionsFromProduct(entity, product)]
            version = "v%04d" % (len(have) + 1)
            core.products.ingestProductVersion(files, entity, product, comment=comment, version=version)
            print("published %s %s %s" % (entity["asset_path"], product, version))

        existing = [v.get("version") for v in core.products.getVersionsFromProduct(LOTUS, "lotus_model")]
        for name, comment in (("lotus_v1.fbx", "first model"), ("lotus_v2.fbx", "bigger petals"),
                              ("lotus_v3_renamed.fbx", "stem renamed, stem material removed")):
            if len(existing) >= 3:
                break
            publish(LOTUS, "lotus_model", [os.path.join(FIXTURES, name)], comment)
            existing.append(name)
        if not core.products.getVersionsFromProduct(CAY, "cay_model"):
            publish(CAY, "cay_model", [os.path.join(FIXTURES, "cay_v1.fbx")], "first cup")

        # A product preview for lotus_model v0002 (solid red, 64x64): the packaging tests check
        # that Unity's thumbnail comes from Prism's preview.
        from qtpy.QtGui import QColor, QPixmap

        v2 = next(v for v in core.products.getVersionsFromProduct(LOTUS, "lotus_model") if v.get("version") == "v0002")
        if not os.path.isfile(core.products.getProductPreviewPath(v2["path"])):
            pixmap = QPixmap(64, 64)
            pixmap.fill(QColor(255, 0, 0))
            core.products.setProductPreview(v2["path"], pixmap)
            print("wrote preview for lotus_model v0002")
    finally:
        if previous:
            core.setConfig("globals", "current project", previous)

    print(config.replace("\\", "/"))


if __name__ == "__main__":
    main()
