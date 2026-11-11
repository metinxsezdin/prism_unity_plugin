using System.Collections;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using Prism.Assets;
using UnityEditor;
using UnityEditor.AddressableAssets;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>A product that disappeared from Prism is flagged on its definition, never deleted.</summary>
    public class MissingFlagTests
    {
        const string Folder = "Assets/Prism/Props/Lotus/lotus_model";
        const string Id = "Props__Lotus__lotus_model";
        ImportFixture _fx;
        string _settingsBackup;

        [SetUp]
        public void SetUp()
        {
            _fx = new ImportFixture();
            _settingsBackup = File.Exists(PackagingSettings.FilePath) ? File.ReadAllText(PackagingSettings.FilePath) : null;
            new PackagingSettings().Save();
        }

        [TearDown]
        public void TearDown()
        {
            PrismClient.Override = null;
            _fx.Cleanup();
            var settings = AddressableAssetSettingsDefaultObject.Settings;
            if (settings != null)
                foreach (var g in settings.groups.Where(g => g != null && g.Name.StartsWith("Prism")).ToList())
                    settings.RemoveGroup(g);
            if (_settingsBackup != null) File.WriteAllText(PackagingSettings.FilePath, _settingsBackup);
            else File.Delete(PackagingSettings.FilePath);
        }

        void Import(string fixture, string version) =>
            ProductImporter.ImportResolved(PrismEntity.Asset("Props/Lotus"), "lotus_model", _fx.Version(fixture, version), true);

        static PrismAssetDefinition Definition => AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{Folder}/lotus_model.asset");

        static JToken SetMissing(bool missing)
        {
            Assert.IsTrue(CommandRegistry.TryGet("setPrismMissing", out var h, out var mutates), "setPrismMissing registered");
            Assert.IsTrue(mutates);
            return h(new JObject { ["ids"] = new JArray(Id), ["missing"] = missing }, new CommandContext());
        }

        [Test]
        public void SetPrismMissingMarksDefinition()
        {
            Import("lotus_v1.fbx", "v0001");
            var result = SetMissing(true);
            Assert.IsTrue(Definition.prismMissing);
            CollectionAssert.AreEqual(new[] { Id }, result["updated"].ToObject<string[]>());
        }

        [Test]
        public void ReimportClearsMissing()
        {
            Import("lotus_v1.fbx", "v0001");
            SetMissing(true);
            Import("lotus_v2.fbx", "v0002");
            Assert.IsFalse(Definition.prismMissing);
        }

        [Test]
        public void MissingNeverDeletesAnything()
        {
            Import("lotus_v1.fbx", "v0001");
            SetMissing(true);
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>($"{Folder}/lotus_model.prefab"));
            Assert.IsNotNull(Definition);
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>($"{Folder}/lotus_model.fbx"));
            var entry = AddressableAssetSettingsDefaultObject.Settings.FindAssetEntry(AssetDatabase.AssetPathToGUID($"{Folder}/lotus_model.prefab"));
            Assert.IsNotNull(entry);
            Assert.AreEqual("Props/Lotus/lotus_model", entry.address);
        }

        [UnityTest]
        public IEnumerator CheckForUpdatesMarksMissing()
        {
            Import("lotus_v1.fbx", "v0001");
            PrismClient.Override = (cmd, args, interactive) => cmd == "checkVersions"
                ? new JArray(new JObject { ["id"] = Id, ["missing"] = true, ["entity"] = "Props/Lotus", ["product"] = "lotus_model" })
                : throw new PrismCommandException(ErrorCodes.UnknownCommand, "fake Prism: " + cmd);

            var task = PrismApi.CheckForUpdates();
            while (!task.IsCompleted) yield return null;

            Assert.IsFalse(task.IsFaulted, task.Exception?.ToString());
            Assert.AreEqual(1, task.Result.Count);
            Assert.IsTrue(Definition.prismMissing);
        }
    }
}
