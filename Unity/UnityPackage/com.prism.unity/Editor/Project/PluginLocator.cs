using System;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// Finds the Prism "Unity" plugin folder (the one with Scripts/Prism_Unity_Launcher.py) on this machine.
    /// The Unity package is embedded in each project, so the plugin can no longer be found relative to it.
    /// </summary>
    public static class PluginLocator
    {
        public const string PrefsKey = "PrismUnity.PluginDir";

        /// <summary>Test hook: replaces the whole search.</summary>
        public static Func<string> TestSearch;

        public static string Find()
        {
            if (TestSearch != null) return TestSearch();
            var pluginPaths = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Prism2", "PluginPaths.json");
            var programData = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Prism2", "plugins");
            var package = UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(PluginLocator).Assembly)?.resolvedPath;
            return Find(pluginPaths, programData, EditorPrefs.GetString(PrefsKey, ""), package);
        }

        /// <summary>Search order: EditorPrefs override, Prism's PluginPaths.json, ProgramData, repo layout (TestProject).</summary>
        public static string Find(string pluginPathsJson, string programDataPlugins, string prefsOverride, string packagePath)
        {
            if (IsPlugin(prefsOverride)) return Path.GetFullPath(prefsOverride);

            foreach (var candidate in FromPluginPaths(pluginPathsJson))
                if (IsPlugin(candidate)) return Path.GetFullPath(candidate);

            if (!string.IsNullOrEmpty(programDataPlugins))
            {
                var unity = Path.Combine(programDataPlugins, "Unity");
                if (IsPlugin(unity)) return Path.GetFullPath(unity);
            }

            if (!string.IsNullOrEmpty(packagePath))
            {
                var repo = Path.GetFullPath(Path.Combine(packagePath, "..", ".."));
                if (IsPlugin(repo)) return repo;
            }
            return null;
        }

        public static bool IsPlugin(string dir) =>
            !string.IsNullOrEmpty(dir) && File.Exists(Path.Combine(dir, "Scripts", "Prism_Unity_Launcher.py"));

        static string[] FromPluginPaths(string file)
        {
            try
            {
                if (string.IsNullOrEmpty(file) || !File.Exists(file)) return Array.Empty<string>();
                var plugins = JObject.Parse(File.ReadAllText(file))["plugins"] as JArray;
                if (plugins == null) return Array.Empty<string>();
                var result = new string[plugins.Count];
                for (var i = 0; i < plugins.Count; i++) result[i] = (string)plugins[i]?["path"];
                return result;
            }
            catch (Exception e) when (e is IOException || e is JsonException)
            {
                return Array.Empty<string>();
            }
        }
    }
}
