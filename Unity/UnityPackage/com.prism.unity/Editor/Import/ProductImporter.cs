using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using UnityEditor;

namespace Prism.Unity.Editor
{
    /// <summary>A product version as Prism resolved it.</summary>
    public class ResolvedVersion
    {
        [JsonProperty("version")] public string Version;
        [JsonProperty("filepath")] public string FilePath;
        [JsonProperty("location")] public string Location;
    }

    public class ImportResult
    {
        [JsonProperty("record")] public ImportRecord Record;
        [JsonProperty("updated")] public bool Updated;
        [JsonProperty("changes", NullValueHandling = NullValueHandling.Ignore)] public HierarchyChanges Changes;
    }

    /// <summary>
    /// Copies a Prism product version into Assets/Prism/&lt;entity&gt;/&lt;product&gt;/&lt;product&gt;&lt;ext&gt;.
    /// The path never contains a version, and updates overwrite the same file, so the .meta and
    /// GUID stay and every reference to the model (scenes, prefabs, material remaps) survives.
    /// </summary>
    public static class ProductImporter
    {
        public const string Root = "Assets/Prism";
        static readonly string[] Supported = { ".fbx", ".obj", ".abc" };
        const string AlembicPackage = "com.unity.formats.alembic";

        public static string TargetPath(PrismEntity entity, string product, string extension) =>
            $"{Root}/{entity.Path}/{product}/{product}{extension}";

        public static ImportResult ImportResolved(PrismEntity entity, string product, ResolvedVersion v, bool confirm)
        {
            if (entity == null || string.IsNullOrEmpty(entity.Path))
                throw new PrismCommandException(ErrorCodes.BadArgs, "An entity is required.");
            if (string.IsNullOrEmpty(product) || product.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
                throw new PrismCommandException(ErrorCodes.BadArgs, $"Invalid product name '{product}'.");

            var ext = Path.GetExtension(v.FilePath ?? "").ToLowerInvariant();
            if (!Supported.Contains(ext))
                throw new PrismCommandException(ErrorCodes.BadArgs,
                    $"Unity cannot import '{ext}' files from Prism. Supported: {string.Join(", ", Supported)}.");
            if (ext == ".abc" && !IsPackageInstalled(AlembicPackage))
                throw new PrismCommandException(ErrorCodes.MissingPackage,
                    $"Importing Alembic (.abc) needs the {AlembicPackage} package. Add it in Package Manager and try again.");
            if (!File.Exists(v.FilePath))
                throw new PrismCommandException(ErrorCodes.SourceUnavailable,
                    $"The Prism file is not reachable: {v.FilePath}. Check that the project drive is connected.");

            var target = TargetPath(entity, product, ext);
            var targetFull = Path.Combine(PrismSettings.ProjectRoot, target);
            var updated = File.Exists(targetFull);

            HierarchyChanges changes = null;
            if (updated)
            {
                changes = HierarchyDiff.Compare(target, v.FilePath);
                if (changes.IsBreaking && !confirm)
                    throw new PrismCommandException(ErrorCodes.NeedsConfirmation,
                        "The new version renames or removes objects or materials; material assignments and overrides on them may break. Confirm to update anyway.",
                        changes.ToJson());
            }

            EnsureFolder(Path.GetDirectoryName(target).Replace('\\', '/'));
            CopyAtomically(v.FilePath, targetFull);
            AssetDatabase.ImportAsset(target, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);

            var record = new ImportRecord
            {
                Id = ImportRecord.MakeId(entity, product),
                Entity = entity,
                Product = product,
                Version = v.Version,
                SourcePath = v.FilePath.Replace('\\', '/'),
                Location = v.Location,
                AssetPath = target,
                ImportedBy = Environment.UserName,
                ImportedAt = DateTime.UtcNow.ToString("o"),
            };
            record.Save();
            return new ImportResult { Record = record, Updated = updated, Changes = changes };
        }

        /// <summary>Copy next to the project (same volume), then swap into place in one step.</summary>
        static void CopyAtomically(string source, string targetFull)
        {
            var staging = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnity");
            Directory.CreateDirectory(staging);
            var tmp = Path.Combine(staging, Guid.NewGuid().ToString("N") + ".prismtmp");
            File.Copy(source, tmp, true);
            if (File.Exists(targetFull))
                File.Replace(tmp, targetFull, null);
            else
                File.Move(tmp, targetFull);
        }

        internal static void EnsureFolder(string assetFolder)
        {
            if (AssetDatabase.IsValidFolder(assetFolder)) return;
            var parent = Path.GetDirectoryName(assetFolder).Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(assetFolder));
        }

        static bool IsPackageInstalled(string name) =>
            UnityEditor.PackageManager.PackageInfo.GetAllRegisteredPackages().Any(p => p.name == name);
    }
}
