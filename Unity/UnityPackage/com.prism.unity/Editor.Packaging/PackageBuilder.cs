using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Prism.Assets;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AddressableAssets;
using Object = UnityEngine.Object;

namespace Prism.Unity.Editor.Packaging
{
    /// <summary>Paths and state of one product's package.</summary>
    public class PackageInfo
    {
        [JsonProperty("prefabPath")] public string PrefabPath;
        [JsonProperty("definitionPath")] public string DefinitionPath;
        [JsonProperty("addressableKey")] public string AddressableKey;
        [JsonProperty("thumbnailPath")] public string ThumbnailPath;
        [JsonProperty("warning", NullValueHandling = NullValueHandling.Ignore)] public string Warning;
    }

    /// <summary>
    /// Builds the package of an imported product next to its model:
    /// prefab variant, definition, thumbnail, Addressable entries and the catalog entry.
    /// The prefab and the team's definition fields are only ever created, never overwritten.
    /// </summary>
    [InitializeOnLoad]
    public static class PackageBuilder
    {
        const int ThumbnailSize = 256;
        static readonly Dictionary<string, string> Warnings = new Dictionary<string, string>();

        static PackageBuilder()
        {
            ProductImporter.Imported += (record, resolved) =>
            {
                if (PackagingSettings.Load().Enabled)
                    Ensure(record, resolved?.PreviewPath);
            };
        }

        public static PackageInfo Describe(ImportRecord record)
        {
            var folder = Path.GetDirectoryName(record.AssetPath).Replace('\\', '/');
            var settings = PackagingSettings.Load();
            Warnings.TryGetValue(record.Id, out var warning);
            return new PackageInfo
            {
                PrefabPath = $"{folder}/{record.Product}.prefab",
                DefinitionPath = $"{folder}/{record.Product}.asset",
                ThumbnailPath = $"{folder}/{record.Product}_thumb.png",
                AddressableKey = settings.FormatAddress(record.Entity, record.Product),
                Warning = warning,
            };
        }

        public static PackageInfo Ensure(ImportRecord record, string previewPath)
        {
            var settings = PackagingSettings.Load();
            var info = Describe(record);
            info.Warning = null;

            EnsurePrefab(record.AssetPath, info.PrefabPath);
            WriteThumbnail(record.AssetPath, previewPath, info.ThumbnailPath);
            var definition = EnsureDefinition(info.DefinitionPath, settings);

            definition.entityType = record.Entity.Type;
            definition.entityPath = record.Entity.Path;
            definition.product = record.Product;
            definition.version = record.Version;
            definition.contentVersion = record.ContentVersion ?? record.Version;
            definition.addressableKey = info.AddressableKey;
            if (string.IsNullOrEmpty(definition.displayName)) definition.displayName = record.Entity.Name;
            definition.prismMissing = false;
            definition.prefab = new AssetReferenceGameObject(AssetDatabase.AssetPathToGUID(info.PrefabPath));
            definition.thumbnail = new AssetReferenceTexture2D(AssetDatabase.AssetPathToGUID(info.ThumbnailPath));
            EditorUtility.SetDirty(definition);
            AssetDatabase.SaveAssetIfDirty(definition);

            var group = settings.FormatGroup(record.Entity);
            var labels = new[] { "prism", PackagingSettings.Category(record.Entity), record.Product };
            info.Warning = AddressablesRegistrar.Register(AssetDatabase.AssetPathToGUID(info.PrefabPath), info.AddressableKey, group, labels)
                           ?? AddressablesRegistrar.Register(AssetDatabase.AssetPathToGUID(info.DefinitionPath), info.AddressableKey + "#definition", group, labels)
                           ?? AddressablesRegistrar.Register(AssetDatabase.AssetPathToGUID(info.ThumbnailPath), info.AddressableKey + "#thumb", group, labels);
            if (info.Warning != null) Debug.LogWarning("[Prism] " + info.Warning);
            Warnings[record.Id] = info.Warning;

            CatalogUpdater.Add(definition);
            AssetDatabase.SaveAssets();
            return info;
        }

        /// <summary>A prefab variant of the model, created once. The team owns it afterwards.</summary>
        static void EnsurePrefab(string modelPath, string prefabPath)
        {
            if (AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath) != null) return;
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
            if (model == null) throw new InvalidOperationException($"No model at {modelPath} to make a prefab from.");
            // Instantiate in a preview scene so the user's open scene is never touched.
            var scene = EditorSceneManager.NewPreviewScene();
            try
            {
                var instance = (GameObject)PrefabUtility.InstantiatePrefab(model, scene);
                PrefabUtility.SaveAsPrefabAsset(instance, prefabPath);
            }
            finally
            {
                EditorSceneManager.ClosePreviewScene(scene);
            }
        }

        static PrismAssetDefinition EnsureDefinition(string path, PackagingSettings settings)
        {
            var existing = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(path);
            if (existing != null) return existing;
            var definition = (PrismAssetDefinition)ScriptableObject.CreateInstance(DefinitionType(settings));
            AssetDatabase.CreateAsset(definition, path);
            return definition;
        }

        /// <summary>The definition class chosen in Project Settings → Prism, or PrismAssetDefinition when it is unusable.</summary>
        public static Type DefinitionType(PackagingSettings settings)
        {
            var type = Type.GetType(settings.DefinitionType ?? "");
            return type != null && IsDefinitionClass(type) ? type : typeof(PrismAssetDefinition);
        }

        public static bool IsDefinitionClass(Type type) =>
            type != null && typeof(PrismAssetDefinition).IsAssignableFrom(type) && !type.IsAbstract;

        /// <summary>True when the record's prefab, definition and thumbnail all exist.</summary>
        public static bool IsComplete(ImportRecord record)
        {
            var info = Describe(record);
            return AssetDatabase.LoadAssetAtPath<GameObject>(info.PrefabPath) != null
                   && AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(info.DefinitionPath) != null
                   && AssetDatabase.LoadAssetAtPath<Texture2D>(info.ThumbnailPath) != null;
        }

        /// <summary>Prism's preview when there is one, else a single turntable frame of the model.</summary>
        static void WriteThumbnail(string modelPath, string previewPath, string thumbPath)
        {
            var full = Path.Combine(PrismSettings.ProjectRoot, thumbPath);
            byte[] png = null;
            if (!string.IsNullOrEmpty(previewPath) && File.Exists(previewPath))
            {
                // Prism previews are JPEGs; store PNG so the extension matches the content.
                var tex = new Texture2D(2, 2);
                try
                {
                    if (tex.LoadImage(File.ReadAllBytes(previewPath))) png = tex.EncodeToPNG();
                }
                finally
                {
                    Object.DestroyImmediate(tex);
                }
            }
            if (png != null)
            {
                File.WriteAllBytes(full, png);
            }
            else
            {
                var model = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
                using (var rig = new TurntableRig(new[] { model }, ThumbnailSize, ThumbnailSize))
                {
                    rig.SetAngle(30f);
                    FrameCapture.CaptureFrame(rig.Camera, ThumbnailSize, ThumbnailSize, full);
                }
            }

            AssetDatabase.ImportAsset(thumbPath, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);
            var importer = (TextureImporter)AssetImporter.GetAtPath(thumbPath);
            if (importer != null && (importer.mipmapEnabled || importer.maxTextureSize != ThumbnailSize))
            {
                importer.mipmapEnabled = false;
                importer.maxTextureSize = ThumbnailSize;
                importer.SaveAndReimport();
            }
        }
    }
}
