import json
import os
import shutil
import subprocess
import tempfile
import unittest

import prism_env

REPO = os.environ.get("PRISM_UNITY_REPO", "")
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
SYSTEM_PATH = r"C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0"


@unittest.skipUnless(prism_env.PRISM_AVAILABLE and os.name == "nt", "needs Windows and Prism")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="prism_install_home_")
        # Prism's settings folder is found like Prism does (PRISM_USER_PREFS, else the Shell Documents folder),
        # never through USERPROFILE\Documents, which is wrong when Documents is redirected (OneDrive).
        self.prefs = os.path.join(self.home, "Redirected Documents", "Prism2")
        os.makedirs(self.prefs)
        self.cfg = os.path.join(self.prefs, "PluginPaths.json")
        with open(self.cfg, "w", encoding="utf-8") as f:
            json.dump({"plugins": [{"path": "C:\\ProgramData\\Prism2\\plugins\\Maya"}]}, f)
        self.bin = tempfile.mkdtemp(prefix="prism_install_bin_")
        self.log = os.path.join(self.bin, "claude.log")
        with open(os.path.join(self.bin, "claude.cmd"), "w") as f:
            f.write('@echo %*>>"%~dp0claude.log"\r\n')

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.bin, ignore_errors=True)

    def _run(self, *args, claude=True, bat=None, prism_root=None):
        env = dict(os.environ, USERPROFILE=self.home, PRISM_USER_PREFS=self.prefs, PATH=(self.bin + ";" if claude else "") + SYSTEM_PATH)
        env.pop("PRISM_ROOT", None)
        flags = ["-NoPause", "-SkipCheck", "-PrismRoot", prism_root or prism_env.PRISM_ROOT] + list(args)
        if bat:
            cmd = ["cmd.exe", "/c", os.path.join(REPO, bat)] + flags
        else:
            cmd = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(REPO, "tools", "install.ps1")] + flags
        proc = subprocess.run(cmd, capture_output=True, timeout=120, env=env)
        return proc.returncode, proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")

    def _plugins(self):
        with open(self.cfg, encoding="utf-8") as f:
            return [os.path.normcase(p["path"]) for p in json.load(f)["plugins"]]

    def _claude_calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8", errors="replace") as f:
            return [line.strip().replace('"', "") for line in f if line.strip()]  # cmd keeps the quotes around spaced args

    def _unity(self):
        return os.path.normcase(os.path.join(REPO, "Unity"))

    def test_install_registers_plugin_and_mcp(self):
        code, out = self._run()
        self.assertEqual(code, 0, out)
        self.assertEqual(self._plugins().count(self._unity()), 1)
        self.assertIn(os.path.normcase("C:\\ProgramData\\Prism2\\plugins\\Maya"), self._plugins())
        calls = self._claude_calls()
        self.assertEqual(len(calls), 2, calls)
        self.assertTrue(calls[0].startswith("mcp remove prism --scope user"), calls)
        self.assertTrue(calls[1].startswith("mcp add prism --scope user -e PRISM_ROOT="), calls)
        self.assertIn("server.py", calls[1])
        self.assertIn("Python313", calls[1])
        self.assertIn("Install complete.", out)
        self.assertTrue(os.path.exists(self.cfg + ".bak"))

    def test_install_twice_is_idempotent(self):
        self._run()
        code, out = self._run()
        self.assertEqual(code, 0, out)
        self.assertEqual(self._plugins().count(self._unity()), 1)
        calls = self._claude_calls()
        self.assertEqual([c.split()[1] for c in calls], ["remove", "add", "remove", "add"])

    def test_uninstall_reverts(self):
        self._run()
        code, out = self._run("-Remove")
        self.assertEqual(code, 0, out)
        self.assertNotIn(self._unity(), self._plugins())
        self.assertTrue(self._claude_calls()[-1].startswith("mcp remove prism --scope user"))
        self.assertIn("Uninstall complete.", out)

    def test_missing_claude_is_not_fatal(self):
        code, out = self._run(claude=False)
        self.assertEqual(code, 0, out)
        self.assertIn("Claude Code not found", out)
        self.assertIn(self._unity(), self._plugins())

    def test_wrong_prism_root_fails_without_asking(self):
        code, out = self._run(prism_root=os.path.join(self.home, "NoPrism"))
        self.assertEqual(code, 1, out)
        self.assertIn("Prism was not found", out)

    def test_npm_ps1_shim_is_not_used(self):
        # I6: PowerShell 5.1 drops "--" when it calls a .ps1, and -e then swallows the server command.
        with open(os.path.join(self.bin, "claude.ps1"), "w") as f:
            f.write('Add-Content -Path (Join-Path $PSScriptRoot "claude.log") -Value ("PS1 " + ($args -join " "))' + chr(10))
        code, out = self._run()
        self.assertEqual(code, 0, out)
        calls = self._claude_calls()
        self.assertFalse(any(c.startswith("PS1") for c in calls), calls)
        self.assertTrue(calls[-1].startswith("mcp add prism --scope user -e PRISM_ROOT="), calls)

    def test_bat_passes_arguments(self):
        code, out = self._run(bat="Install.bat")
        self.assertEqual(code, 0, out)
        self.assertEqual(self._plugins().count(self._unity()), 1)
        code, out = self._run(bat="Uninstall.bat")
        self.assertEqual(code, 0, out)
        self.assertNotIn(self._unity(), self._plugins())


if __name__ == "__main__":
    unittest.main()
