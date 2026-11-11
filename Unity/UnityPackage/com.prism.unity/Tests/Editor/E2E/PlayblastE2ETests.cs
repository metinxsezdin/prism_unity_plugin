using System;
using System.Collections;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.TestTools;
using Prism.Unity.Editor.Tests.Support;

namespace Prism.Unity.Editor.Tests.E2E
{
    /// <summary>Turntables published to the real Prism test project, with no Prism window allowed.</summary>
    [Category("E2E")]
    public class PlayblastE2ETests
    {
        string _turntableFolder;

        [OneTimeSetUp]
        public void OneTimeSetUp()
        {
            PrismProcess.StopOwnedProcess();
            Environment.SetEnvironmentVariable("PRISM_UNITY_FAIL_ON_DIALOG", "1");
        }

        [OneTimeTearDown]
        public void OneTimeTearDown()
        {
            PrismProcess.StopOwnedProcess();
            Environment.SetEnvironmentVariable("PRISM_UNITY_FAIL_ON_DIALOG", null);
        }

        [TearDown]
        public void TearDown()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            AssetDatabase.DeleteAsset("Assets/Prism");
            if (Directory.Exists(ImportRecord.Folder)) Directory.Delete(ImportRecord.Folder, true);
            if (_turntableFolder != null && Directory.Exists(_turntableFolder)) Directory.Delete(_turntableFolder, true);
        }

        [UnityTest]
        public IEnumerator TurntableAppearsInPrismMedia()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var import = PrismApi.ImportProduct(PrismEntity.Asset("Props/Lotus"), "lotus_model", "v0002");
            yield return E2EWait.For(import, 120);
            var lotus = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(import.Result.Record.AssetPath));
            lotus.name = "Lotus";

            var png = PrismApi.Playblast(new PlayblastRequest
            {
                Mode = "turntable", TargetPaths = new[] { "Lotus" }, Frames = 24, Width = 320, Height = 320, Comment = "e2e",
            });
            yield return E2EWait.For(png, 300);
            var versionDir = Path.GetDirectoryName(png.Result.OutputPath);
            _turntableFolder = Path.GetDirectoryName(versionDir);
            StringAssert.Contains("Props/Lotus/Playblasts/Turntable", png.Result.OutputPath.Replace('\\', '/'));
            Assert.AreEqual(24, Directory.GetFiles(versionDir, "*.png").Length);
            var info = JObject.Parse(File.ReadAllText(Path.Combine(versionDir, "versioninfo.json")));
            Assert.AreEqual("e2e", (string)info["comment"]);
            Assert.AreEqual("Unity", (string)info["source"]);
            Assert.AreEqual(24, (int)info["frames"]);

            var mp4 = PrismApi.Playblast(new PlayblastRequest
            {
                Mode = "turntable", TargetPaths = new[] { "Lotus" }, Frames = 12, Width = 320, Height = 320, Format = "mp4",
            });
            yield return E2EWait.For(mp4, 300);
            Assert.AreNotEqual(png.Result.Version, mp4.Result.Version);
            StringAssert.EndsWith(".mp4", mp4.Result.OutputPath);
            Assert.IsTrue(File.Exists(mp4.Result.OutputPath));
            Assert.AreEqual(1, Directory.GetFiles(Path.GetDirectoryName(mp4.Result.OutputPath))
                .Count(f => f.EndsWith(".mp4")));
            Assert.AreEqual(1, EditorSceneManager.GetActiveScene().rootCount, "The turntable must not add objects to the scene.");
        }
    }
}
