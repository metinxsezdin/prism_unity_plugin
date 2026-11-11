using System.IO;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// The working scene always stays in Assets/. Saving a Prism version saves it in place and
    /// copies the .unity file to Prism's versioned path.
    /// </summary>
    public static class SceneVersioning
    {
        /// <summary>Bind the active scene to a Prism target, saving an untitled scene to its default path first.</summary>
        public static SceneBinding Bind(PrismEntity entity, string department, string task)
        {
            var scene = EditorSceneManager.GetActiveScene();
            if (string.IsNullOrEmpty(scene.path))
            {
                var path = SceneBinding.DefaultWorkingPath(entity, task);
                ProductImporter.EnsureFolder(Path.GetDirectoryName(path).Replace('\\', '/'));
                if (!EditorSceneManager.SaveScene(scene, path))
                    throw new PrismCommandException(ErrorCodes.Internal, $"Unity could not save the scene to {path}.");
            }
            var guid = AssetDatabase.AssetPathToGUID(scene.path);
            var binding = SceneBinding.ForScenePath(scene.path) ?? new SceneBinding { SceneGuid = guid };
            binding.WorkingPath = scene.path;
            binding.Entity = entity;
            binding.Department = department;
            binding.Task = task;
            binding.Save();
            return binding;
        }

        /// <summary>Save the active scene in place, copy it to prismPath, remember it as the last version.</summary>
        public static string SaveTo(string prismPath)
        {
            var scene = EditorSceneManager.GetActiveScene();
            var binding = SceneBinding.ForActiveScene();
            if (binding == null)
                throw new PrismCommandException(ErrorCodes.BadArgs, "The active scene is not bound to a Prism target yet (bindScene).");
            if (!EditorSceneManager.SaveScene(scene))
                throw new PrismCommandException(ErrorCodes.Internal, $"Unity could not save {scene.path}.");

            Directory.CreateDirectory(Path.GetDirectoryName(prismPath));
            File.Copy(Path.Combine(PrismSettings.ProjectRoot, scene.path), prismPath, true);
            binding.WorkingPath = scene.path;
            binding.LastPrismPath = prismPath.Replace('\\', '/');
            binding.Save();
            return scene.path;
        }

        internal static void Register()
        {
            CommandRegistry.Register("getSceneBinding", (a, c) =>
            {
                var b = SceneBinding.ForActiveScene();
                return b == null ? JValue.CreateNull() : JObject.FromObject(b);
            }, false);
            CommandRegistry.Register("bindScene", (a, c) => JObject.FromObject(
                Bind(UnityCommands.RequireEntity(a), UnityCommands.RequireString(a, "department"), UnityCommands.RequireString(a, "task"))), true);
            CommandRegistry.Register("saveSceneTo", (a, c) =>
                new JObject { ["workingPath"] = SaveTo(UnityCommands.RequireString(a, "path")) }, true);
        }
    }
}
