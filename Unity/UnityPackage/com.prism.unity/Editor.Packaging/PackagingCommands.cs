using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using Prism.Assets;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace Prism.Unity.Editor.Packaging
{
    /// <summary>Commands, menus and hooks of the packaging assembly.</summary>
    [InitializeOnLoad]
    public static class PackagingCommands
    {
        static PackagingCommands()
        {
            // Prism's "Check for updates" window sends this for products that disappeared from Prism.
            CommandRegistry.Register("setPrismMissing", (a, c) =>
            {
                var ids = a["ids"]?.ToObject<string[]>() ?? new string[0];
                return new JObject { ["updated"] = new JArray(SetMissing(ids, (bool?)a["missing"] ?? true).Cast<object>().ToArray()) };
            }, true);
            PrismApi.MissingReported += ids => SetMissing(ids, true);
            PrismSettingsProvider.DefinitionClassChanged += t => OfferConversion(t);
        }

        // ---- missing in Prism ----

        /// <summary>Set prismMissing on the definitions of these records. Returns the ids that have a definition.</summary>
        public static List<string> SetMissing(IEnumerable<string> recordIds, bool missing)
        {
            var updated = new List<string>();
            foreach (var id in recordIds)
            {
                var record = string.IsNullOrEmpty(id) ? null : ImportRecord.Load(id);
                if (record == null) continue;
                var definition = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(PackageBuilder.Describe(record).DefinitionPath);
                if (definition == null) continue;
                if (definition.prismMissing != missing)
                {
                    definition.prismMissing = missing;
                    EditorUtility.SetDirty(definition);
                    AssetDatabase.SaveAssetIfDirty(definition);
                    if (missing) Debug.LogWarning($"[Prism] {record.Entity.Path}/{record.Product} no longer exists in Prism. Its package is kept and flagged prismMissing.");
                }
                updated.Add(id);
            }
            return updated;
        }

        // ---- generate missing packages ----

        /// <summary>Package every imported product whose package is incomplete. Thumbnails are rendered. Returns how many were packaged.</summary>
        public static int GenerateMissing() => GenerateMissing(_ => null);

        /// <summary>Like GenerateMissing, but asks Prism for each product's preview image first; falls back to rendering when Prism is unreachable.</summary>
        public static async Task<int> GenerateMissingAsync()
        {
            var previews = new Dictionary<string, string>();
            foreach (var record in Incomplete())
            {
                try
                {
                    var resolved = await PrismClient.SendAsync("resolveVersion", new JObject
                    {
                        ["entity"] = record.Entity.ToJson(), ["product"] = record.Product, ["version"] = record.Version,
                    }, interactive: false, timeout: TimeSpan.FromSeconds(30));
                    previews[record.Id] = (string)resolved?["previewPath"];
                }
                catch (Exception e)
                {
                    Debug.Log($"[Prism] No Prism preview for {record.Id} ({e.Message}); the thumbnail will be rendered.");
                }
            }
            return await MainThreadDispatcher.Run(() => GenerateMissing(r => previews.TryGetValue(r.Id, out var p) ? p : null),
                TimeSpan.FromMinutes(10));
        }

        static int GenerateMissing(Func<ImportRecord, string> previewFor)
        {
            var count = 0;
            foreach (var record in Incomplete())
            {
                PackageBuilder.Ensure(record, previewFor(record));
                count++;
            }
            return count;
        }

        static List<ImportRecord> Incomplete() => ImportRecord.LoadAll().Where(r => !PackageBuilder.IsComplete(r)).ToList();

        // ---- convert definitions ----

        /// <summary>Definitions under Assets/Prism that are not yet of the target class.</summary>
        public static (int count, string[] paths) PreviewConversion(Type target)
        {
            RequireDefinitionClass(target);
            var paths = DefinitionPaths().Where(p => AssetDatabase.GetMainAssetTypeAtPath(p) != target).ToArray();
            return (paths.Length, paths);
        }

        /// <summary>
        /// Switch those definitions to the target class in place: same file, same GUID, so every reference
        /// (catalog, Addressables, scenes) still points at them. Fields with the same name keep their values.
        /// </summary>
        public static int ConvertDefinitions(Type target)
        {
            var paths = PreviewConversion(target).paths;
            if (paths.Length == 0) return 0;
            var script = ScriptFor(target);
            foreach (var path in paths)
            {
                var so = new SerializedObject(AssetDatabase.LoadMainAssetAtPath(path));
                so.FindProperty("m_Script").objectReferenceValue = script;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
            AssetDatabase.SaveAssets();
            // Changing the class replaces the loaded object. The file keeps the reference (GUID + fileID),
            // but the catalog's loaded list still holds the old objects: unload it so the next load
            // reads its references from disk again.
            var catalog = AssetDatabase.LoadAssetAtPath<PrismAssetCatalog>(CatalogUpdater.CatalogPath);
            if (catalog != null) Resources.UnloadAsset(catalog);
            return paths.Length;
        }

        static IEnumerable<string> DefinitionPaths() =>
            AssetDatabase.IsValidFolder(ProductImporter.Root)
                ? AssetDatabase.FindAssets("t:" + nameof(PrismAssetDefinition), new[] { ProductImporter.Root })
                    .Select(AssetDatabase.GUIDToAssetPath).Distinct()
                    .Where(p => typeof(PrismAssetDefinition).IsAssignableFrom(AssetDatabase.GetMainAssetTypeAtPath(p)))
                : Enumerable.Empty<string>();

        static void RequireDefinitionClass(Type target)
        {
            if (!PackageBuilder.IsDefinitionClass(target))
                throw new PrismCommandException(ErrorCodes.BadArgs,
                    $"{target?.FullName ?? "null"} is not a concrete subclass of {nameof(PrismAssetDefinition)}.");
        }

        static MonoScript ScriptFor(Type target)
        {
            var probe = ScriptableObject.CreateInstance(target);
            try
            {
                var script = MonoScript.FromScriptableObject(probe);
                if (script == null || script.GetClass() != target)
                    throw new PrismCommandException(ErrorCodes.BadArgs,
                        $"{target.FullName} must be in a script file named {target.Name}.cs so Unity can save assets of it.");
                return script;
            }
            finally
            {
                Object.DestroyImmediate(probe);
            }
        }

        // ---- menus (a person clicked them, so dialogs are fine) ----

        [MenuItem("Prism/Generate Missing Asset Packages", priority = 42)]
        static async void GenerateMissingMenu()
        {
            try
            {
                var count = await GenerateMissingAsync();
                EditorUtility.DisplayDialog("Prism", count == 0 ? "Every imported product already has a package." : $"Packaged {count} product(s).", "OK");
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                EditorUtility.DisplayDialog("Prism", "Generating packages failed: " + e.Message, "OK");
            }
        }

        /// <summary>The class selected in the Project window if it is a definition class, else the one in Project Settings → Prism.</summary>
        static Type MenuTarget()
        {
            var selected = (Selection.activeObject as MonoScript)?.GetClass();
            return PackageBuilder.IsDefinitionClass(selected) ? selected : PackageBuilder.DefinitionType(PackagingSettings.Load());
        }

        [MenuItem("Prism/Convert Definitions to Selected Class", priority = 43)]
        static void ConvertMenu()
        {
            var target = MenuTarget();
            if (!OfferConversion(target))
                EditorUtility.DisplayDialog("Prism", $"Every definition is already a {target.Name}.", "OK");
        }

        /// <summary>Ask, then convert. Returns false when there was nothing to convert.</summary>
        static bool OfferConversion(Type target)
        {
            if (!PackageBuilder.IsDefinitionClass(target)) return false;
            var count = PreviewConversion(target).count;
            if (count == 0) return false;
            if (EditorUtility.DisplayDialog("Prism", $"Convert {count} existing definition(s) to {target.Name}? " +
                    "Files, GUIDs and fields with the same name are kept.", "Convert", "Not now"))
            {
                try { ConvertDefinitions(target); }
                catch (Exception e) { Debug.LogException(e); EditorUtility.DisplayDialog("Prism", "Conversion failed: " + e.Message, "OK"); }
            }
            return true;
        }
    }
}
