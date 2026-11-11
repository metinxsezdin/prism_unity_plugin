using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using UnityEditor;
using UnityEditor.SceneManagement;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// Which Prism entity / department / task a Unity scene is saved under, and its last Prism
    /// version. One file per scene: ProjectSettings/PrismUnity/scenes/&lt;scene guid&gt;.json.
    /// </summary>
    public class SceneBinding
    {
        [JsonProperty("sceneGuid")] public string SceneGuid;
        [JsonProperty("workingPath")] public string WorkingPath;
        [JsonProperty("entity")] public PrismEntity Entity;
        [JsonProperty("department")] public string Department;
        [JsonProperty("task")] public string Task;
        [JsonProperty("lastPrismPath")] public string LastPrismPath;

        public static string Folder => Path.Combine(PrismSettings.ProjectRoot, "ProjectSettings", "PrismUnity", "scenes");

        static string FileFor(string guid) => Path.Combine(Folder, guid + ".json");

        public static SceneBinding ForScenePath(string scenePath)
        {
            if (string.IsNullOrEmpty(scenePath)) return null;
            var guid = AssetDatabase.AssetPathToGUID(scenePath);
            if (string.IsNullOrEmpty(guid) || !File.Exists(FileFor(guid))) return null;
            return JsonConvert.DeserializeObject<SceneBinding>(File.ReadAllText(FileFor(guid)));
        }

        public static SceneBinding ForActiveScene() => ForScenePath(EditorSceneManager.GetActiveScene().path);

        /// <summary>The binding whose Prism versions live in the same task folder as prismScenefile.</summary>
        public static SceneBinding FindByPrismPath(string prismScenefile)
        {
            if (!Directory.Exists(Folder) || string.IsNullOrEmpty(prismScenefile)) return null;
            var dir = NormDir(prismScenefile);
            return Directory.GetFiles(Folder, "*.json")
                .Select(f => JsonConvert.DeserializeObject<SceneBinding>(File.ReadAllText(f)))
                .FirstOrDefault(b => b?.LastPrismPath != null && NormDir(b.LastPrismPath) == dir);
        }

        static string NormDir(string path) =>
            Path.GetFullPath(Path.GetDirectoryName(path) ?? "").TrimEnd('\\', '/').ToLowerInvariant();

        public void Save()
        {
            Directory.CreateDirectory(Folder);
            File.WriteAllText(FileFor(SceneGuid), JsonConvert.SerializeObject(this, Formatting.Indented) + "\n");
        }

        public static string DefaultWorkingPath(PrismEntity entity, string task) =>
            $"Assets/Scenes/{entity.Name}/{task}.unity";
    }
}
