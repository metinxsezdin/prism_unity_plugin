import unittest

from unity_bridge.projects import pin_project


class FakeConfigCore:
    """changeProject behaves like Prism with a UI: it writes globals/current project."""

    def __init__(self, current):
        self.config = {"current project": current}
        self.prismIni = current
        self.changed_to = []

    def getConfig(self, cat, param, **kwargs):
        return self.config.get(param)

    def setConfig(self, cat, param, val, **kwargs):
        self.config[param] = val

    def changeProject(self, configPath=None, writeToConfig=None, **kwargs):
        self.changed_to.append(configPath)
        self.prismIni = configPath
        self.config["current project"] = configPath  # Prism ignores writeToConfig=False when a UI exists


class PinProjectTests(unittest.TestCase):
    def test_pins_project_without_touching_users_setting(self):
        core = FakeConfigCore(r"M:\other_project\00_Pipeline\pipeline.json")
        pin_project(core, "C:/Users/x/PrismUnityTest Project/00_Pipeline/pipeline.json")
        self.assertEqual(core.prismIni, "C:/Users/x/PrismUnityTest Project/00_Pipeline/pipeline.json")
        self.assertEqual(core.config["current project"], r"M:\other_project\00_Pipeline\pipeline.json")

    def test_already_active_project_is_not_reloaded(self):
        core = FakeConfigCore("C:/P/00_Pipeline/pipeline.json")
        pin_project(core, "C:\\P\\00_Pipeline\\pipeline.json")
        self.assertEqual(core.changed_to, [])

    def test_empty_target_does_nothing(self):
        core = FakeConfigCore("C:/P/00_Pipeline/pipeline.json")
        pin_project(core, "")
        self.assertEqual(core.changed_to, [])


if __name__ == "__main__":
    unittest.main()
