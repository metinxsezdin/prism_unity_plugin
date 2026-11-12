using System.Collections.Generic;
using System.IO;
using System.Linq;
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
        [JsonProperty("addressFormat")] public string AddressFormat = DefaultAddressFormat;
        [JsonProperty("groupFormat")] public string GroupFormat = DefaultGroupFormat;

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

        public const string DefaultAddressFormat = "{entity}/{product}";
        public const string DefaultGroupFormat = "Prism {category}";

        /// <summary>What is wrong with the formats, for the settings page; empty when they are fine.</summary>
        public List<string> Problems()
        {
            var problems = new List<string>();
            var address = Effective(AddressFormat, DefaultAddressFormat);
            if (!address.Contains("{product}") || !(address.Contains("{entity}")))
                problems.Add("The address format needs both {entity} and {product}; otherwise several products get the same address and only the first one is addressable.");
            return problems;
        }

        public static string Category(PrismEntity e)
        {
            var path = e?.Path ?? "";
            var slash = path.IndexOf('/');
            return slash < 0 ? path : path.Substring(0, slash);
        }

        /// <summary>An empty format means the default.</summary>
        public string FormatAddress(PrismEntity e, string product) => Apply(Effective(AddressFormat, DefaultAddressFormat), e, product);

        /// <summary>The group name is also a file name: slashes and other characters a file name cannot hold become '-'.</summary>
        public string FormatGroup(PrismEntity e)
        {
            var name = Apply(Effective(GroupFormat, DefaultGroupFormat), e, "");
            var invalid = Path.GetInvalidFileNameChars();
            return new string(name.Select(c => invalid.Contains(c) ? '-' : c).ToArray()).Trim();
        }

        static string Effective(string format, string fallback) => string.IsNullOrWhiteSpace(format) ? fallback : format;

        static string Apply(string format, PrismEntity e, string product) =>
            (format ?? "").Replace("{entity}", e?.Path ?? "").Replace("{product}", product ?? "").Replace("{category}", Category(e));
    }
}
