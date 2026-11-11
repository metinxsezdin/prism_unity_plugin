using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

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

    /// <summary>
    /// Compares node paths and source material names of two model files. Both the currently
    /// imported file and the new one are imported fresh into a staging folder with default
    /// settings, so the user's material remaps never hide a source material name.
    /// </summary>
    public static class HierarchyDiff
    {
        const string StagingRoot = "Assets/Prism/_staging";

        public static HierarchyChanges Compare(string existingAssetPath, string newSourceFile)
        {
            var ext = Path.GetExtension(existingAssetPath);
            var folder = $"{StagingRoot}/{Guid.NewGuid():N}";
            try
            {
                ProductImporter.EnsureFolder(folder);
                var oldPath = Stage(Path.Combine(PrismSettings.ProjectRoot, existingAssetPath), folder, "old" + ext);
                var newPath = Stage(newSourceFile, folder, "new" + Path.GetExtension(newSourceFile));
                var before = Describe(oldPath);
                var after = Describe(newPath);
                return new HierarchyChanges
                {
                    RemovedNodes = before.Nodes.Except(after.Nodes).OrderBy(n => n).ToList(),
                    AddedNodes = after.Nodes.Except(before.Nodes).OrderBy(n => n).ToList(),
                    RemovedMaterials = before.Materials.Except(after.Materials).OrderBy(n => n).ToList(),
                    AddedMaterials = after.Materials.Except(before.Materials).OrderBy(n => n).ToList(),
                };
            }
            finally
            {
                AssetDatabase.DeleteAsset(folder);
                if (AssetDatabase.IsValidFolder(StagingRoot) && AssetDatabase.GetSubFolders(StagingRoot).Length == 0
                    && Directory.GetFiles(Path.Combine(PrismSettings.ProjectRoot, StagingRoot)).All(f => f.EndsWith(".meta")))
                    AssetDatabase.DeleteAsset(StagingRoot);
            }
        }

        static string Stage(string sourceFile, string folder, string name)
        {
            var assetPath = $"{folder}/{name}";
            File.Copy(sourceFile, Path.Combine(PrismSettings.ProjectRoot, assetPath), true);
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);
            return assetPath;
        }

        struct Shape
        {
            public HashSet<string> Nodes;
            public HashSet<string> Materials;
        }

        static Shape Describe(string assetPath)
        {
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            var shape = new Shape { Nodes = new HashSet<string>(), Materials = new HashSet<string>() };
            if (root == null) return shape;
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                if (t == root.transform) continue;
                shape.Nodes.Add(AnimationUtility.CalculateTransformPath(t, root.transform));
            }
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                    if (m != null) shape.Materials.Add(m.name);
            return shape;
        }
    }
}
