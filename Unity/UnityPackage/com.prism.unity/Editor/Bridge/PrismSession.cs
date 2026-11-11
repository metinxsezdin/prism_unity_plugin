using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;

namespace Prism.Unity.Editor
{
    public class SessionInfo
    {
        [JsonProperty("unityPort")] public int UnityPort;
        [JsonProperty("prismPort")] public int PrismPort;
        [JsonProperty("token")] public string Token;
        [JsonProperty("unityPid")] public int UnityPid;
    }

    /// <summary>
    /// The bridge session of this editor: Unity's command server plus the port and token
    /// handed to the Prism process. Survives domain reloads through Library/PrismUnity/session.json.
    /// </summary>
    [InitializeOnLoad]
    public static class PrismSession
    {
        static CommandServer _server;

        /// <summary>Test hook: overrides the Play Mode check.</summary>
        public static bool? PlayModeOverride;

        /// <summary>Raised after the command server starts (commands register here).</summary>
        public static event Action Started;

        public static SessionInfo Current { get; private set; }

        public static string SessionFilePath =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Library", "PrismUnity", "session.json"));

        static PrismSession()
        {
            AssemblyReloadEvents.beforeAssemblyReload += Shutdown;
            EditorApplication.quitting += Shutdown;
            EditorApplication.delayCall += () => EnsureStarted();
        }

        public static bool IsPlaying() => PlayModeOverride ?? EditorApplication.isPlayingOrWillChangePlaymode;

        public static SessionInfo EnsureStarted()
        {
            if (_server != null && Current != null)
                return Current;

            var pid = Process.GetCurrentProcess().Id;
            var previous = Load();
            var reuse = previous != null && previous.UnityPid == pid && !string.IsNullOrEmpty(previous.Token);
            var info = reuse
                ? previous
                : new SessionInfo { Token = NewToken(), UnityPid = pid, PrismPort = FreePort() };

            _server = new CommandServer(info.Token);
            info.UnityPort = _server.Start(reuse ? previous.UnityPort : 0);
            if (info.PrismPort == 0 || info.PrismPort == info.UnityPort)
                info.PrismPort = FreePort();
            Current = info;
            Save(info);
            Started?.Invoke();
            return info;
        }

        /// <summary>Stops the server but keeps session.json so the next domain reuses port and token.</summary>
        public static void Shutdown()
        {
            _server?.Stop();
            _server = null;
            Current = null;
        }

        static SessionInfo Load()
        {
            try
            {
                return File.Exists(SessionFilePath)
                    ? JsonConvert.DeserializeObject<SessionInfo>(File.ReadAllText(SessionFilePath))
                    : null;
            }
            catch (Exception e) when (e is IOException || e is JsonException)
            {
                return null;
            }
        }

        static void Save(SessionInfo info)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(SessionFilePath));
            File.WriteAllText(SessionFilePath, JsonConvert.SerializeObject(info, Formatting.Indented));
        }

        static string NewToken()
        {
            var bytes = new byte[24];
            using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(bytes);
            return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
        }

        static int FreePort()
        {
            var l = new TcpListener(IPAddress.Loopback, 0);
            l.Start();
            var port = ((IPEndPoint)l.LocalEndpoint).Port;
            l.Stop();
            return port;
        }
    }
}
