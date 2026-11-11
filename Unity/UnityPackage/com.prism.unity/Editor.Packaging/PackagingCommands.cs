using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using Prism.Assets;
using UnityEditor;
using UnityEngine;

namespace Prism.Unity.Editor.Packaging
{
    /// <summary>Commands and hooks of the packaging assembly.</summary>
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
        }

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
    }
}
