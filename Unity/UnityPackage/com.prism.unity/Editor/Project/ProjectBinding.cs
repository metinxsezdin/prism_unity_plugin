using System.IO;
using Newtonsoft.Json;

namespace Prism.Unity.Editor
{
    /// <summary>The Prism project this Unity project is pinned to (ProjectSettings/PrismUnity/project.json).</summary>
    public class ProjectBinding
    {
        [JsonProperty("prismProjectConfig")] public string PrismProjectConfig;
        /// <summary>globals.project_name at bind time; lets a relocation be checked when the old path is gone.</summary>
        [JsonProperty("projectName", NullValueHandling = NullValueHandling.Ignore)] public string ProjectName;

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
        /// Error text when newConfig is not the same Prism project (compared by globals.project_name: the stored
        /// currentName, else read from currentConfig), or cannot be read; null when it is the same project, moved.
        /// </summary>
        public static string ValidateRelocation(string newConfig, string currentConfig, string currentName = null)
        {
            var newName = ReadProjectName(newConfig);
            if (newName == null) return $"Cannot read a Prism project at {newConfig}.";
            currentName = currentName ?? ReadProjectName(currentConfig);
            if (currentName != null && currentName != newName)
                return $"{newConfig} is the Prism project '{newName}', not '{currentName}'. Only a moved copy of the same project can be set here.";
            return null;
        }

        /// <summary>Point this Unity project at the moved Prism project; Prism restarts on the next call.</summary>
        public static string Relocate(string newConfig)
        {
            var current = Load();
            var error = ValidateRelocation(newConfig, current?.PrismProjectConfig, current?.ProjectName);
            if (error != null) return error;
            new ProjectBinding { PrismProjectConfig = newConfig.Replace('\\', '/'), ProjectName = ReadProjectName(newConfig) }.Save();
            PrismProcess.StopOwnedProcess();
            return null;
        }

        static string ReadProjectName(string config)
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
