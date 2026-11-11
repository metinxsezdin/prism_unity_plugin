import unittest

from unity_bridge.protocol import BridgeError
from unity_bridge.testhooks import install_fail_on_dialog


class FakeDialog:
    def exec_(self):
        return 1

    def exec(self):
        return 1

    def show(self):
        return None

    def windowTitle(self):
        return "Save comment"


class FakeMessageBox(FakeDialog):
    def windowTitle(self):
        return "Prism"


class FailOnDialogTests(unittest.TestCase):
    def test_any_dialog_raises_internal(self):
        install_fail_on_dialog(FakeDialog, FakeMessageBox)
        for call in (lambda: FakeDialog().exec_(), lambda: FakeDialog().exec(), lambda: FakeDialog().show(),
                     lambda: FakeMessageBox().exec_()):
            with self.assertRaises(BridgeError) as ctx:
                call()
            self.assertEqual(ctx.exception.code, "internal")
        with self.assertRaises(BridgeError) as ctx:
            FakeDialog().show()
        self.assertIn("Save comment", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
