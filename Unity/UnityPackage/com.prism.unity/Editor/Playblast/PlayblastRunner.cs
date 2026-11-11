using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Playables;
using Object = UnityEngine.Object;

namespace Prism.Unity.Editor
{
    public class PlayblastRequest
    {
        [JsonProperty("mode")] public string Mode = "turntable";
        [JsonProperty("targetPaths")] public string[] TargetPaths;
        [JsonProperty("cameraPath")] public string CameraPath;
        [JsonProperty("width")] public int Width = 1920;
        [JsonProperty("height")] public int Height = 1080;
        [JsonProperty("frames")] public int Frames = 120;
        [JsonProperty("fps")] public int Fps = 30;
        [JsonProperty("format")] public string Format = "png";
        [JsonProperty("comment")] public string Comment = "";
        [JsonProperty("task")] public string Task;
        [JsonProperty("entity")] public PrismEntity Entity;
        [JsonProperty("outputPath")] public string OutputPath;
    }

    public class PlayblastResult
    {
        [JsonProperty("outputPath")] public string OutputPath;
        [JsonProperty("version")] public string Version;
        [JsonProperty("frameCount")] public int FrameCount;
        [JsonProperty("entity")] public PrismEntity Entity;
        [JsonProperty("task")] public string Task;
    }

    public class PlayblastContext
    {
        public PrismEntity Entity;
        public string Task;
        public List<GameObject> Targets = new List<GameObject>();
        public Camera Camera;
    }

    /// <summary>Renders turntable or camera playblasts to image sequences or MP4.</summary>
    public static class PlayblastRunner
    {
        public const string TurntableTask = "Turntable";
        public const string FreeTask = "Playblast";

        /// <summary>What to render and which Prism entity / task it belongs to.</summary>
        public static PlayblastContext ResolveContext(PlayblastRequest req)
        {
            var ctx = new PlayblastContext();
            if (req.Mode == "free")
            {
                ctx.Camera = FindCamera(req.CameraPath);
                ctx.Entity = req.Entity ?? SceneBinding.ForActiveScene()?.Entity;
                ctx.Task = string.IsNullOrEmpty(req.Task) ? FreeTask : req.Task;
                if (ctx.Entity == null)
                    throw new PrismCommandException(ErrorCodes.NeedsInput,
                        "This scene is not saved in Prism, so the playblast has no Prism entity. Save a version first or pass an entity.",
                        new JObject { ["missing"] = new JArray("entity") });
                return ctx;
            }
            if (req.Mode != "turntable")
                throw new PrismCommandException(ErrorCodes.BadArgs, "mode must be 'turntable' or 'free'.");

            ctx.Targets = req.TargetPaths != null && req.TargetPaths.Length > 0
                ? req.TargetPaths.Select(FindObject).ToList()
                : Selection.gameObjects.Where(g => g.scene.IsValid()).ToList();
            if (ctx.Targets.Count == 0)
                throw new PrismCommandException(ErrorCodes.NeedsInput, "Select the objects for the turntable (or pass targetPaths).",
                    new JObject { ["missing"] = new JArray("targets") });
            ctx.Entity = req.Entity ?? EntityOf(ctx.Targets[0]);
            ctx.Task = string.IsNullOrEmpty(req.Task) ? TurntableTask : req.Task;
            if (ctx.Entity == null)
                throw new PrismCommandException(ErrorCodes.NeedsInput,
                    $"'{ctx.Targets[0].name}' was not imported from Prism, so the turntable has no Prism asset. Pass an entity.",
                    new JObject { ["missing"] = new JArray("entity") });
            return ctx;
        }

        /// <summary>Render to outputPath: a #### frame pattern for PNG, or a .mp4 file.</summary>
        public static PlayblastResult Run(PlayblastRequest req, string outputPath)
        {
            if (string.IsNullOrEmpty(outputPath))
                throw new PrismCommandException(ErrorCodes.BadArgs, "Missing outputPath.");
            if (req.Frames <= 0 || req.Frames > 10000) throw new PrismCommandException(ErrorCodes.BadArgs, "frames must be 1..10000.");
            if (req.Fps <= 0) throw new PrismCommandException(ErrorCodes.BadArgs, "fps must be positive.");
            var ctx = ResolveContext(req);
            var video = req.Format == "mp4" || outputPath.EndsWith(".mp4", StringComparison.OrdinalIgnoreCase);
            var frameDir = video
                ? Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnity", "pb_" + Guid.NewGuid().ToString("N"))
                : Path.GetDirectoryName(outputPath);
            var pattern = video ? Path.Combine(frameDir, "frame.####.png") : WithFrameToken(outputPath);
            Directory.CreateDirectory(frameDir);
            try
            {
                if (req.Mode == "free") RenderCamera(ctx.Camera, req, pattern);
                else RenderTurntable(ctx.Targets, req, pattern);
                if (video) Encode(frameDir, req.Fps, outputPath);
            }
            finally
            {
                if (video && Directory.Exists(frameDir)) Directory.Delete(frameDir, true);
            }
            return new PlayblastResult
            {
                OutputPath = (video ? outputPath : pattern).Replace('\\', '/'),
                FrameCount = req.Frames,
                Entity = ctx.Entity,
                Task = ctx.Task,
            };
        }

        static void RenderTurntable(List<GameObject> targets, PlayblastRequest req, string pattern)
        {
            using (var rig = new TurntableRig(targets, req.Width, req.Height))
            {
                for (var i = 0; i < req.Frames; i++)
                {
                    rig.SetAngle(360f * i / req.Frames);
                    FrameCapture.CaptureFrame(rig.Camera, req.Width, req.Height, FramePath(pattern, i + 1));
                }
            }
        }

