import unittest

from fakes import FakeCore
from unity_bridge.headless import headless, instance_key
from unity_bridge.protocol import BridgeError


class HeadlessTests(unittest.TestCase):
    def test_headless_popup_raises_needs_input(self):
        core = FakeCore()
        original_popup = core.popup
        with self.assertRaises(BridgeError) as ctx:
            with headless(core):
                self.assertIn("silent", core.prismArgs)
                core.popup("Did you save it using Prism?")
        self.assertEqual(ctx.exception.code, "needs_input")
        self.assertIn("Did you save it using Prism?", ctx.exception.message)
        self.assertNotIn("silent", core.prismArgs)
        self.assertEqual(core.popup, original_popup)
        self.assertEqual(core.popups, [])

    def test_headless_popup_question_raises_needs_input(self):
        core = FakeCore()
        with self.assertRaises(BridgeError) as ctx:
            with headless(core):
                core.popupQuestion("Overwrite?", buttons=["Yes", "No"])
        self.assertEqual(ctx.exception.code, "needs_input")

    def test_headless_restores_on_exception(self):
        core = FakeCore()
        original_question = core.popupQuestion
        with self.assertRaises(ZeroDivisionError):
            with headless(core):
                1 / 0
        self.assertEqual(core.prismArgs, [])
        self.assertEqual(core.popupQuestion, original_question)

    def test_headless_keeps_existing_silent_flag(self):
        core = FakeCore()
        core.prismArgs = ["silent"]
        with headless(core):
            pass
        self.assertEqual(core.prismArgs, ["silent"])

    def test_instance_key_differs_per_project(self):
        self.assertNotEqual(instance_key("C:/A"), instance_key("C:/B"))
        self.assertEqual(instance_key("C:/A/"), instance_key("c:\\a"))
        self.assertEqual(len(instance_key("C:/A")), 16)


if __name__ == "__main__":
    unittest.main()
