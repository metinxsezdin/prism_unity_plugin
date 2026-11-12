using System.IO;
using System.Linq;
using NUnit.Framework;
using Prism.Assets;
using Prism.Unity.Editor.Packaging;
using UnityEditor;
using UnityEditor.AddressableAssets;
using UnityEditor.AddressableAssets.Settings;
using UnityEngine;

namespace Prism.Unity.Editor.Tests
{
    public class PackageBuilderTests
    {
        const string Folder = "Assets/Prism/Props/Lotus/lotus_model";
        const string Address = "Props/Lotus/lotus_model";
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
            AssetDatabase.DeleteAsset("Assets/PrismTestOther"); // before the models: a moved variant must not outlive its parent
            _fx.Cleanup();
            var settings = AddressableAssetSettingsDefaultObject.Settings;
            if (settings != null)
                foreach (var g in settings.groups.Where(g => g != null && g.Name.StartsWith("Prism")).ToList())
                    settings.RemoveGroup(g);
            if (_settingsBackup != null) File.WriteAllText(PackagingSettings.FilePath, _settingsBackup);
            else File.Delete(PackagingSettings.FilePath);
        }

        ImportResult Import(string fixture, string version, string preview = null, string entity = "Props/Lotus", string product = "lotus_model")
        {
            var v = _fx.Version(fixture, version);
            v.PreviewPath = preview;
            return ProductImporter.ImportResolved(PrismEntity.Asset(entity), product, v, true);
        }

        static AddressableAssetEntry Entry(string assetPath) =>
            AddressableAssetSettingsDefaultObject.Settings.FindAssetEntry(AssetDatabase.AssetPathToGUID(assetPath));

        [Test]
        public void ImportCreatesFullPackage()
        {
            Import("lotus_v1.fbx", "v0001");

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{Folder}/lotus_model.prefab");
            Assert.IsNotNull(prefab, "prefab");
            Assert.AreEqual(PrefabAssetType.Variant, PrefabUtility.GetPrefabAssetType(prefab));
            Assert.AreEqual($"{Folder}/lotus_model.fbx", AssetDatabase.GetAssetPath(PrefabUtility.GetCorrespondingObjectFromSource(prefab)));

            var def = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{Folder}/lotus_model.asset");
            Assert.IsNotNull(def, "definition");
            Assert.AreEqual("v0001", def.version);
            Assert.AreEqual(Address, def.addressableKey);
            Assert.AreEqual("Lotus", def.displayName);
            Assert.AreEqual("Props/Lotus", def.entityPath);
            Assert.AreEqual(AssetDatabase.AssetPathToGUID($"{Folder}/lotus_model.prefab"), def.prefab.AssetGUID);
            Assert.IsTrue(File.Exists(Path.Combine(PrismSettings.ProjectRoot, Folder, "lotus_model_thumb.png")));
            Assert.AreEqual(AssetDatabase.AssetPathToGUID($"{Folder}/lotus_model_thumb.png"), def.thumbnail.AssetGUID);

            var entry = Entry($"{Folder}/lotus_model.prefab");
            Assert.IsNotNull(entry, "Addressable entry");
            Assert.AreEqual(Address, entry.address);
            Assert.AreEqual("Prism Props", entry.parentGroup.Name);
            CollectionAssert.IsSupersetOf(entry.labels, new[] { "prism", "Props", "lotus_model" });
            Assert.AreEqual(Address + "#definition", Entry($"{Folder}/lotus_model.asset").address);
            Assert.AreEqual(Address + "#thumb", Entry($"{Folder}/lotus_model_thumb.png").address);

            var catalog = AssetDatabase.LoadAssetAtPath<PrismAssetCatalog>("Assets/Prism/PrismAssetCatalog.asset");
            Assert.AreSame(def, catalog.Find("Props/Lotus", "lotus_model"));
            Assert.AreEqual(PrismAssetCatalog.Address, Entry("Assets/Prism/PrismAssetCatalog.asset").address);
        }

        [Test]
        public void FirstPackagingCreatesAddressablesSettingsWithoutDialog()
        {
            AssetDatabase.DeleteAsset("Assets/AddressableAssetsData");
            Assume.That(AddressableAssetSettingsDefaultObject.Settings, Is.Null, "precondition: no Addressables settings");
            Import("lotus_v1.fbx", "v0001");
            Assert.IsNotNull(AddressableAssetSettingsDefaultObject.Settings);
            Assert.AreEqual(Address, Entry($"{Folder}/lotus_model.prefab").address);
        }

