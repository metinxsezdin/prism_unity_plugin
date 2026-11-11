using System.IO;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Prism.Unity.Editor.Tests
{
    public class SceneVersioningTests
    {
        static readonly PrismEntity Room = PrismEntity.Asset("Scenes/MeditationRoom");
        string _prismDir;

        [SetUp]
        public void SetUp()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            _prismDir = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "prism", Path.GetRandomFileName());
            Directory.CreateDirectory(_prismDir);
        }

        [TearDown]
        public void TearDown()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            AssetDatabase.DeleteAsset("Assets/Scenes/MeditationRoom");
            AssetDatabase.DeleteAsset("Assets/Scenes/Çay Bardağı");
            if (Directory.Exists(SceneBinding.Folder)) Directory.Delete(SceneBinding.Folder, true);
            if (Directory.Exists(_prismDir)) Directory.Delete(_prismDir, true);
        }

        static JToken Run(string cmd, JObject args)
        {
            Assert.IsTrue(CommandRegistry.TryGet(cmd, out var h, out _), cmd);
            return h(args, new CommandContext());
        }

        static JObject BindArgs(PrismEntity entity, string task = "layout") =>
            new JObject { ["entity"] = entity.ToJson(), ["department"] = "Unity", ["task"] = task };

        [Test]
        public void UnsavedSceneGetsDefaultWorkingPath()
        {
            new GameObject("Cube").AddComponent<MeshFilter>();
            var binding = Run("bindScene", BindArgs(Room));
            Assert.AreEqual("Assets/Scenes/MeditationRoom/layout.unity", (string)binding["workingPath"]);
            Assert.IsTrue(File.Exists(Path.Combine(PrismSettings.ProjectRoot, "Assets/Scenes/MeditationRoom/layout.unity")));
            Assert.AreEqual("Assets/Scenes/MeditationRoom/layout.unity", EditorSceneManager.GetActiveScene().path);
        }

        [Test]
        public void SaveToCopiesSceneAndUpdatesBinding()
        {
            Run("bindScene", BindArgs(Room));
            new GameObject("AddedAfterBind");
            var prismPath = Path.Combine(_prismDir, "MeditationRoom_layout_v0001_.unity").Replace('\\', '/');

            var result = Run("saveSceneTo", new JObject { ["path"] = prismPath });

            Assert.AreEqual("Assets/Scenes/MeditationRoom/layout.unity", (string)result["workingPath"]);
            Assert.IsTrue(File.Exists(prismPath));
            var working = File.ReadAllBytes(Path.Combine(PrismSettings.ProjectRoot, "Assets/Scenes/MeditationRoom/layout.unity"));
            CollectionAssert.AreEqual(working, File.ReadAllBytes(prismPath));
            StringAssert.Contains("AddedAfterBind", File.ReadAllText(prismPath));
            Assert.IsFalse(EditorSceneManager.GetActiveScene().isDirty);
            Assert.AreEqual(prismPath, SceneBinding.ForActiveScene().LastPrismPath);
            Assert.AreEqual(prismPath, (string)Run("getSceneBinding", new JObject())["lastPrismPath"]);
        }

        [Test]
        public void SaveToWithoutBindingIsBadArgs()
        {
            var ex = Assert.Throws<PrismCommandException>(() =>
                Run("saveSceneTo", new JObject { ["path"] = Path.Combine(_prismDir, "x.unity") }));
            Assert.AreEqual(ErrorCodes.BadArgs, ex.Code);
        }

        [Test]
        public void GetSceneBindingIsNullForUnboundScene()
        {
            Assert.AreEqual(JTokenType.Null, Run("getSceneBinding", new JObject()).Type);
        }

        [Test]
        public void BindingAnUntitledSceneNeverOverwritesAnExistingFile()
        {
            new GameObject("First");
            Run("bindScene", BindArgs(Room));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            new GameObject("Second");
            var binding = Run("bindScene", BindArgs(Room));
            Assert.AreNotEqual("Assets/Scenes/MeditationRoom/layout.unity", (string)binding["workingPath"]);
            StringAssert.Contains("First", File.ReadAllText(Path.Combine(PrismSettings.ProjectRoot, "Assets/Scenes/MeditationRoom/layout.unity")));
        }

        [Test]
        public void BindingFileIsPerScene()
        {
            Run("bindScene", BindArgs(Room, "layout"));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Run("bindScene", BindArgs(Room, "lighting"));
            var files = Directory.GetFiles(SceneBinding.Folder, "*.json");
            Assert.AreEqual(2, files.Length);
            var guid = AssetDatabase.AssetPathToGUID("Assets/Scenes/MeditationRoom/lighting.unity");
            Assert.IsTrue(File.Exists(Path.Combine(SceneBinding.Folder, guid + ".json")));
        }

        [Test]
        public void FindByPrismPathMatchesTaskFolder()
        {
            Run("bindScene", BindArgs(Room));
            var v1 = Path.Combine(_prismDir, "MeditationRoom_layout_v0001_.unity").Replace('\\', '/');
            Run("saveSceneTo", new JObject { ["path"] = v1 });
            var v2 = Path.Combine(_prismDir, "MeditationRoom_layout_v0002_.unity").Replace('\\', '/');
            Assert.AreEqual("Assets/Scenes/MeditationRoom/layout.unity", SceneBinding.FindByPrismPath(v2).WorkingPath);
            Assert.IsNull(SceneBinding.FindByPrismPath("C:/elsewhere/other_v0001_.unity"));
        }

        [Test]
        public void TurkishEntityWorkingPath()
        {
            var binding = Run("bindScene", BindArgs(PrismEntity.Asset("Scenes/Çay Bardağı")));
            Assert.AreEqual("Assets/Scenes/Çay Bardağı/layout.unity", (string)binding["workingPath"]);
            var prismPath = Path.Combine(_prismDir, "Çay Bardağı_layout_v0001_.unity").Replace('\\', '/');
            Run("saveSceneTo", new JObject { ["path"] = prismPath });
            Assert.IsTrue(File.Exists(prismPath));
        }
    }
}
