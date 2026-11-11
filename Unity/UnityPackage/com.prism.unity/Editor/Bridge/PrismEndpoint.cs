using System;
using System.Diagnostics;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// The port the Prism process actually listens on. Prism binds whatever port is free and publishes
    /// it in Library/PrismUnity/prism.json {port, pid}; nothing is reserved ahead of time.
    /// </summary>
    public static class PrismEndpoint
    {
        /// <summary>The published port, or null when there is none or its Prism process has exited.</summary>
        public static int? ReadPrismPort(string projectRoot) => Read(projectRoot)?.port;

        /// <summary>The live Prism process id, or null.</summary>
        public static int? ReadPrismPid(string projectRoot) => Read(projectRoot)?.pid;

        static (int port, int pid)? Read(string projectRoot)
        {
            var path = Path.Combine(projectRoot, "Library", "PrismUnity", "prism.json");
            try
            {
                if (!File.Exists(path)) return null;
                var json = JObject.Parse(File.ReadAllText(path));
                var pid = (int?)json["pid"];
                var port = (int?)json["port"];
                if (pid == null || port == null || !IsAlive(pid.Value)) return null;
                return (port.Value, pid.Value);
            }
            catch (Exception e) when (e is IOException || e is JsonException || e is FormatException || e is ArgumentException)
            {
                return null;
            }
        }

        static bool IsAlive(int pid)
        {
            try
            {
                using (var p = Process.GetProcessById(pid))
                    return !p.HasExited;
            }
            catch (ArgumentException) { return false; }
            catch (InvalidOperationException) { return false; }
        }
    }
}