        [Test]
        public void UpdateKeepsTeamPrefabAdditions()
        {
            Import("lotus_v1.fbx", "v0001");
            var path = $"{Folder}/lotus_model.prefab";
            var root = PrefabUtility.LoadPrefabContents(path);
            root.AddComponent<BoxCollider>();
            PrefabUtility.SaveAsPrefabAsset(root, path);
            PrefabUtility.UnloadPrefabContents(root);

            Import("lotus_v2.fbx", "v0002");

            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<GameObject>(path).GetComponent<BoxCollider>());
            Assert.AreEqual("v0002", AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{Folder}/lotus_model.asset").version);
        }

        [Test]
        public void UpdateKeepsTeamDefinitionFieldsAndDisplayName()
        {
            new PackagingSettings { DefinitionType = typeof(TestItemDefinition).AssemblyQualifiedName }.Save();
            Import("lotus_v1.fbx", "v0001");
            var def = AssetDatabase.LoadAssetAtPath<TestItemDefinition>($"{Folder}/lotus_model.asset");
            Assert.IsNotNull(def, "the team's class is used for new definitions");
            def.unlockLevel = 5;
            def.displayName = "Nilüfer";
            EditorUtility.SetDirty(def);
            AssetDatabase.SaveAssets();

            Import("lotus_v2.fbx", "v0002");

            def = AssetDatabase.LoadAssetAtPath<TestItemDefinition>($"{Folder}/lotus_model.asset");
            Assert.AreEqual(5, def.unlockLevel);
            Assert.AreEqual("Nilüfer", def.displayName);
            Assert.AreEqual("v0002", def.version);
        }

        [Test]
        public void AddressCollisionIsNotOverwritten()
        {
            AssetDatabase.CreateFolder("Assets", "PrismTestOther");
            var other = ScriptableObject.CreateInstance<PrismAssetCatalog>();
            AssetDatabase.CreateAsset(other, "Assets/PrismTestOther/Other.asset");
            var settings = AddressableAssetSettingsDefaultObject.GetSettings(true);
            var otherEntry = settings.CreateOrMoveEntry(AssetDatabase.AssetPathToGUID("Assets/PrismTestOther/Other.asset"), settings.DefaultGroup);
            otherEntry.address = Address;

            var result = Import("lotus_v1.fbx", "v0001");

            Assert.IsNotNull(PackageBuilder.Describe(result.Record).Warning);
            StringAssert.Contains(Address, PackageBuilder.Describe(result.Record).Warning);
            Assert.AreEqual(Address, Entry("Assets/PrismTestOther/Other.asset").address);
            var mine = Entry($"{Folder}/lotus_model.prefab");
            Assert.IsTrue(mine == null || mine.address != Address);
            settings.RemoveAssetEntry(otherEntry.guid);
        }

        [Test]
        public void CollisionLeavesKeyEmptyAndRegistersTheRest()
        {
            AssetDatabase.CreateFolder("Assets", "PrismTestOther");
            AssetDatabase.CreateAsset(ScriptableObject.CreateInstance<PrismAssetCatalog>(), "Assets/PrismTestOther/Other.asset");
            var settings = AddressableAssetSettingsDefaultObject.GetSettings(true);
            var otherEntry = settings.CreateOrMoveEntry(AssetDatabase.AssetPathToGUID("Assets/PrismTestOther/Other.asset"), settings.DefaultGroup);
            otherEntry.address = Address;

            Import("lotus_v1.fbx", "v0001");

            var def = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{Folder}/lotus_model.asset");
            Assert.IsTrue(string.IsNullOrEmpty(def.addressableKey), "the key must not name the other asset");
            Assert.AreEqual(Address + "#definition", Entry($"{Folder}/lotus_model.asset").address);
            Assert.AreEqual(Address + "#thumb", Entry($"{Folder}/lotus_model_thumb.png").address);
            settings.RemoveAssetEntry(otherEntry.guid);
        }

