using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    /// <summary>A Prism entity in Prism's own dict shape: {"type":"asset","asset_path":...} or {"type":"shot",...}.</summary>
    public class PrismEntity
    {
        [JsonProperty("type")] public string Type;
        [JsonProperty("asset_path", NullValueHandling = NullValueHandling.Ignore)] public string AssetPath;
        [JsonProperty("sequence", NullValueHandling = NullValueHandling.Ignore)] public string Sequence;
        [JsonProperty("shot", NullValueHandling = NullValueHandling.Ignore)] public string Shot;

        public static PrismEntity Asset(string assetPath) => new PrismEntity { Type = "asset", AssetPath = assetPath };

        public JObject ToJson() => JObject.FromObject(this);

        public static PrismEntity FromJson(JObject json) => json?.ToObject<PrismEntity>();

        /// <summary>Folder-style path: "Props/Lotus" for assets, "sq01/sh010" for shots.</summary>
        [JsonIgnore]
        public string Path => Type == "shot" ? $"{Sequence}/{Shot}" : AssetPath;

        /// <summary>Last path segment, used for default file names.</summary>
        [JsonIgnore]
        public string Name
        {
            get
            {
                var p = (Path ?? "").TrimEnd('/');
                var i = p.LastIndexOf('/');
                return i < 0 ? p : p.Substring(i + 1);
            }
        }

        public override string ToString() => $"{Type}:{Path}";
    }
}
