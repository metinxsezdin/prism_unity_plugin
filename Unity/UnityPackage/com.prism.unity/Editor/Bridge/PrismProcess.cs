using System.Diagnostics;
using System.IO;

namespace Prism.Unity.Editor
{
    /// <summary>Starts the Prism process (Prism_Unity_Launcher.py) that serves this editor.</summary>
    public static class PrismProcess
    {
        static Process _owned;
        static readonly object Lock = new object();

        public static string PythonPath(string prismRoot) => Path.Combine(prismRoot, "Python313", "python.exe");

        public static string LauncherPath(string pluginDir) => Path.Combine(pluginDir, "Scripts", "Prism_Unity_Launcher.py");

        public static ProcessStartInfo BuildStartInfo(SessionInfo s, ProjectBinding b, string prismRoot, string pluginDir,
            string projectRoot, string firstCmd)
        {
            var psi = new ProcessStartInfo
            {
                FileName = PythonPath(prismRoot),
                Arguments = $"\"{LauncherPath(pluginDir)}\" {firstCmd}",
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = prismRoot,
            };
            psi.EnvironmentVariables["PRISM_ROOT"] = prismRoot;
            psi.EnvironmentVariables["PRISM_UNITY_PORT"] = s.UnityPort.ToString();
            psi.EnvironmentVariables["PRISM_UNITY_PRISM_PORT"] = s.PrismPort.ToString();
            psi.EnvironmentVariables["PRISM_UNITY_TOKEN"] = s.Token;
            psi.EnvironmentVariables["PRISM_UNITY_PID"] = s.UnityPid.ToString();
            psi.EnvironmentVariables["PRISM_UNITY_PROJECT"] = projectRoot;
            psi.EnvironmentVariables["PRISM_UNITY_PRISM_PROJECT"] = b?.PrismProjectConfig ?? "";
            return psi;
        }

        /// <summary>True when a Prism process started by this domain is still alive.</summary>
        public static bool IsRunning()
        {
            lock (Lock) return _owned != null && !_owned.HasExited;
        }

        /// <summary>
        /// Starts Prism unless this domain already did. After a domain reload the old Prism keeps
        /// running; the new launcher sees its mutex and exits, and calls reach the old one by port.
        /// </summary>
        public static void EnsureRunning(LaunchContext ctx)
        {
            lock (Lock)
            {
                if (_owned != null && !_owned.HasExited)
                    return;
                CheckInstalled(ctx);
                _owned = Process.Start(BuildStartInfo(ctx.Session, ctx.Binding, ctx.PrismRoot, ctx.PluginDir, ctx.ProjectRoot, "launch"));
            }
        }

        /// <summary>Throws prism_unavailable when Prism or the plugin launcher is missing.</summary>
        public static void CheckInstalled(LaunchContext ctx)
        {
            var python = PythonPath(ctx.PrismRoot);
            if (!File.Exists(python))
                throw new PrismCommandException(ErrorCodes.PrismUnavailable,
                    $"Prism was not found at {ctx.PrismRoot} (missing {python}). Set EditorPrefs 'PrismUnity.PrismRoot' to the Prism folder.");
            var launcher = LauncherPath(ctx.PluginDir);
            if (!File.Exists(launcher))
                throw new PrismCommandException(ErrorCodes.PrismUnavailable, $"Prism Unity plugin launcher not found: {launcher}");
        }

        /// <summary>True when the process this domain started has exited with a non-zero code.</summary>
        public static bool HasOwnedExitedWithError(out int exitCode)
        {
            lock (Lock)
            {
                exitCode = 0;
                if (_owned == null || !_owned.HasExited) return false;
                exitCode = _owned.ExitCode;
                return exitCode != 0;
            }
        }

        /// <summary>Drop the handle of a Prism process that has already exited, so it can be started again.</summary>
        public static void ForgetExitedProcess()
        {
            lock (Lock)
                if (_owned != null && _owned.HasExited) _owned = null;
        }

        /// <summary>Test hook: forget the process started by this domain (it keeps running).</summary>
        public static void ForgetRunningProcess()
        {
            lock (Lock) _owned = null;
        }

        /// <summary>Test hook: simulate a Prism crash (kill without waiting for exit).</summary>
        public static void KillOwnedWithoutWaiting()
        {
            lock (Lock)
            {
                try { if (_owned != null && !_owned.HasExited) _owned.Kill(); }
                catch (System.InvalidOperationException) { }
            }
        }

        /// <summary>Stops the Prism process this domain started (used by tests).</summary>
        public static void StopOwnedProcess()
        {
            lock (Lock)
            {
                try
                {
                    if (_owned != null && !_owned.HasExited)
                    {
                        _owned.Kill();
                        _owned.WaitForExit(10000); // release the port and mutex before anyone reconnects
                    }
                }
                catch (System.InvalidOperationException) { }
                _owned = null;
            }
        }
    }

    /// <summary>Everything needed to start Prism, captured on the main thread.</summary>
    public class LaunchContext
    {
        public SessionInfo Session;
        public ProjectBinding Binding;
        public string PrismRoot;
        public string PluginDir;
        public string ProjectRoot;

        public static LaunchContext Capture() => new LaunchContext
        {
            Session = PrismSession.EnsureStarted(),
            Binding = ProjectBinding.Load(),
            PrismRoot = PrismSettings.PrismRoot,
            PluginDir = PrismSettings.PluginDir,
            ProjectRoot = PrismSettings.ProjectRoot,
        };
    }
}
