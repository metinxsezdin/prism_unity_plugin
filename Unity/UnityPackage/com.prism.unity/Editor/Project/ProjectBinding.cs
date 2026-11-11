using System.IO;
using Newtonsoft.Json;

namespace Prism.Unity.Editor
{
    /// <summary>The Prism project this Unity project is pinned to (ProjectSettings/PrismUnity/project.json).</summary>
    public class ProjectBinding
    {
        [JsonProperty("prismProjectConfig")] public string PrismProjectConfig;

        public static string FilePath => Path.Combine(PrismSettings.ProjectRoot, "ProjectSettings", "PrismUnity", "project.json");

        public static ProjectBinding Load() => LoadFrom(FilePath);

        public static ProjectBinding LoadFrom(string path) =>
            File.Exists(path) ? JsonConvert.DeserializeObject<ProjectBinding>(File.ReadAllText(path)) : null;

        public void Save()
        {
            Directory.CreateDirectory(Path.GetDirectoryName(FilePath));
            File.WriteAllText(FilePath, JsonConvert.SerializeObject(this, Formatting.Indented) + "\n");
        }

        public static void Delete()
        {
            if (File.Exists(FilePath)) File.Delete(FilePath);
        }
    }
}
