using System.IO;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Prism.Unity.Editor.Tests
{
    public class PlayblastRunnerTests
    {
        ImportFixture _fx;
        string _outDir;

        [SetUp]
        public void SetUp()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            _fx = new ImportFixture();
            _outDir = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "pb", Path.GetRandomFileName());
            Directory.CreateDirectory(_outDir);
        }

        [TearDown]
        public void TearDown()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Selection.objects = new Object[0];
            if (Directory.Exists(SceneBinding.Folder)) Directory.Delete(SceneBinding.Folder, true);
            AssetDatabase.DeleteAsset("Assets/Scenes/MeditationRoom");
            _fx.Cleanup();
            if (Directory.Exists(_outDir)) Directory.Delete(_outDir, true);
        }

        GameObject PlaceLotus()
        {
            var r = ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v1.fbx", "v0001"), false);
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(r.Record.AssetPath));
            return instance;
        }

        [Test]
        public void TurntableEntityFromImportRecord()
        {
            var lotus = PlaceLotus();
            Selection.activeGameObject = lotus;
            var ctx = PlayblastRunner.ResolveContext(new PlayblastRequest { Mode = "turntable" });
            Assert.AreEqual("Props/Lotus", ctx.Entity.AssetPath);
            Assert.AreEqual("Turntable", ctx.Task);
            Assert.AreEqual(lotus, ctx.Targets[0]);
        }

        [Test]
        public void TurntableTargetsByPath()
        {
            var lotus = PlaceLotus();
            lotus.name = "LotusInScene";
            var ctx = PlayblastRunner.ResolveContext(new PlayblastRequest { Mode = "turntable", TargetPaths = new[] { "LotusInScene" } });
            Assert.AreEqual(lotus, ctx.Targets[0]);
        }

        [Test]
        public void TurntableNonPrismTargetNeedsInput()
        {
            Selection.activeGameObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var ex = Assert.Throws<PrismCommandException>(() => PlayblastRunner.ResolveContext(new PlayblastRequest { Mode = "turntable" }));
            Assert.AreEqual(ErrorCodes.NeedsInput, ex.Code);
            Assert.AreEqual("entity", (string)ex.Details["missing"][0]);
        }

        [Test]
        public void TurntableNonPrismTargetWithEntityWorks()
        {
            Selection.activeGameObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var ctx = PlayblastRunner.ResolveContext(new PlayblastRequest { Mode = "turntable", Entity = PrismEntity.Asset("Props/Lotus") });
            Assert.AreEqual("Props/Lotus", ctx.Entity.AssetPath);
        }

        [Test]
        public void TurntableWithoutSelectionNeedsInput()
        {
            var ex = Assert.Throws<PrismCommandException>(() => PlayblastRunner.ResolveContext(new PlayblastRequest { Mode = "turntable" }));
            Assert.AreEqual(ErrorCodes.NeedsInput, ex.Code);
        }

        [Test]
        public void FreeModeWithoutBindingNeedsInput()
        {
            new GameObject("Cam").AddComponent<Camera>();
            var ex = Assert.Throws<PrismCommandException>(() => PlayblastRunner.ResolveContext(new PlayblastRequest { Mode = "free", CameraPath = "Cam" }));
            Assert.AreEqual(ErrorCodes.NeedsInput, ex.Code);
        }

        [Test]
        public void FreeModeUsesSceneBinding()
        {
            new GameObject("Cam").AddComponent<Camera>();
            SceneVersioning.Bind(PrismEntity.Asset("Scenes/MeditationRoom"), "Unity", "layout");
            var ctx = PlayblastRunner.ResolveContext(new PlayblastRequest { Mode = "free", CameraPath = "Cam" });
            Assert.AreEqual("Scenes/MeditationRoom", ctx.Entity.AssetPath);
            Assert.AreEqual("Playblast", ctx.Task);
            Assert.AreEqual("Cam", ctx.Camera.name);
        }

        [Test]
        public void WritesRequestedFrameCount()
        {
            Selection.activeGameObject = PlaceLotus();
            var pattern = Path.Combine(_outDir, "Lotus_Turntable_v0001.####.png").Replace('\\', '/');
            var result = PlayblastRunner.Run(new PlayblastRequest { Mode = "turntable", Frames = 12, Width = 64, Height = 64 }, pattern);
            Assert.AreEqual(12, result.FrameCount);
            Assert.AreEqual(12, Directory.GetFiles(_outDir, "*.png").Length);
            Assert.IsTrue(File.Exists(Path.Combine(_outDir, "Lotus_Turntable_v0001.0001.png")));
            Assert.IsTrue(File.Exists(Path.Combine(_outDir, "Lotus_Turntable_v0001.0012.png")));
            Assert.AreEqual(pattern, result.OutputPath);
        }

        [Test]
        public void Mp4UsesFfmpeg()
        {
            Selection.activeGameObject = PlaceLotus();
            var mp4 = Path.Combine(_outDir, "Lotus_Turntable_v0002.mp4").Replace('\\', '/');
            var result = PlayblastRunner.Run(new PlayblastRequest { Mode = "turntable", Frames = 6, Width = 64, Height = 64, Format = "mp4" }, mp4);
            Assert.IsTrue(File.Exists(mp4));
            Assert.Greater(new FileInfo(mp4).Length, 100);
            Assert.AreEqual(1, Directory.GetFiles(_outDir).Length, "Only the video remains; temporary frames are removed.");
            Assert.AreEqual(6, result.FrameCount);
        }

        [Test]
        public void PlayblastCommandRequiresOutputPath()
        {
            Assert.IsTrue(CommandRegistry.TryGet("playblast", out var h, out var mutates));
            Assert.IsFalse(mutates, "a playblast does not change the project");
            var ex = Assert.Throws<PrismCommandException>(() => h(new JObject { ["mode"] = "turntable" }, new CommandContext()));
            Assert.AreEqual(ErrorCodes.BadArgs, ex.Code);
        }

        [Test]
        public void ListCamerasReturnsSceneCameras()
        {
            var root = new GameObject("Rig");
            var cam = new GameObject("ShotCam");
            cam.transform.SetParent(root.transform);
            cam.AddComponent<Camera>();
            Assert.IsTrue(CommandRegistry.TryGet("listCameras", out var h, out _));
            var list = (JArray)h(new JObject(), new CommandContext());
            Assert.AreEqual(1, list.Count);
            Assert.AreEqual("ShotCam", (string)list[0]["name"]);
            Assert.AreEqual("Rig/ShotCam", (string)list[0]["path"]);
        }

        [Test]
        public void PlayblastContextCommandReturnsEntityAndTask()
        {
            Selection.activeGameObject = PlaceLotus();
            Assert.IsTrue(CommandRegistry.TryGet("playblastContext", out var h, out _));
            var ctx = h(new JObject { ["mode"] = "turntable" }, new CommandContext());
            Assert.AreEqual("Props/Lotus", (string)ctx["entity"]["asset_path"]);
            Assert.AreEqual("Turntable", (string)ctx["task"]);
        }
    }
}
