using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    /// <summary>What a new model version renames, adds or removes compared to the imported one.</summary>
    public class HierarchyChanges
    {
        [JsonProperty("removedNodes")] public List<string> RemovedNodes = new List<string>();
        [JsonProperty("addedNodes")] public List<string> AddedNodes = new List<string>();
        [JsonProperty("removedMaterials")] public List<string> RemovedMaterials = new List<string>();
        [JsonProperty("addedMaterials")] public List<string> AddedMaterials = new List<string>();

        /// <summary>Removed (or renamed) nodes or materials can break remaps and overrides.</summary>
        [JsonProperty("isBreaking")]
        public bool IsBreaking => RemovedNodes.Count > 0 || RemovedMaterials.Count > 0;

        public JObject ToJson() => JObject.FromObject(this);
    }

    public static class HierarchyDiff
    {
        /// <summary>Task 7 implements the comparison; until then updates are never breaking.</summary>
        public static HierarchyChanges Compare(string existingAssetPath, string newSourceFile) => new HierarchyChanges();
    }
}
