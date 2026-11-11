import unittest

from fakes import FakeCore
from unity_bridge import dialogs, protocol
from unity_bridge.commands import PrismCommands

LOTUS = {"type": "asset", "asset_path": "Props/Lotus"}


class FakeMedia:
    def __init__(self):
        self.calls = []

    def generatePlayblastPath(self, entity, task, extension, framePadding="", comment=None, returnDetails=False, **kwargs):
        self.calls.append({"entity": entity, "task": task, "extension": extension, "framePadding": framePadding,
                           "comment": comment, "returnDetails": returnDetails})
        frame = (".%s" % framePadding) if framePadding else ""
        path = "P:/Lotus/Playblasts/%s/v0004/Lotus_%s_v0004%s%s" % (task, task, frame, extension)
        return {"path": path, "version": "v0004"} if returnDetails else path

    def getPlayblastVersionInfoPathFromFilepath(self, path):
        return path.rsplit("/", 1)[0] + "/versioninfo.json"


class MediaCore(FakeCore):
    user = "adm"
    username = "Administrator"

    def __init__(self):
        super().__init__()
        self.mediaProducts = FakeMedia()
        self.configs_written = []

    def setConfig(self, cat=None, param=None, val=None, data=None, configPath=None, **kwargs):
        self.configs_written.append((configPath, data))


def call(cmds, cmd, **args):
    return cmds.dispatch(protocol.make_request(cmd, args, "t", False))


class PlayblastCommandTests(unittest.TestCase):
    def setUp(self):
        self.core = MediaCore()
        self.cmds = PrismCommands(self.core, unity=None)

    def test_playblast_target_uses_generate_playblast_path(self):
        result = call(self.cmds, "playblastTarget", entity=LOTUS, task="Turntable", extension=".png", comment="tt")["result"]
        c = self.core.mediaProducts.calls[0]
        self.assertEqual((c["entity"], c["task"], c["extension"], c["comment"]), (LOTUS, "Turntable", ".png", "tt"))
        self.assertEqual(c["framePadding"], "####", "image sequences need a frame token")
        self.assertEqual(result["version"], "v0004")
        self.assertTrue(result["path"].endswith(".####.png"))

    def test_video_target_has_no_frame_token(self):
        result = call(self.cmds, "playblastTarget", entity=LOTUS, task="Turntable", extension=".mp4")["result"]
        self.assertEqual(self.core.mediaProducts.calls[0]["framePadding"], "")
        self.assertTrue(result["path"].endswith("v0004.mp4"))

    def test_unsupported_extension_is_bad_args(self):
        resp = call(self.cmds, "playblastTarget", entity=LOTUS, task="Turntable", extension=".exe")
        self.assertEqual(resp["error"]["code"], "bad_args")

    def test_playblast_done_registers_media(self):
        resp = call(self.cmds, "playblastDone", path="P:/Lotus/Playblasts/Turntable/v0004/Lotus_Turntable_v0004.####.png",
                    entity=LOTUS, task="Turntable", comment="tt", details={"frames": 24, "mode": "turntable"})
        self.assertTrue(resp["ok"], resp)
        path, data = self.core.configs_written[0]
        self.assertEqual(path, "P:/Lotus/Playblasts/Turntable/v0004/versioninfo.json")
        self.assertEqual(data["comment"], "tt")
        self.assertEqual(data["frames"], 24)
        self.assertEqual(data["source"], "Unity")
        self.assertEqual(data["user"], "adm")
        self.assertIn("date", data)


class ScriptedUnity:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def call(self, cmd, args=None, interactive=False, timeout=None):
        self.calls.append((cmd, dict(args or {})))
        return self.replies[cmd]


class PlayblastFlowTests(unittest.TestCase):
    def test_prism_started_playblast_never_lets_unity_call_back(self):
        core = MediaCore()
        unity = ScriptedUnity({
            "playblastContext": {"entity": LOTUS, "task": "Turntable"},
            "playblast": {"outputPath": "P:/x.####.png", "frameCount": 24},
        })
        cmds = PrismCommands(core, unity)
        result = dialogs.run_playblast(cmds, {"mode": "turntable", "frames": 24, "format": "png", "comment": "tt"})
        names = [c for c, a in unity.calls]
        self.assertEqual(names, ["playblastContext", "playblast"])
        sent = unity.calls[1][1]
        self.assertTrue(sent["outputPath"].endswith(".####.png"), "Prism resolves the output before calling Unity")
        self.assertEqual(sent["entity"], LOTUS)
        self.assertEqual(result["version"], "v0004")
        self.assertEqual(len(core.configs_written), 1, "Prism registers the media after Unity finished")


if __name__ == "__main__":
    unittest.main()
