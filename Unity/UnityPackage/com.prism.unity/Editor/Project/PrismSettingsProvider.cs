using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEngine;

namespace Prism.Unity.Editor
{
    /// <summary>Project Settings → Prism: where Prism is, which Prism project, and asset packaging.</summary>
    public static class PrismSettingsProvider
    {
        const string DefinitionBaseType = "Prism.Assets.PrismAssetDefinition, Prism.Assets";

        [SettingsProvider]
        static SettingsProvider Create() => new SettingsProvider("Project/Prism", SettingsScope.Project)
        {
            label = "Prism",
            keywords = new[] { "Prism", "Addressables", "Pipeline", "Packaging" },
            guiHandler = _ => Draw(),
        };

        static void Draw()
        {
            var settings = CurrentSettings();

            EditorGUILayout.LabelField("This machine", EditorStyles.boldLabel);
            var root = EditorGUILayout.TextField("Prism folder", PrismSettings.PrismRoot);
            if (root != PrismSettings.PrismRoot)
            {
                PrismSettings.PrismRoot = root;
                ResetCache();
            }
            var pluginDir = CachedPluginDir();
            EditorGUILayout.LabelField("Prism Unity plugin", pluginDir ?? "not found — register it with Prism");
            foreach (var message in CachedOutdated())
                EditorGUILayout.HelpBox(message, MessageType.Warning);

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Prism project", EditorStyles.boldLabel);
            var binding = ProjectBinding.Load();
            EditorGUILayout.LabelField("Bound to", binding?.PrismProjectConfig ?? "not bound — install from Prism Settings → DCC apps → Unity");
            if (binding != null && GUILayout.Button("The Prism project moved…", GUILayout.Width(220)))
            {
                var picked = EditorUtility.OpenFilePanel("Select the moved project's pipeline.json", "", "json");
                if (!string.IsNullOrEmpty(picked))
                {
                    var error = ProjectBinding.Relocate(picked);
                    EditorUtility.DisplayDialog("Prism", error ?? "The project path was updated. Prism restarts on the next use.", "OK");
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Asset packaging", EditorStyles.boldLabel);
            EditorGUI.BeginChangeCheck();
            settings.Enabled = EditorGUILayout.Toggle("Package imported products", settings.Enabled);
            using (new EditorGUI.DisabledScope(!settings.Enabled))
            {
                var types = DefinitionTypes();
                var names = types.Select(t => t.FullName).ToArray();
                var current = SelectedIndex(types, settings.DefinitionType);
                var chosen = EditorGUILayout.Popup("Definition class", current, names);
                if (chosen != current && chosen >= 0 && chosen < types.Length)
                {
                    settings.DefinitionType = $"{types[chosen].FullName}, {types[chosen].Assembly.GetName().Name}";
                    DefinitionClassChanged?.Invoke(types[chosen]);
                }
                settings.AddressFormat = EditorGUILayout.TextField(new GUIContent("Address format", "{entity} {product} {category}"), settings.AddressFormat);
                settings.GroupFormat = EditorGUILayout.TextField(new GUIContent("Group format", "{category}"), settings.GroupFormat);
                EditorGUILayout.HelpBox($"Example: {settings.FormatAddress(PrismEntity.Asset("Props/Lotus"), "lotus_model")} in group \"{settings.FormatGroup(PrismEntity.Asset("Props/Lotus"))}\"", MessageType.None);
                foreach (var problem in settings.Problems())
                    EditorGUILayout.HelpBox(problem, MessageType.Warning);
            }
            if (EditorGUI.EndChangeCheck())
            {
                settings.Save();
                _settingsStamp = Stamp();
            }
        }

        /// <summary>Raised when another definition class is chosen (the packaging assembly offers conversion).</summary>
        public static event Action<Type> DefinitionClassChanged;

        // ---- settings.json, re-read when it changes on disk (e.g. a git pull) so a stale copy is never saved back ----

        static PackagingSettings _settings;
        static DateTime _settingsStamp;

        public static PackagingSettings CurrentSettings()
        {
            var stamp = Stamp();
            if (_settings == null || stamp != _settingsStamp)
            {
                _settings = PackagingSettings.Load();
                _settingsStamp = stamp;
            }
            return _settings;
        }

        static DateTime Stamp() => File.Exists(PackagingSettings.FilePath) ? File.GetLastWriteTimeUtc(PackagingSettings.FilePath) : DateTime.MinValue;

        // ---- plugin folder and embedded package check: they read files, so not on every repaint ----

        /// <summary>Test hook: where the plugin folder comes from.</summary>
        public static Func<string> PluginDirSource = () => PrismSettings.PluginDir;
        static bool _pluginDirKnown;
        static string _pluginDir;
        static List<string> _outdated;

        public static void ResetCache()
        {
            _pluginDirKnown = false;
            _pluginDir = null;
            _outdated = null;
        }

        public static string CachedPluginDir()
        {
            if (!_pluginDirKnown)
            {
                _pluginDir = PluginDirSource();
                _pluginDirKnown = true;
            }
            return _pluginDir;
        }

        static List<string> CachedOutdated() =>
            _outdated = _outdated ?? EmbeddedPackages.Outdated(PrismSettings.ProjectRoot, CachedPluginDir());

        // ---- definition class picker ----

        /// <summary>Index of definitionType in types; 0 (the base class) when it is empty or not listed.</summary>
        public static int SelectedIndex(Type[] types, string definitionType)
        {
            var name = (definitionType ?? "").Split(',')[0].Trim();
            if (name.Length == 0) return 0;
            return Math.Max(0, Array.FindIndex(types, t => t.FullName == name));
        }

        /// <summary>
        /// The base definition class and its concrete subclasses that are compiled into player builds.
        /// A class in an editor-only assembly would leave the built game with definitions that have no script.
        /// </summary>
        public static Type[] DefinitionTypes()
        {
            if (_types != null) return _types; // classes only change with a recompile, which resets this field
            var baseType = Type.GetType(DefinitionBaseType);
            if (baseType == null) return Array.Empty<Type>();
            var player = new HashSet<string>(CompilationPipeline.GetAssemblies(AssembliesType.PlayerWithoutTestAssemblies).Select(a => a.name));
            return _types = new[] { baseType }
                .Concat(TypeCache.GetTypesDerivedFrom(baseType).Where(t => !t.IsAbstract && player.Contains(t.Assembly.GetName().Name)))
                .ToArray();
        }

        static Type[] _types;
    }
}
