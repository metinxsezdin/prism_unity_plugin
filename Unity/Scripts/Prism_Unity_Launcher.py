"""Entry point of the Prism process that serves one Unity editor.

Started by the Unity package (PrismProcess.cs) with Prism's bundled Python:

    python.exe Prism_Unity_Launcher.py <firstCmd>

Everything else comes from the environment:
    PRISM_ROOT                  Prism install folder
    PRISM_UNITY_PORT            port of the Unity command server
    PRISM_UNITY_PRISM_PORT      port this process listens on
    PRISM_UNITY_TOKEN           session token both sides require
    PRISM_UNITY_PID             Unity editor process id (Prism quits when it exits)
    PRISM_UNITY_PROJECT         Unity project root (one Prism instance per project)
    PRISM_UNITY_PRISM_PROJECT   pipeline.json of the Prism project this Unity project is bound to
"""

import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from unity_bridge.headless import instance_key  # noqa: E402

MUTEX_PREFIX = "Local\\PrismUnity_"


def acquire_single_instance(unity_project):
    """Return a mutex handle, or None when a Prism instance already serves this Unity project."""
    if sys.platform != "win32":
        return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, wintypes.BOOL(True), MUTEX_PREFIX + instance_key(unity_project))
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return handle


def main():
    env = os.environ
    unity_project = env.get("PRISM_UNITY_PROJECT", "")
    if not unity_project:
        raise SystemExit("PRISM_UNITY_PROJECT is not set.")
    mutex = acquire_single_instance(unity_project)
    if mutex is None:
        return 0  # Unity talks to the running instance over its port.

    prism_root = env.get("PRISM_ROOT") or r"C:\Program Files\Prism2"
    sys.path.insert(0, os.path.join(prism_root, "Scripts"))
    import PrismCore  # noqa: E402  (adds Prism's library paths)
    from qtpy.QtCore import QObject, QThread, QTimer, Qt, Signal
    from qtpy.QtWidgets import QApplication

    from unity_bridge.command_server import CommandServer
    from unity_bridge.commands import PrismCommands
    from unity_bridge.endpoint import write_prism_endpoint
    from unity_bridge.projects import pin_project
    from unity_bridge.unity_client import UnityClient

    class MainThreadInvoker(QObject):
        request = Signal(object)

        def __init__(self):
            super().__init__()
            self.request.connect(self._run, Qt.QueuedConnection)

        def _run(self, job):
            job()

        def __call__(self, fn):
            app = QApplication.instance()
            if app is None or QThread.currentThread() == app.thread():
                return fn()
            box = {}
            done = threading.Event()

            def job():
                try:
                    box["result"] = fn()
                except BaseException as e:  # handed back to the server thread
                    box["error"] = e
                finally:
                    done.set()

            self.request.emit(job)
            done.wait()
            if "error" in box:
                raise box["error"]
            return box["result"]

    qapp = QApplication.instance() or QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)

    prism_project = env.get("PRISM_UNITY_PRISM_PROJECT", "")
    prism_args = ["noProjectBrowser", "splash"] if prism_project else ["loadProject", "noProjectBrowser", "splash"]
    pcore = PrismCore.create(app="Unity", prismArgs=prism_args)
    # Pin the project for this Unity project only; leave the user's global choice alone.
    pin_project(pcore, prism_project)

    if env.get("PRISM_UNITY_FAIL_ON_DIALOG") == "1":
        from qtpy.QtWidgets import QDialog, QMessageBox

        from unity_bridge.testhooks import install_fail_on_dialog

        install_fail_on_dialog(QDialog, QMessageBox)

    unity = UnityClient(int(env["PRISM_UNITY_PORT"]), env["PRISM_UNITY_TOKEN"], project=unity_project)
    pcore.appPlugin.unity = unity
    commands = PrismCommands(pcore, unity)
    invoker = MainThreadInvoker()
    server = CommandServer(int(env.get("PRISM_UNITY_PRISM_PORT") or 0), env["PRISM_UNITY_TOKEN"], commands.dispatch, invoker)
    server.start()
    # Publish the port actually bound (the suggested one may have been taken meanwhile).
    write_prism_endpoint(unity_project, server.port, os.getpid())

    unity_pid = int(env.get("PRISM_UNITY_PID", "0") or 0)

    def check_unity_alive():
        try:
            import psutil

            alive = psutil.pid_exists(unity_pid)
        except ImportError:
            alive = True
        if not alive:
            server.stop()
            qapp.quit()

    alive_timer = QTimer()
    alive_timer.timeout.connect(check_unity_alive)
    alive_timer.start(5000)

    first_cmd = sys.argv[1] if len(sys.argv) > 1 else "launch"
    if first_cmd != "launch":
        QTimer.singleShot(0, lambda: commands.dispatch({"id": "argv", "cmd": first_cmd, "args": {}, "interactive": True}))

    return qapp.exec_()


if __name__ == "__main__":
    sys.exit(main())
