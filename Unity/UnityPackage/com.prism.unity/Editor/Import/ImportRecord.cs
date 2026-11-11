using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// Which Prism product version an imported Unity asset came from. One small JSON file per
    /// product under ProjectSettings/PrismUnity/imports/, so the team shares it through Git.
    /// </summary>
    public class ImportRecord
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("entity")] public PrismEntity Entity;
        [JsonProperty("product")] public string Product;
        [JsonProperty("version")] public string Version;
        [JsonProperty("sourcePath")] public string SourcePath;
        [JsonProperty("location")] public string Location;
        [JsonProperty("assetPath")] public string AssetPath;
        [JsonProperty("importedBy")] public string ImportedBy;
        [JsonProperty("importedAt")] public string ImportedAt;

        public static string Folder => Path.Combine(PrismSettings.ProjectRoot, "ProjectSettings", "PrismUnity", "imports");

        public static string MakeId(PrismEntity entity, string product) =>
            (entity.Type == "shot" ? $"{entity.Sequence}__{entity.Shot}" : (entity.AssetPath ?? "").Replace("/", "__")) + "__" + product;

        static string FileFor(string id) => Path.Combine(Folder, id + ".json");

        public static ImportRecord Load(string id)
        {
            var path = FileFor(id);
            return File.Exists(path) ? JsonConvert.DeserializeObject<ImportRecord>(File.ReadAllText(path)) : null;
        }

        public static IReadOnlyList<ImportRecord> LoadAll()
        {
            if (!Directory.Exists(Folder)) return new List<ImportRecord>();
            return Directory.GetFiles(Folder, "*.json")
                .Select(f => JsonConvert.DeserializeObject<ImportRecord>(File.ReadAllText(f)))
                .Where(r => r != null)
                .OrderBy(r => r.Id)
                .ToList();
        }

        /// <summary>The record whose imported asset is at this project-relative path, if any.</summary>
        public static ImportRecord FindByAssetPath(string assetPath) =>
            LoadAll().FirstOrDefault(r => string.Equals(r.AssetPath, assetPath, System.StringComparison.OrdinalIgnoreCase));

        public void Save()
        {
            Directory.CreateDirectory(Folder);
            File.WriteAllText(FileFor(Id), JsonConvert.SerializeObject(this, Formatting.Indented) + "\n");
        }
    }
}
