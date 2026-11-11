import os
import unittest

import prism_env  # noqa: F401  (adds Prism paths)


@unittest.skipUnless(prism_env.PRISM_AVAILABLE, "Prism is not installed")
class PluginFunctionsTests(unittest.TestCase):
    def setUp(self):
        from Prism_Unity_Functions import Prism_Unity_Functions
        from Prism_Unity_Variables import Prism_Unity_Variables

        class FakeUnity:
            def __init__(self):
                self.calls = []

            def call(self, cmd, args=None, interactive=False, timeout=None):
                self.calls.append((cmd, args))
                return {"getFPS": 30, "getFrameRange": {"start": 1, "end": 120}, "getAppVersion": "6000.5.6f1"}.get(cmd)

        class Core:
            pass

        self.unity = FakeUnity()
        self.core = Core()
        self.vars = Prism_Unity_Variables(self.core, None)
        self.funcs = Prism_Unity_Functions(self.core, None)
        self.funcs.unity = self.unity

    def test_variables(self):
        self.assertEqual(self.vars.pluginName, "Unity")
        self.assertEqual(self.vars.pluginType, "App")
        self.assertEqual(self.vars.appShortName, "Unity")
        self.assertEqual(self.vars.sceneFormats, [".unity"])
        self.assertEqual(self.vars.outputFormats, [".fbx", ".obj", ".abc"])
        self.assertEqual(self.vars.platforms, ["Windows"])
        self.assertTrue(os.path.isdir(os.path.join(self.vars.pluginDirectory, "UnityPackage", "com.prism.unity")))

    def test_getFPS_calls_unity(self):
        self.assertEqual(self.funcs.getFPS(None), 30)
        self.assertEqual(self.unity.calls, [("getFPS", None)])

    def test_setFPS_calls_unity(self):
        self.funcs.setFPS(None, 24)
        self.assertEqual(self.unity.calls, [("setFPS", {"fps": 24})])

    def test_frame_range_roundtrip(self):
        self.assertEqual(self.funcs.getFrameRange(None), [1, 120])
        self.funcs.setFrameRange(None, 10, 50)
        self.assertEqual(self.unity.calls[-1], ("setFrameRange", {"start": 10, "end": 50}))

    def test_app_version(self):
        self.assertEqual(self.funcs.getAppVersion(None), "6000.5.6f1")

    def test_scene_extension(self):
        self.funcs.sceneFormats = [".unity"]
        self.assertEqual(self.funcs.getSceneExtension(None), ".unity")

    def test_get_current_file_name_does_not_raise_at_startup(self):
        # PrismCore.startup calls getCurrentFileName(); raising there opens a blocking error dialog.
        self.assertEqual(self.funcs.getCurrentFileName(None), "")

    def test_unity_client_from_environment(self):
        from Prism_Unity_Functions import unity_client_from_env

        client = unity_client_from_env({"PRISM_UNITY_PORT": "51234", "PRISM_UNITY_TOKEN": "t"})
        self.assertEqual((client.port, client.token), (51234, "t"))
        self.assertIsNone(unity_client_from_env({}))


if __name__ == "__main__":
    unittest.main()
