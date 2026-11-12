using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// The project carries its own copy of the Prism packages (Packages/com.prism.*).
    /// When the Prism plugin on this machine has a newer version, say so once per editor session.
    /// </summary>
    [InitializeOnLoad]
    public static class EmbeddedPackages
    {
        static readonly string[] Names = { "com.prism.unity", "com.prism.assets" };
        const string CheckedKey = "PrismUnity.EmbeddedPackagesChecked";

        static EmbeddedPackages()
        {
            if (SessionState.GetBool(CheckedKey, false)) return;
            SessionState.SetBool(CheckedKey, true);
            EditorApplication.delayCall += () =>
            {
                foreach (var message in Outdated(PrismSettings.ProjectRoot, PrismSettings.PluginDir))
                    Debug.LogWarning("[Prism] " + message);
            };
        }

        /// <summary>One message per embedded package that is older than the same package in the plugin.</summary>
        public static List<string> Outdated(string projectRoot, string pluginDir)
        {
            var messages = new List<string>();
            if (string.IsNullOrEmpty(projectRoot) || string.IsNullOrEmpty(pluginDir)) return messages;
            foreach (var name in Names)
            {
                var embedded = ReadVersion(Path.Combine(projectRoot, "Packages", name, "package.json"));
                var available = ReadVersion(Path.Combine(pluginDir, "UnityPackage", name, "package.json"));
                if (embedded == null || available == null) continue;
                if (Parse(available) > Parse(embedded))
                    messages.Add($"Packages/{name} {embedded} in this project is older than {available} in the Prism plugin. " +
                                 "Reinstall it from Prism (Settings → DCC apps → Unity) and commit the updated Packages folder.");
            }
            return messages;
        }

        static string ReadVersion(string packageJson)
        {
            try
            {
                return File.Exists(packageJson) ? (string)JObject.Parse(File.ReadAllText(packageJson))["version"] : null;
            }
            catch (Exception e) when (e is IOException || e is Newtonsoft.Json.JsonException)
            {
                return null;
            }
        }

        /// <summary>"1.2.3-pre" → 1.2.3; unreadable → 0.0.</summary>
        static Version Parse(string version)
        {
            var core = version.Split('-', '+')[0];
            return Version.TryParse(core, out var v) ? v : new Version(0, 0);
        }
    }
}
