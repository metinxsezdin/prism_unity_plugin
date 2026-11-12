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
            // Prism's "Check for updates" window sends this for products that disappeared from Prism (missing: true)
            // and for those that exist (missing: false). "changed" lets its startup check stay quiet about old news.
            CommandRegistry.Register("setPrismMissing", (a, c) =>
            {
                var ids = a["ids"]?.ToObject<string[]>() ?? new string[0];
                var (updated, changed) = SetMissing(ids, (bool?)a["missing"] ?? true);
                return new JObject
                {
                    ["updated"] = new JArray(updated.Cast<object>().ToArray()),
                    ["changed"] = new JArray(changed.Cast<object>().ToArray()),
                };
            }, true);
            PrismApi.AvailabilityReported += (missing, present) =>
            {
                SetMissing(missing, true);
                SetMissing(present, false);
            };
            PrismSettingsProvider.DefinitionClassChanged += t => OfferConversion(t);

            // Claude's tools live in Prism.Unity.Editor, which does not reference this assembly.
            PrismMcpTools.PackageInfoProvider = PackageJson;
            PrismMcpTools.GeneratePackagesHandler = async () => (await GenerateMissingAsync()).ToJson();
            PrismMcpTools.ConvertDefinitionsHandler = ConvertForClaude;
        }

        // ---- Claude ----

        static JObject PackageJson(string recordId)
        {
            var record = ImportRecord.Load(recordId);
            if (record == null) return null;
            var json = JObject.FromObject(PackageBuilder.Describe(record));
            json["complete"] = PackageBuilder.IsComplete(record);
            var definition = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>((string)json["definitionPath"]);
            if (definition != null)
            {
                json["definitionClass"] = definition.GetType().FullName;
                json["prismMissing"] = definition.prismMissing;
            }
            return json;
        }

        /// <summary>Without confirm: needs_confirmation with {count, paths, className}. With confirm: {converted, className}.</summary>
        static JToken ConvertForClaude(string className, bool confirm)
        {
            var target = FindDefinitionClass(className);
            var (count, paths) = PreviewConversion(target);
            if (count > 0 && !confirm)
                throw new PrismCommandException(ErrorCodes.NeedsConfirmation,
                    $"{count} definition(s) would switch to {target.Name}. Ask the user, then call again with confirm=true.",
                    new JObject { ["count"] = count, ["paths"] = new JArray(paths.Cast<object>().ToArray()), ["className"] = target.FullName });
            return new JObject { ["converted"] = ConvertDefinitions(target), ["className"] = target.FullName };
        }

        /// <summary>A definition class by simple name, full name or assembly-qualified name.</summary>
        public static Type FindDefinitionClass(string className)
        {
            var candidates = TypeCache.GetTypesDerivedFrom<PrismAssetDefinition>().Append(typeof(PrismAssetDefinition))
                .Where(PackageBuilder.IsDefinitionClass).ToList();
            var matches = candidates.Where(t => t.Name == className || t.FullName == className || t.AssemblyQualifiedName == className).ToList();
            if (matches.Count == 1) return matches[0];
            var known = string.Join(", ", candidates.Select(t => t.FullName));
            throw new PrismCommandException(ErrorCodes.BadArgs, matches.Count == 0
                ? $"No definition class '{className}'. Known: {known}"
                : $"'{className}' is ambiguous; use the full name. Known: {known}");
        }

        // ---- missing in Prism ----

        /// <summary>Set prismMissing on the definitions of these records: (ids that have a definition, ids whose flag changed).</summary>
        public static (List<string> updated, List<string> changed) SetMissing(IEnumerable<string> recordIds, bool missing)
        {
            var updated = new List<string>();
            var changed = new List<string>();
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
                    changed.Add(id);
                }
                updated.Add(id);
            }
            return (updated, changed);
        }

        // ---- generate missing packages ----

        /// <summary>What a Generate Missing run did.</summary>
        public class GenerateReport
        {
            /// <summary>Products that got their package created.</summary>
            public int Generated;
            /// <summary>Complete packages whose Addressable entries and catalog entry were checked again.</summary>
            public int Repaired;
            public readonly List<(string id, string error)> Failed = new List<(string, string)>();

            public JObject ToJson() => new JObject
            {
                ["generated"] = Generated,
                ["repaired"] = Repaired,
                ["failed"] = new JArray(Failed.Select(f => new JObject { ["id"] = f.id, ["error"] = f.error })),
            };
        }

        /// <summary>
        /// Package every imported product whose package is incomplete (thumbnails are rendered), and re-register the
        /// Addressable and catalog entries of complete ones. A failing product is reported and skipped. Returns how many were packaged.
        /// </summary>
        public static int GenerateMissing() => Generate(_ => null).Generated;

        /// <summary>Like GenerateMissing, but asks Prism for each product's preview image first; falls back to rendering when Prism is unreachable.</summary>
        public static async Task<GenerateReport> GenerateMissingAsync()
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
            return await MainThreadDispatcher.Run(() => Generate(r => previews.TryGetValue(r.Id, out var p) ? p : null),
                TimeSpan.FromMinutes(10));
        }

        static GenerateReport Generate(Func<ImportRecord, string> previewFor)
        {
            var report = new GenerateReport();
            foreach (var record in ImportRecord.LoadAll())
            {
                try
                {
                    if (PackageBuilder.IsComplete(record))
                    {
                        PackageBuilder.Repair(record);
                        report.Repaired++;
                    }
                    else
                    {
                        PackageBuilder.Ensure(record, previewFor(record));
                        report.Generated++;
                    }
                }
                catch (Exception e)
                {
                    report.Failed.Add((record.Id, e.Message));
                    Debug.LogError($"[Prism] Could not package {record.Id}: {e.Message}");
                }
            }
            return report;
        }

        static List<ImportRecord> Incomplete() => ImportRecord.LoadAll().Where(r => !PackageBuilder.IsComplete(r)).ToList();

        // ---- convert definitions ----

        /// <summary>
        /// Definitions under Assets/Prism whose class the target extends. Only those are converted, so no field is ever
        /// dropped: a definition of a sibling class, or a conversion back to a base class, is left alone.
        /// </summary>
        public static (int count, string[] paths) PreviewConversion(Type target)
        {
            RequireDefinitionClass(target);
            var paths = DefinitionPaths().Where(p =>
            {
                var current = AssetDatabase.GetMainAssetTypeAtPath(p);
                return current != target && current.IsAssignableFrom(target);
            }).ToArray();
            return (paths.Length, paths);
        }

        /// <summary>
        /// Switch those definitions to the target class in place: same file, same GUID, so every reference
        /// (catalog, Addressables, scenes) still points at them. Every existing field keeps its value; new fields start empty.
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
                var report = await GenerateMissingAsync();
                var text = report.Generated == 0 ? "Every imported product already has a package." : $"Packaged {report.Generated} product(s).";
                if (report.Failed.Count > 0)
                    text += $"\n\n{report.Failed.Count} could not be packaged:\n" + string.Join("\n", report.Failed.Select(f => $"{f.id}: {f.error}"));
                EditorUtility.DisplayDialog("Prism", text, "OK");
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
                EditorUtility.DisplayDialog("Prism", $"No definition can become a {target.Name} without losing fields.", "OK");
        }

        /// <summary>Ask, then convert. Returns false when there was nothing to convert.</summary>
        static bool OfferConversion(Type target)
        {
            if (!PackageBuilder.IsDefinitionClass(target)) return false;
            var count = PreviewConversion(target).count;
            if (count == 0) return false;
            if (EditorUtility.DisplayDialog("Prism", $"Convert {count} existing definition(s) to {target.Name}? " +
                    "Files, GUIDs and every existing field are kept; the new fields start empty.", "Convert", "Not now"))
            {
                try { ConvertDefinitions(target); }
                catch (Exception e) { Debug.LogException(e); EditorUtility.DisplayDialog("Prism", "Conversion failed: " + e.Message, "OK"); }
            }
            return true;
        }
    }
}
