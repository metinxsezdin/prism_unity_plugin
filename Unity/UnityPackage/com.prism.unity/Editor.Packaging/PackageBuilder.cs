using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Prism.Assets;
using UnityEditor;
using UnityEditor.AddressableAssets;
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
        /// <summary>The prefab's Addressable address as registered; null when it is not addressable (e.g. address collision).</summary>
        [JsonProperty("addressableKey")] public string AddressableKey;
        [JsonProperty("thumbnailPath")] public string ThumbnailPath;
        [JsonProperty("warning", NullValueHandling = NullValueHandling.Ignore)] public string Warning;
    }

    /// <summary>
    /// Builds the package of an imported product next to its model:
    /// prefab variant, definition, thumbnail, Addressable entries and the catalog entry.
    /// The prefab and the definition file are only ever created, never replaced: the team owns them.
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
            var info = new PackageInfo
            {
                PrefabPath = $"{folder}/{record.Product}.prefab",
                DefinitionPath = $"{folder}/{record.Product}.asset",
                ThumbnailPath = $"{folder}/{record.Product}_thumb.png",
            };
            // The team may have moved or renamed the prefab: follow the definition's reference.
            var linked = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(info.DefinitionPath)?.prefab?.AssetGUID;
            var linkedPath = string.IsNullOrEmpty(linked) ? null : AssetDatabase.GUIDToAssetPath(linked);
            if (!string.IsNullOrEmpty(linkedPath) && AssetDatabase.LoadAssetAtPath<GameObject>(linkedPath) != null)
                info.PrefabPath = linkedPath;
            info.AddressableKey = AddressableAssetSettingsDefaultObject.Settings?.FindAssetEntry(AssetDatabase.AssetPathToGUID(info.PrefabPath))?.address;
            Warnings.TryGetValue(record.Id, out info.Warning);
            return info;
        }

        public static PackageInfo Ensure(ImportRecord record, string previewPath)
        {
            var settings = PackagingSettings.Load();
            var info = Describe(record);
            var warnings = new List<string>();

            EnsurePrefab(record.AssetPath, info.PrefabPath);
            WriteThumbnail(record.AssetPath, previewPath, info.ThumbnailPath);
            var definition = EnsureDefinition(info.DefinitionPath, settings, warnings);
            if (definition != null)
            {
                definition.entityType = record.Entity.Type;
                definition.entityPath = record.Entity.Path;
                definition.product = record.Product;
                definition.version = record.Version;
                definition.contentVersion = record.ContentVersion ?? record.Version;
                if (string.IsNullOrEmpty(definition.displayName)) definition.displayName = record.Entity.Name;
                definition.prismMissing = false;
                definition.prefab = new AssetReferenceGameObject(AssetDatabase.AssetPathToGUID(info.PrefabPath));
                definition.thumbnail = new AssetReferenceTexture2D(AssetDatabase.AssetPathToGUID(info.ThumbnailPath));
                // Save before registering: Addressables may reload the asset, which would drop unsaved values.
                EditorUtility.SetDirty(definition);
                AssetDatabase.SaveAssetIfDirty(definition);
            }

            RegisterAll(record, info, definition, settings, warnings);
            AssetDatabase.SaveAssets();
            return info;
        }

        /// <summary>Redo the cheap part (Addressable entries, catalog) of a complete package. Nothing is rendered or created.</summary>
        public static PackageInfo Repair(ImportRecord record)
        {
            var info = Describe(record);
            var warnings = new List<string>();
            RegisterAll(record, info, AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(info.DefinitionPath), PackagingSettings.Load(), warnings);
            AssetDatabase.SaveAssets();
            return info;
        }

        /// <summary>
        /// Register prefab, definition and thumbnail independently (a collision on one never skips the others),
        /// store the address the prefab actually has as the definition's key, and list the definition in the catalog.
        /// </summary>
        static void RegisterAll(ImportRecord record, PackageInfo info, PrismAssetDefinition definition, PackagingSettings settings, List<string> warnings)
        {
            var address = settings.FormatAddress(record.Entity, record.Product);
            var group = settings.FormatGroup(record.Entity);
            var labels = new[] { "prism", PackagingSettings.Category(record.Entity), record.Product };

            info.AddressableKey = Register(info.PrefabPath, address, group, labels, warnings);
            Register(info.ThumbnailPath, address + "#thumb", group, labels, warnings);
            if (definition != null)
            {
                Register(info.DefinitionPath, address + "#definition", group, labels, warnings);
                definition.addressableKey = info.AddressableKey ?? "";
                EditorUtility.SetDirty(definition);
                AssetDatabase.SaveAssetIfDirty(definition);
                CatalogUpdater.Add(definition);
            }

            info.Warning = warnings.Count == 0 ? null : string.Join(" ", warnings);
            if (info.Warning != null) Debug.LogWarning("[Prism] " + info.Warning);
            Warnings[record.Id] = info.Warning;
        }

        static string Register(string assetPath, string address, string group, string[] labels, List<string> warnings)
        {
            var guid = AssetDatabase.AssetPathToGUID(assetPath);
            if (string.IsNullOrEmpty(guid)) return null;
            var registered = AddressablesRegistrar.Register(guid, address, group, labels, out var warning);
            if (warning != null) warnings.Add(warning);
            return registered;
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

        /// <summary>The existing definition, a new one when there is no file, or null (with a warning) when a file exists that does not load as one.</summary>
        static PrismAssetDefinition EnsureDefinition(string path, PackagingSettings settings, List<string> warnings)
        {
            var existing = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(path);
            if (existing != null) return existing;
            if (File.Exists(Path.Combine(PrismSettings.ProjectRoot, path)))
            {
                // Typically the team renamed its definition class. Replacing the file would lose its fields and GUID.
                warnings.Add($"{path} exists but does not load as a {nameof(PrismAssetDefinition)} (renamed or missing script?). " +
                             "It was left untouched; fix the script reference to update it.");
                return null;
            }
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
