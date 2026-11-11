using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;

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
                if (File.Exists(Path.Combine(PrismSettings.ProjectRoot, path)))
                    path = AssetDatabase.GenerateUniqueAssetPath(path); // never overwrite another scene
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

        /// <summary>
        /// Bring a Prism scene version into its working path in Assets/ and open it.
        /// unsaved: "abort" (fail with needs_confirmation if the active scene has changes), "save" or "discard".
        /// sourceProductGuid: the Unity project that saved the version; null reads it from Prism's version info.
        /// </summary>
        public static string OpenFrom(string prismPath, string unsaved, string sourceProductGuid, bool confirmForeign,
            PrismEntity entity = null, string department = null, string task = null)
        {
            if (!File.Exists(prismPath))
                throw new PrismCommandException(ErrorCodes.SourceUnavailable, $"The Prism scene file is not reachable: {prismPath}");

            var info = ReadVersionInfo(prismPath);
            sourceProductGuid = sourceProductGuid ?? (string)info["unityProductGuid"];
            entity = entity ?? (info["type"] != null ? info.ToObject<PrismEntity>() : null);
            department = department ?? (string)info["department"];
            task = task ?? (string)info["task"];

            var binding = SceneBinding.FindByPrismPath(prismPath);
            var working = binding?.WorkingPath;
            if (working == null)
            {
                if (entity == null || string.IsNullOrEmpty(task))
                    throw new PrismCommandException(ErrorCodes.NeedsInput,
                        "Prism has no target (entity and task) for this scene file, so Unity does not know where to put it.",
                        new JObject { ["missing"] = new JArray("entity", "task") });
                working = SceneBinding.DefaultWorkingPath(entity, task);
            }

            // Every loaded scene is replaced, not only the active one.
            var dirty = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt)
                .Where(s => s.isLoaded && s.isDirty).ToList();
            if (dirty.Count > 0)
            {
                switch (unsaved)
                {
                    case "discard":
                        break;
                    case "save":
                        foreach (var s in dirty)
                        {
                            if (string.IsNullOrEmpty(s.path))
                                throw new PrismCommandException(ErrorCodes.BadArgs, $"'{s.name}' was never saved; save it first or use unsaved='discard'.");
                            EditorSceneManager.SaveScene(s);
                        }
                        break;
                    default:
                        throw new PrismCommandException(ErrorCodes.NeedsConfirmation,
                            $"{string.Join(", ", dirty.Select(s => "'" + s.name + "'"))} has unsaved changes. Save them, discard them, or cancel.",
                            new JObject { ["reason"] = "unsaved_changes", ["scenes"] = new JArray(dirty.Select(s => s.path)) });
                }
            }

            // The working file is about to be overwritten. Unless the user said "discard", refuse when it
            // holds work that is not in Prism yet (saved with Ctrl+S, or just saved above).
            var workingFull = Path.Combine(PrismSettings.ProjectRoot, working);
            if (unsaved != "discard" && File.Exists(workingFull) && !SameContent(workingFull, prismPath))
            {
                var last = (SceneBinding.ForScenePath(working) ?? binding)?.LastPrismPath;
                if (last == null || !File.Exists(last) || !SameContent(workingFull, last))
                    throw new PrismCommandException(ErrorCodes.NeedsConfirmation,
                        $"{working} has changes that are not saved as a Prism version. Save a version first, or discard them.",
                        new JObject { ["reason"] = "unversioned_changes", ["workingPath"] = working });
            }

            var current = PlayerSettings.productGUID.ToString();
            if (!string.IsNullOrEmpty(sourceProductGuid) && sourceProductGuid != current && !confirmForeign)
                throw new PrismCommandException(ErrorCodes.NeedsConfirmation,
                    "This scene version was saved from a different Unity project; its asset references may not resolve here.",
                    new JObject { ["reason"] = "foreign_project", ["sourceProductGuid"] = sourceProductGuid });

            // Leave the target scene before overwriting its file, so Unity never reloads a half-written scene.
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            ProductImporter.EnsureFolder(Path.GetDirectoryName(working).Replace('\\', '/'));
            File.Copy(prismPath, Path.Combine(PrismSettings.ProjectRoot, working), true);
            AssetDatabase.ImportAsset(working, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);
            EditorSceneManager.OpenScene(working, OpenSceneMode.Single);

            binding = SceneBinding.ForScenePath(working) ?? binding ?? new SceneBinding();
            binding.SceneGuid = AssetDatabase.AssetPathToGUID(working);
            binding.WorkingPath = working;
            binding.Entity = entity ?? binding.Entity;
            binding.Department = department ?? binding.Department;
            binding.Task = task ?? binding.Task;
            binding.LastPrismPath = prismPath.Replace('\\', '/');
            binding.Save();
            return working;
        }

        static bool SameContent(string a, string b)
        {
            var fa = new FileInfo(a);
            var fb = new FileInfo(b);
            if (fa.Length != fb.Length) return false;
            return File.ReadAllBytes(a).AsSpan().SequenceEqual(File.ReadAllBytes(b));
        }

        /// <summary>Prism's version info next to a scene file: &lt;name&gt;versioninfo.json (empty if missing).</summary>
        public static JObject ReadVersionInfo(string prismPath)
        {
            var path = Path.Combine(Path.GetDirectoryName(prismPath), Path.GetFileNameWithoutExtension(prismPath) + "versioninfo.json");
            try
            {
                return File.Exists(path) ? JObject.Parse(File.ReadAllText(path)) : new JObject();
            }
            catch (Newtonsoft.Json.JsonException)
            {
                return new JObject();
            }
        }

        internal static void Register()
        {
            CommandRegistry.Register("openSceneFrom", (a, c) =>
            {
                var working = OpenFrom(UnityCommands.RequireString(a, "path"), (string)a["unsaved"] ?? "abort",
                    (string)a["sourceProductGuid"], (bool?)a["confirmForeign"] ?? false,
                    a["entity"] is JObject e ? PrismEntity.FromJson(e) : null, (string)a["department"], (string)a["task"]);
                return new JObject { ["workingPath"] = working };
            }, true);
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
