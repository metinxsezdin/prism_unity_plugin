using System;
using System.Linq;
using UnityEditor;
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

        static PackagingSettings _settings;

        static void Draw()
        {
            _settings = _settings ?? PackagingSettings.Load();

            EditorGUILayout.LabelField("This machine", EditorStyles.boldLabel);
            var root = EditorGUILayout.TextField("Prism folder", PrismSettings.PrismRoot);
            if (root != PrismSettings.PrismRoot) PrismSettings.PrismRoot = root;
            EditorGUILayout.LabelField("Prism Unity plugin", PrismSettings.PluginDir ?? "not found — register it with Prism");

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
            _settings.Enabled = EditorGUILayout.Toggle("Package imported products", _settings.Enabled);
            using (new EditorGUI.DisabledScope(!_settings.Enabled))
            {
                var types = DefinitionTypes();
                var names = types.Select(t => t.FullName).ToArray();
                var current = Math.Max(0, Array.FindIndex(types, t => t.AssemblyQualifiedName.StartsWith(_settings.DefinitionType.Split(',')[0] + ",")));
                var chosen = EditorGUILayout.Popup("Definition class", current, names);
                if (chosen != current && chosen >= 0 && chosen < types.Length)
                {
                    _settings.DefinitionType = $"{types[chosen].FullName}, {types[chosen].Assembly.GetName().Name}";
                    DefinitionClassChanged?.Invoke(types[chosen]);
                }
                _settings.AddressFormat = EditorGUILayout.TextField(new GUIContent("Address format", "{entity} {product} {category}"), _settings.AddressFormat);
                _settings.GroupFormat = EditorGUILayout.TextField(new GUIContent("Group format", "{category}"), _settings.GroupFormat);
                EditorGUILayout.HelpBox($"Example: {_settings.FormatAddress(PrismEntity.Asset("Props/Lotus"), "lotus_model")} in group \"{_settings.FormatGroup(PrismEntity.Asset("Props/Lotus"))}\"", MessageType.None);
            }
            if (EditorGUI.EndChangeCheck()) _settings.Save();
        }

        /// <summary>Raised when another definition class is chosen (the packaging assembly offers conversion).</summary>
        public static event Action<Type> DefinitionClassChanged;

        static Type[] DefinitionTypes()
        {
            var baseType = Type.GetType(DefinitionBaseType);
            if (baseType == null) return Array.Empty<Type>();
            return new[] { baseType }.Concat(TypeCache.GetTypesDerivedFrom(baseType).Where(t => !t.IsAbstract)).ToArray();
        }
    }
}
