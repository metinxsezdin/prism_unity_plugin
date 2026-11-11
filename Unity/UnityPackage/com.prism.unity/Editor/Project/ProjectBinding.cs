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

        /// <summary>
        /// Error text when newConfig is not the same Prism project as currentConfig (compared by
        /// globals.project_name), or cannot be read; null when it is the same project, moved.
        /// </summary>
        public static string ValidateRelocation(string newConfig, string currentConfig)
        {
            var newName = ProjectName(newConfig);
            if (newName == null) return $"Cannot read a Prism project at {newConfig}.";
            var currentName = ProjectName(currentConfig);
            if (currentName != null && currentName != newName)
                return $"{newConfig} is the Prism project '{newName}', not '{currentName}'. Only a moved copy of the same project can be set here.";
            return null;
        }

        /// <summary>Point this Unity project at the moved Prism project; Prism restarts on the next call.</summary>
        public static string Relocate(string newConfig)
        {
            var current = Load();
            var error = ValidateRelocation(newConfig, current?.PrismProjectConfig);
            if (error != null) return error;
            new ProjectBinding { PrismProjectConfig = newConfig.Replace('\\', '/') }.Save();
            PrismProcess.StopOwnedProcess();
            return null;
        }

        static string ProjectName(string config)
        {
            try
            {
                if (string.IsNullOrEmpty(config) || !File.Exists(config)) return null;
                return (string)Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(config))["globals"]?["project_name"];
            }
            catch (System.Exception e) when (e is IOException || e is JsonException)
            {
                return null;
            }
        }

        public static void Delete()
        {
            if (File.Exists(FilePath)) File.Delete(FilePath);
        }
    }
}
