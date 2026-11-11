using System.IO;
using Newtonsoft.Json;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// Asset packaging settings, shared with the team through ProjectSettings/PrismUnity/settings.json.
    /// Tokens in the formats: {entity} (e.g. Props/Lotus), {product}, {category} (first folder of the entity).
    /// </summary>
    public class PackagingSettings
    {
        [JsonProperty("enabled")] public bool Enabled = true;
        [JsonProperty("definitionType")] public string DefinitionType = DefaultDefinitionType;
        [JsonProperty("addressFormat")] public string AddressFormat = "{entity}/{product}";
        [JsonProperty("groupFormat")] public string GroupFormat = "Prism {category}";

        public const string DefaultDefinitionType = "Prism.Assets.PrismAssetDefinition, Prism.Assets";

        public static string FilePath => Path.Combine(PrismSettings.ProjectRoot, "ProjectSettings", "PrismUnity", "settings.json");

        public static PackagingSettings Load()
        {
            try
            {
                return File.Exists(FilePath)
                    ? JsonConvert.DeserializeObject<PackagingSettings>(File.ReadAllText(FilePath)) ?? new PackagingSettings()
                    : new PackagingSettings();
            }
            catch (JsonException)
            {
                UnityEngine.Debug.LogWarning($"[Prism] {FilePath} is not valid JSON; using default packaging settings.");
                return new PackagingSettings();
            }
        }

        public void Save()
        {
            Directory.CreateDirectory(Path.GetDirectoryName(FilePath));
            File.WriteAllText(FilePath, JsonConvert.SerializeObject(this, Formatting.Indented) + "\n");
        }

        public static string Category(PrismEntity e)
        {
            var path = e?.Path ?? "";
            var slash = path.IndexOf('/');
            return slash < 0 ? path : path.Substring(0, slash);
        }

        public string FormatAddress(PrismEntity e, string product) => Apply(AddressFormat, e, product);

        public string FormatGroup(PrismEntity e) => Apply(GroupFormat, e, "");

        static string Apply(string format, PrismEntity e, string product) =>
            (format ?? "").Replace("{entity}", e?.Path ?? "").Replace("{product}", product ?? "").Replace("{category}", Category(e));
    }
}
