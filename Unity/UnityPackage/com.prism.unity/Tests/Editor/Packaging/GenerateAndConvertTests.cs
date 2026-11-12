using System.IO;
using System.Linq;
using NUnit.Framework;
using Prism.Assets;
using Prism.Unity.Editor.Packaging;
using UnityEditor;
using UnityEditor.AddressableAssets;
using UnityEngine;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests
{
    public class GenerateAndConvertTests
    {
        const string Lotus = "Assets/Prism/Props/Lotus/lotus_model";
        const string Cay = "Assets/Prism/Props/Çay Bardağı/cay_model";
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
            _fx.Cleanup();
            var settings = AddressableAssetSettingsDefaultObject.Settings;
            if (settings != null)
                foreach (var g in settings.groups.Where(g => g != null && g.Name.StartsWith("Prism")).ToList())
                    settings.RemoveGroup(g);
            if (_settingsBackup != null) File.WriteAllText(PackagingSettings.FilePath, _settingsBackup);
            else File.Delete(PackagingSettings.FilePath);
        }

        void ImportBoth()
        {
            ProductImporter.ImportResolved(PrismEntity.Asset("Props/Lotus"), "lotus_model", _fx.Version("lotus_v1.fbx", "v0001"), true);
            ProductImporter.ImportResolved(PrismEntity.Asset("Props/Çay Bardağı"), "cay_model", _fx.Version("cay_v1.fbx", "v0001"), true);
        }

        static void AssertFullPackage(string folder, string product)
        {
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<GameObject>($"{folder}/{product}.prefab"), product + " prefab");
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{folder}/{product}.asset"), product + " definition");
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<Texture2D>($"{folder}/{product}_thumb.png"), product + " thumbnail");
            Assert.IsNotNull(AddressableAssetSettingsDefaultObject.Settings.FindAssetEntry(AssetDatabase.AssetPathToGUID($"{folder}/{product}.prefab")));
        }

        [Test]
        public void GenerateMissingCreatesPackagesForV1Imports()
        {
            new PackagingSettings { Enabled = false }.Save();
            ImportBoth();
            Assume.That(File.Exists($"{Lotus}/lotus_model.prefab"), Is.False);
            new PackagingSettings().Save();

            Assert.AreEqual(2, PackagingCommands.GenerateMissing());

            AssertFullPackage(Lotus, "lotus_model");
            AssertFullPackage(Cay, "cay_model");
        }

        [Test]
        public void GenerateMissingIsIdempotent()
        {
            new PackagingSettings { Enabled = false }.Save();
            ImportBoth();
            new PackagingSettings().Save();
            PackagingCommands.GenerateMissing();
            var path = $"{Lotus}/lotus_model.prefab";
            var root = PrefabUtility.LoadPrefabContents(path);
            root.AddComponent<BoxCollider>();
            PrefabUtility.SaveAsPrefabAsset(root, path);
            PrefabUtility.UnloadPrefabContents(root);

            Assert.AreEqual(0, PackagingCommands.GenerateMissing());
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<GameObject>(path).GetComponent<BoxCollider>());
        }

        [Test]
        public void GenerateMissingSkipsBrokenRecordAndContinues()
        {
            new PackagingSettings { Enabled = false }.Save();
            ImportBoth();
            AssetDatabase.DeleteAsset($"{Lotus}/lotus_model.fbx");
            new PackagingSettings().Save();
            LogAssert.ignoreFailingMessages = true;

            Assert.AreEqual(1, PackagingCommands.GenerateMissing());
            AssertFullPackage(Cay, "cay_model");
        }

        [Test]
        public void GenerateMissingRepairsAddressablesAndCatalog()
        {
            ImportBoth();
            var settings = AddressableAssetSettingsDefaultObject.Settings;
            settings.RemoveAssetEntry(AssetDatabase.AssetPathToGUID($"{Lotus}/lotus_model.prefab"));
            settings.RemoveAssetEntry(AssetDatabase.AssetPathToGUID(CatalogUpdater.CatalogPath));
            var catalog = AssetDatabase.LoadAssetAtPath<PrismAssetCatalog>(CatalogUpdater.CatalogPath);
            catalog.definitions.Clear();
            EditorUtility.SetDirty(catalog);

            Assert.AreEqual(0, PackagingCommands.GenerateMissing(), "nothing new was created");

            Assert.AreEqual("Props/Lotus/lotus_model", settings.FindAssetEntry(AssetDatabase.AssetPathToGUID($"{Lotus}/lotus_model.prefab")).address);
            Assert.AreEqual(PrismAssetCatalog.Address, settings.FindAssetEntry(AssetDatabase.AssetPathToGUID(CatalogUpdater.CatalogPath)).address);
            Assert.AreEqual(2, catalog.definitions.Count);
        }

        [Test]
        public void ConvertNeverDropsFields()
        {
            new PackagingSettings { DefinitionType = typeof(TestItemDefinition).AssemblyQualifiedName }.Save();
            ImportBoth();
            // Back to the base class would drop unlockLevel: those definitions are left alone.
            Assert.AreEqual(0, PackagingCommands.PreviewConversion(typeof(PrismAssetDefinition)).count);
            Assert.AreEqual(0, PackagingCommands.ConvertDefinitions(typeof(PrismAssetDefinition)));
            Assert.IsInstanceOf<TestItemDefinition>(AssetDatabase.LoadMainAssetAtPath($"{Lotus}/lotus_model.asset"));
        }

        [Test]
        public void ConvertKeepsGuidAndPrismFields()
        {
            ImportBoth();
            var path = $"{Lotus}/lotus_model.asset";
            var guid = AssetDatabase.AssetPathToGUID(path);

            var preview = PackagingCommands.PreviewConversion(typeof(TestItemDefinition));
            Assert.AreEqual(2, preview.count);
            CollectionAssert.Contains(preview.paths, path);

            Assert.AreEqual(2, PackagingCommands.ConvertDefinitions(typeof(TestItemDefinition)));

            Assert.AreEqual(guid, AssetDatabase.AssetPathToGUID(path));
            var def = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(path);
            Assert.IsInstanceOf<TestItemDefinition>(def);
            Assert.AreEqual("Props/Lotus/lotus_model", def.addressableKey);
            Assert.AreEqual("v0001", def.version);
            Assert.AreEqual(0, PackagingCommands.PreviewConversion(typeof(TestItemDefinition)).count);
        }

        [Test]
        public void ConvertedDefinitionStillInCatalog()
        {
            ImportBoth();
            PackagingCommands.ConvertDefinitions(typeof(TestItemDefinition));
            var catalog = AssetDatabase.LoadAssetAtPath<PrismAssetCatalog>(CatalogUpdater.CatalogPath);            var found = catalog.Find("Props/Lotus", "lotus_model");
            Assert.IsInstanceOf<TestItemDefinition>(found);
            Assert.AreEqual(2, catalog.OfType<TestItemDefinition>().Count());
        }
    }
}
