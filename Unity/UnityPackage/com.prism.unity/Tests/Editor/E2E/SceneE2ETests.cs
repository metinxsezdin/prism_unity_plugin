using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.TestTools;
using Prism.Unity.Editor.Tests.Support;

namespace Prism.Unity.Editor.Tests.E2E
{
    /// <summary>Scene versions saved through the real Prism, with no Prism window allowed.</summary>
    [Category("E2E")]
    public class SceneE2ETests
    {
        readonly List<string> _prismDepartmentFolders = new List<string>();

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

        [SetUp]
        public void SetUp() => EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        [TearDown]
        public void TearDown()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            AssetDatabase.DeleteAsset("Assets/Scenes/MeditationRoom");
            AssetDatabase.DeleteAsset("Assets/Scenes/Çay Bardağı");
            if (Directory.Exists(SceneBinding.Folder)) Directory.Delete(SceneBinding.Folder, true);
            foreach (var dir in _prismDepartmentFolders)
                if (Directory.Exists(dir)) Directory.Delete(dir, true);
            _prismDepartmentFolders.Clear();
        }

        void ForgetDepartmentOf(string savedPath) =>
            _prismDepartmentFolders.Add(Path.GetDirectoryName(Path.GetDirectoryName(savedPath)));

        static int VersionNumber(string v) => int.Parse(v.TrimStart('v'));

        [UnityTest]
        public IEnumerator SaveVersionHeadlessTwice()
        {
            new GameObject("Lotus Spot");
            var first = PrismApi.SaveVersion("ilk", PrismEntity.Asset("Scenes/MeditationRoom"), "Unity", "layout", createDepartment: true);
            yield return E2EWait.For(first, 180);
            var firstPath = (string)first.Result["path"];
            ForgetDepartmentOf(firstPath);
            Assert.IsTrue(File.Exists(firstPath), firstPath);
            StringAssert.EndsWith(".unity", firstPath);
            StringAssert.Contains("Lotus Spot", File.ReadAllText(firstPath));

            new GameObject("Second Light");
            var second = PrismApi.SaveVersion("ikinci");
            yield return E2EWait.For(second, 180);
            var secondPath = (string)second.Result["path"];
            Assert.IsTrue(File.Exists(secondPath), secondPath);
            Assert.AreEqual(VersionNumber((string)first.Result["version"]) + 1, VersionNumber((string)second.Result["version"]));
            StringAssert.Contains("Second Light", File.ReadAllText(secondPath));
            Assert.AreEqual(secondPath, SceneBinding.ForActiveScene().LastPrismPath);

            var info = File.ReadAllText(Path.Combine(Path.GetDirectoryName(secondPath),
                Path.GetFileNameWithoutExtension(secondPath) + "versioninfo.json"));
            StringAssert.Contains("ikinci", info);
            StringAssert.Contains(PlayerSettings.productGUID.ToString(), info);
        }

        [UnityTest]
        public IEnumerator FirstSaveWithoutTargetNeedsInput()
        {
            var save = PrismApi.SaveVersion("x");
            while (!save.IsCompleted) yield return null;
            var ex = save.Exception?.GetBaseException() as PrismCommandException;
            Assert.IsNotNull(ex);
            Assert.AreEqual(ErrorCodes.NeedsInput, ex.Code, ex.Message);
            CollectionAssert.AreEqual(new[] { "entity", "task" }, ex.Details["missing"].ToObject<string[]>());
        }

        [UnityTest]
        public IEnumerator SaveVersionTurkishEntity()
        {
            var save = PrismApi.SaveVersion("çay", PrismEntity.Asset("Props/Çay Bardağı"), "Unity", "look", createDepartment: true);
            yield return E2EWait.For(save, 180);
            var path = (string)save.Result["path"];
            ForgetDepartmentOf(path);
            Assert.IsTrue(File.Exists(path), path);
            StringAssert.Contains("Çay Bardağı", path);
        }
    }
}