        static void RenderCamera(Camera cam, PlayblastRequest req, string pattern)
        {
            var directors = Object.FindObjectsByType<PlayableDirector>(FindObjectsSortMode.None);
            var saved = directors.Select(d => d.time).ToArray();
            try
            {
                for (var i = 0; i < req.Frames; i++)
                {
                    foreach (var d in directors)
                    {
                        d.time = (double)i / req.Fps;
                        d.Evaluate();
                    }
                    FrameCapture.CaptureFrame(cam, req.Width, req.Height, FramePath(pattern, i + 1));
                }
            }
            finally
            {
                for (var i = 0; i < directors.Length; i++)
                {
                    directors[i].time = saved[i];
                    directors[i].Evaluate();
                }
            }
        }

        static void Encode(string frameDir, int fps, string mp4)
        {
            var ffmpeg = Path.Combine(PrismSettings.PrismRoot, "Tools", "FFmpeg", "bin", "ffmpeg.exe");
            if (!File.Exists(ffmpeg))
                throw new PrismCommandException(ErrorCodes.MissingPackage, $"MP4 needs Prism's FFmpeg, not found at {ffmpeg}. Use format 'png'.");
            Directory.CreateDirectory(Path.GetDirectoryName(mp4));
            var psi = new ProcessStartInfo
            {
                FileName = ffmpeg,
                Arguments = $"-y -loglevel error -framerate {fps} -start_number 1 -i \"{Path.Combine(frameDir, "frame.%04d.png")}\" " +
                            $"-c:v libx264 -pix_fmt yuv420p -r {fps} -vf \"scale=trunc(iw/2)*2:trunc(ih/2)*2\" \"{mp4}\"",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardError = true,
            };
            using (var p = Process.Start(psi))
            {
                var err = p.StandardError.ReadToEnd();
                p.WaitForExit();
                if (p.ExitCode != 0 || !File.Exists(mp4))
                    throw new PrismCommandException(ErrorCodes.Internal, $"FFmpeg failed ({p.ExitCode}): {err}");
            }
        }

        static readonly Regex FrameToken = new Regex("#+");

        static string WithFrameToken(string path) =>
            FrameToken.IsMatch(Path.GetFileName(path))
                ? path
                : Path.Combine(Path.GetDirectoryName(path), Path.GetFileNameWithoutExtension(path) + ".####" + Path.GetExtension(path));

        static string FramePath(string pattern, int frame)
        {
            var dir = Path.GetDirectoryName(pattern);
            var name = FrameToken.Replace(Path.GetFileName(pattern), m => frame.ToString(new string('0', m.Length)), 1);
            return Path.Combine(dir, name);
        }

        static PrismEntity EntityOf(GameObject go)
        {
            var source = PrefabUtility.GetCorrespondingObjectFromOriginalSource(go) ?? go;
            var path = AssetDatabase.GetAssetPath(source);
            return string.IsNullOrEmpty(path) ? null : ImportRecord.FindByAssetPath(path)?.Entity;
        }

        static GameObject FindObject(string hierarchyPath)
        {
            var scene = EditorSceneManager.GetActiveScene();
            foreach (var root in scene.GetRootGameObjects())
            {
                if (root.name == hierarchyPath) return root;
                var prefix = root.name + "/";
                if (hierarchyPath.StartsWith(prefix))
                {
                    var t = root.transform.Find(hierarchyPath.Substring(prefix.Length));
                    if (t != null) return t.gameObject;
                }
            }
            throw new PrismCommandException(ErrorCodes.BadArgs, $"No object '{hierarchyPath}' in the active scene.");
        }

        static Camera FindCamera(string path)
        {
            if (!string.IsNullOrEmpty(path))
                return FindObject(path).GetComponent<Camera>() ??
                       throw new PrismCommandException(ErrorCodes.BadArgs, $"'{path}' has no Camera.");
            return Camera.main ?? Object.FindObjectsByType<Camera>(FindObjectsSortMode.None).FirstOrDefault() ??
                   throw new PrismCommandException(ErrorCodes.NeedsInput, "The scene has no camera; pass cameraPath.",
                       new JObject { ["missing"] = new JArray("cameraPath") });
        }

        public static string HierarchyPath(Transform t) => t.parent == null ? t.name : HierarchyPath(t.parent) + "/" + t.name;

        internal static void Register()
        {
            CommandRegistry.Register("listCameras", (a, c) => new JArray(
                Object.FindObjectsByType<Camera>(FindObjectsSortMode.None)
                    .Where(cam => cam.gameObject.scene == EditorSceneManager.GetActiveScene())
                    .OrderBy(cam => HierarchyPath(cam.transform))
                    .Select(cam => new JObject { ["name"] = cam.name, ["path"] = HierarchyPath(cam.transform) })), false);
            CommandRegistry.Register("playblastContext", (a, c) =>
            {
                var ctx = ResolveContext(a.ToObject<PlayblastRequest>());
                return new JObject { ["entity"] = ctx.Entity.ToJson(), ["task"] = ctx.Task };
            }, false);
            CommandRegistry.Register("playblast", (a, c) =>
            {
                var req = a.ToObject<PlayblastRequest>();
                if (string.IsNullOrEmpty(req.OutputPath))
                    throw new PrismCommandException(ErrorCodes.BadArgs, "Missing outputPath (Prism resolves it before calling Unity).");
                return JObject.FromObject(Run(req, req.OutputPath));
            }, false);
        }
    }
}
