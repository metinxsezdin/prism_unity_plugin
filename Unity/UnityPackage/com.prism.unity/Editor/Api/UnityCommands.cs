using System.Diagnostics;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

namespace Prism.Unity.Editor
{
    /// <summary>The commands Prism may call on Unity. Registered once per domain.</summary>
    [InitializeOnLoad]
    public static class UnityCommands
    {
        const string StartKey = "PrismUnity.FrameStart";
        const string EndKey = "PrismUnity.FrameEnd";
        const string FpsKey = "PrismUnity.Fps";

        static UnityCommands() => RegisterAll();

        public static void RegisterAll()
        {
            CommandRegistry.Register("getPid", (a, c) => Process.GetCurrentProcess().Id, false);
            CommandRegistry.Register("getAppVersion", (a, c) => Application.unityVersion, false);
            CommandRegistry.Register("getProjectInfo", (a, c) => new JObject
            {
                ["projectPath"] = PrismSettings.ProjectRoot.Replace('\\', '/'),
                ["productGuid"] = PlayerSettings.productGUID.ToString(),
            }, false);

            // Frame range and FPS are session settings: Unity has no scene-wide timeline, so these
            // are what Prism reads and writes, and what free-mode playblasts default to.
            CommandRegistry.Register("getFrameRange", (a, c) => new JObject
            {
                ["start"] = SessionState.GetInt(StartKey, 1),
                ["end"] = SessionState.GetInt(EndKey, 120),
            }, false);
            CommandRegistry.Register("setFrameRange", (a, c) =>
            {
                var start = RequireInt(a, "start");
                var end = RequireInt(a, "end");
                if (end < start)
                    throw new PrismCommandException(ErrorCodes.BadArgs, "end must not be before start.");
                SessionState.SetInt(StartKey, start);
                SessionState.SetInt(EndKey, end);
                return true;
            }, false);
            CommandRegistry.Register("getFPS", (a, c) => SessionState.GetInt(FpsKey, 30), false);
            CommandRegistry.Register("setFPS", (a, c) =>
            {
                var fps = RequireInt(a, "fps");
                if (fps <= 0) throw new PrismCommandException(ErrorCodes.BadArgs, "fps must be positive.");
                SessionState.SetInt(FpsKey, fps);
                return true;
            }, false);
        }

        public static int RequireInt(JObject a, string name)
        {
            var t = a?[name];
            if (t == null || (t.Type != JTokenType.Integer && t.Type != JTokenType.Float))
                throw new PrismCommandException(ErrorCodes.BadArgs, $"Missing number '{name}'.");
            return (int)t;
        }

        public static string RequireString(JObject a, string name)
        {
            var t = a?[name];
            if (t == null || t.Type != JTokenType.String || string.IsNullOrEmpty((string)t))
                throw new PrismCommandException(ErrorCodes.BadArgs, $"Missing text '{name}'.");
            return (string)t;
        }

        public static PrismEntity RequireEntity(JObject a, string name = "entity")
        {
            if (!(a?[name] is JObject o) || o["type"] == null)
                throw new PrismCommandException(ErrorCodes.BadArgs, $"Missing entity '{name}'.");
            return PrismEntity.FromJson(o);
        }
    }
}
