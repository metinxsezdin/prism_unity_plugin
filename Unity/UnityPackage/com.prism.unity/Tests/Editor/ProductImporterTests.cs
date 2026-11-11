using System.IO;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Prism.Unity.Editor.Tests
{
    public class ProductImporterTests
    {
        const string LotusAsset = "Assets/Prism/Props/Lotus/lotus_model/lotus_model.fbx";
        ImportFixture _fx;

        [SetUp]
        public void SetUp() => _fx = new ImportFixture();

        [TearDown]
        public void TearDown()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            AssetDatabase.DeleteAsset("Assets/PrismTestMaterials");
            _fx.Cleanup();
        }

        ImportResult ImportLotus(string fixture, string version, bool confirm = false) =>
            ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version(fixture, version), confirm);

        [Test]
        public void ImportCreatesAssetAndRecord()
        {
            var result = ImportLotus("lotus_v1.fbx", "v0001");
            Assert.IsFalse(result.Updated);
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<GameObject>(LotusAsset));
            Assert.AreEqual(LotusAsset, result.Record.AssetPath);

            var record = ImportRecord.Load("Props__Lotus__lotus_model");
            Assert.IsNotNull(record);
            Assert.AreEqual("v0001", record.Version);
            Assert.AreEqual("Props/Lotus", record.Entity.AssetPath);
            Assert.AreEqual("lotus_model", record.Product);
            Assert.AreEqual("global", record.Location);
            StringAssert.EndsWith(Path.Combine("v0001", "lotus_v1.fbx"), record.SourcePath.Replace('/', Path.DirectorySeparatorChar));
            Assert.IsFalse(string.IsNullOrEmpty(record.ImportedBy));
            Assert.IsFalse(string.IsNullOrEmpty(record.ImportedAt));
        }

        [Test]
        public void RecordFilesArePerProduct()
        {
            ImportLotus("lotus_v1.fbx", "v0001");
            var files = Directory.GetFiles(ImportRecord.Folder, "*.json");
            Assert.AreEqual(1, files.Length);
            Assert.AreEqual("Props__Lotus__lotus_model.json", Path.GetFileName(files[0]));
            Assert.AreEqual(1, ImportRecord.LoadAll().Count);
        }

        [Test]
        public void UpdateKeepsGuid()
        {
            ImportLotus("lotus_v1.fbx", "v0001");
            var guid = AssetDatabase.AssetPathToGUID(LotusAsset);
            var hashV1 = ImportFixture.Hash(LotusAsset);

            var result = ImportLotus("lotus_v2.fbx", "v0002");
            Assert.IsTrue(result.Updated);
            Assert.AreEqual(guid, AssetDatabase.AssetPathToGUID(LotusAsset));
            Assert.AreNotEqual(hashV1, ImportFixture.Hash(LotusAsset), "File content should be the new version.");
            Assert.AreEqual("v0002", ImportRecord.Load("Props__Lotus__lotus_model").Version);
        }

        [Test]
        public void UpdateKeepsMaterialRemap()
        {
            ImportLotus("lotus_v1.fbx", "v0001");
            AssetDatabase.CreateFolder("Assets", "PrismTestMaterials");
            var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            AssetDatabase.CreateAsset(mat, "Assets/PrismTestMaterials/TestPetal.mat");
            var importer = (ModelImporter)AssetImporter.GetAtPath(LotusAsset);
            importer.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), "PetalMat"), mat);
            importer.SaveAndReimport();

            ImportLotus("lotus_v2.fbx", "v0002");

            importer = (ModelImporter)AssetImporter.GetAtPath(LotusAsset);
            var map = importer.GetExternalObjectMap();
            Assert.IsTrue(map.TryGetValue(new AssetImporter.SourceAssetIdentifier(typeof(Material), "PetalMat"), out var remapped));
            Assert.AreEqual("Assets/PrismTestMaterials/TestPetal.mat", AssetDatabase.GetAssetPath(remapped));
        }

        [Test]
        public void UpdateKeepsSceneInstance()
        {
            ImportLotus("lotus_v1.fbx", "v0001");
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(LotusAsset);
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(model);
            instance.transform.position = new Vector3(3, 0, 1);
            // What the inspector / move tool does: record the override on the instance.
            PrefabUtility.RecordPrefabInstancePropertyModifications(instance.transform);

            ImportLotus("lotus_v2.fbx", "v0002");

            var source = PrefabUtility.GetCorrespondingObjectFromSource(instance);
            Assert.IsNotNull(source, "Scene instance lost its link to the model.");
            Assert.AreEqual(AssetDatabase.AssetPathToGUID(LotusAsset), AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(source)));
            Assert.AreEqual(new Vector3(3, 0, 1), instance.transform.position);
        }

        [Test]
        public void MissingSourceLeavesAssetUntouched()
        {
            ImportLotus("lotus_v1.fbx", "v0001");
            var hash = ImportFixture.Hash(LotusAsset);
            var missing = new ResolvedVersion { Version = "v0002", FilePath = @"M:\yok\lotus.fbx", Location = "global" };

            var ex = Assert.Throws<PrismCommandException>(() =>
                ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, missing, false));
            Assert.AreEqual(ErrorCodes.SourceUnavailable, ex.Code);
            Assert.AreEqual(hash, ImportFixture.Hash(LotusAsset));
            Assert.AreEqual("v0001", ImportRecord.Load("Props__Lotus__lotus_model").Version);
        }

        [Test]
        public void AbcWithoutAlembicPackage()
        {
            var dir = Path.Combine(_fx.SourceDir, "v0001");
            Directory.CreateDirectory(dir);
            var abc = Path.Combine(dir, "lotus.abc");
            File.WriteAllText(abc, "not really alembic");
            var ex = Assert.Throws<PrismCommandException>(() => ProductImporter.ImportResolved(ImportFixture.Lotus, "lotus_cache",
                new ResolvedVersion { Version = "v0001", FilePath = abc, Location = "global" }, false));
            Assert.AreEqual(ErrorCodes.MissingPackage, ex.Code);
            StringAssert.Contains("com.unity.formats.alembic", ex.Message);
            Assert.IsFalse(File.Exists(Path.Combine(PrismSettings.ProjectRoot, "Assets/Prism/Props/Lotus/lotus_cache/lotus_cache.abc")));
        }

        [Test]
        public void UnsupportedExtensionIsBadArgs()
        {
            var dir = Path.Combine(_fx.SourceDir, "v0001");
            Directory.CreateDirectory(dir);
            var file = Path.Combine(dir, "lotus.blend");
            File.WriteAllText(file, "x");
            var ex = Assert.Throws<PrismCommandException>(() => ProductImporter.ImportResolved(ImportFixture.Lotus, "lotus_src",
                new ResolvedVersion { Version = "v0001", FilePath = file, Location = "global" }, false));
            Assert.AreEqual(ErrorCodes.BadArgs, ex.Code);
        }

        [Test]
        public void TurkishAndSpacedNames()
        {
            var entity = PrismEntity.Asset("Props/Çay Bardağı");
            var v = new ResolvedVersion { Version = "v0001", FilePath = _fx.Source("cay_v1.fbx", "v0001"), Location = "global" };
            var result = ProductImporter.ImportResolved(entity, "cay_model", v, false);

            const string expected = "Assets/Prism/Props/Çay Bardağı/cay_model/cay_model.fbx";
            Assert.AreEqual(expected, result.Record.AssetPath);
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<GameObject>(expected));
            var record = ImportRecord.Load("Props__Çay Bardağı__cay_model");
            Assert.IsNotNull(record);
            Assert.AreEqual("Props/Çay Bardağı", record.Entity.AssetPath);
        }
    }
}