        [Test]
        public void TeamRenamedAddressIsKept()
        {
            var result = Import("lotus_v1.fbx", "v0001");
            Entry($"{Folder}/lotus_model.prefab").address = "Wellness/Lotus";

            Import("lotus_v2.fbx", "v0002");

            Assert.AreEqual("Wellness/Lotus", Entry($"{Folder}/lotus_model.prefab").address);
            Assert.AreEqual("Wellness/Lotus", AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{Folder}/lotus_model.asset").addressableKey);
            Assert.IsNull(PackageBuilder.Describe(result.Record).Warning);
            Assert.AreEqual("Wellness/Lotus", PackageBuilder.Describe(result.Record).AddressableKey);
        }

        [Test]
        public void MovedPrefabIsNotDuplicated()
        {
            var result = Import("lotus_v1.fbx", "v0001");
            AssetDatabase.CreateFolder("Assets", "PrismTestOther");
            Assert.IsEmpty(AssetDatabase.MoveAsset($"{Folder}/lotus_model.prefab", "Assets/PrismTestOther/Lotus.prefab"));
            var moved = AssetDatabase.AssetPathToGUID("Assets/PrismTestOther/Lotus.prefab");

            Import("lotus_v2.fbx", "v0002");

            Assert.IsFalse(File.Exists(Path.Combine(PrismSettings.ProjectRoot, Folder, "lotus_model.prefab")), "no second variant");
            Assert.AreEqual(moved, AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{Folder}/lotus_model.asset").prefab.AssetGUID);
            Assert.AreEqual("Assets/PrismTestOther/Lotus.prefab", PackageBuilder.Describe(result.Record).PrefabPath);
            Assert.IsNull(PackageBuilder.Describe(result.Record).Warning);
        }

        [Test]
        public void UnloadableDefinitionIsNotReplaced()
        {
            // e.g. the team renamed its definition class: the file no longer loads as a definition.
            var result = Import("lotus_v1.fbx", "v0001");
            var path = $"{Folder}/lotus_model.asset";
            AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(ScriptableObject.CreateInstance<PrismAssetCatalog>(), path);
            var guid = AssetDatabase.AssetPathToGUID(path);

            Import("lotus_v2.fbx", "v0002");

            Assert.AreEqual(guid, AssetDatabase.AssetPathToGUID(path), "the file is kept");
            Assert.IsInstanceOf<PrismAssetCatalog>(AssetDatabase.LoadMainAssetAtPath(path));
            StringAssert.Contains("lotus_model.asset", PackageBuilder.Describe(result.Record).Warning);
        }

        [Test]
        public void ThumbnailFromPrismPreview()
        {
            var red = new Texture2D(64, 64);
            red.SetPixels(Enumerable.Repeat(Color.red, 64 * 64).ToArray());
            var preview = Path.Combine(_fx.SourceDir, "preview.jpg");
            File.WriteAllBytes(preview, red.EncodeToJPG());

            Import("lotus_v1.fbx", "v0001", preview);

            var tex = new Texture2D(2, 2);
            tex.LoadImage(File.ReadAllBytes(Path.Combine(PrismSettings.ProjectRoot, Folder, "lotus_model_thumb.png")));
            Assert.AreEqual(64, tex.width);
            var c = tex.GetPixel(32, 32);
            Assert.Greater(c.r, 0.9f);
            Assert.Less(c.g, 0.1f);
        }

        [Test]
        public void ThumbnailRenderedWithoutPreview()
        {
            Import("lotus_v1.fbx", "v0001");
            var tex = new Texture2D(2, 2);
            tex.LoadImage(File.ReadAllBytes(Path.Combine(PrismSettings.ProjectRoot, Folder, "lotus_model_thumb.png")));
            Assert.AreEqual(256, tex.width);
            Assert.AreEqual(256, tex.height);
            var importer = (TextureImporter)AssetImporter.GetAtPath($"{Folder}/lotus_model_thumb.png");
            Assert.IsFalse(importer.mipmapEnabled);
        }

        [Test]
        public void TurkishNamesWork()
        {
            Import("cay_v1.fbx", "v0001", null, "Props/Çay Bardağı", "cay_model");
            var folder = "Assets/Prism/Props/Çay Bardağı/cay_model";
            var entry = Entry($"{folder}/cay_model.prefab");
            Assert.AreEqual("Props/Çay Bardağı/cay_model", entry.address);
            Assert.AreEqual("Prism Props", entry.parentGroup.Name);
            Assert.AreEqual("Çay Bardağı", AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{folder}/cay_model.asset").displayName);
        }

        [Test]
        public void PackagingDisabledKeepsV1Behaviour()
        {
            new PackagingSettings { Enabled = false }.Save();
            Import("lotus_v1.fbx", "v0001");
            Assert.IsTrue(File.Exists(Path.Combine(PrismSettings.ProjectRoot, Folder, "lotus_model.fbx")));
            Assert.IsFalse(File.Exists(Path.Combine(PrismSettings.ProjectRoot, Folder, "lotus_model.prefab")));
            Assert.IsFalse(File.Exists(Path.Combine(PrismSettings.ProjectRoot, Folder, "lotus_model.asset")));
        }
    }
}
