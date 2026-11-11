using System.IO;
using NUnit.Framework;
using UnityEditor;

namespace Prism.Unity.Editor.Tests
{
    public class HierarchyDiffTests
    {
        const string LotusAsset = "Assets/Prism/Props/Lotus/lotus_model/lotus_model.fbx";
        const string RecordId = "Props__Lotus__lotus_model";
        ImportFixture _fx;

        [SetUp]
        public void SetUp()
        {
            _fx = new ImportFixture();
            ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v1.fbx", "v0001"), false);
        }

        [TearDown]
        public void TearDown()
        {
            Assert.IsFalse(AssetDatabase.IsValidFolder("Assets/Prism/_staging"), "Staging folder was left behind.");
            _fx.Cleanup();
        }

        [Test]
        public void NoChangesBetweenV1AndV2()
        {
            var changes = HierarchyDiff.Compare(LotusAsset, _fx.Source("lotus_v2.fbx", "v0002"));
            Assert.IsFalse(changes.IsBreaking);
            CollectionAssert.IsEmpty(changes.RemovedNodes);
            CollectionAssert.IsEmpty(changes.AddedNodes);
            CollectionAssert.IsEmpty(changes.RemovedMaterials);
            CollectionAssert.IsEmpty(changes.AddedMaterials);
        }

        [Test]
        public void DetectsRenameAndRemovedMaterial()
        {
            var changes = HierarchyDiff.Compare(LotusAsset, _fx.Source("lotus_v3_renamed.fbx", "v0003"));
            CollectionAssert.Contains(changes.RemovedNodes, "Stem");
            CollectionAssert.Contains(changes.AddedNodes, "StemMain");
            CollectionAssert.Contains(changes.RemovedMaterials, "StemMat");
            CollectionAssert.DoesNotContain(changes.RemovedNodes, "Petals");
            Assert.IsTrue(changes.IsBreaking);
        }

        [Test]
        public void BreakingUpdateNeedsConfirmation()
        {
            var hash = ImportFixture.Hash(LotusAsset);
            var ex = Assert.Throws<PrismCommandException>(() => ProductImporter.ImportResolved(
                ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v3_renamed.fbx", "v0003"), confirm: false));
            Assert.AreEqual(ErrorCodes.NeedsConfirmation, ex.Code);
            CollectionAssert.Contains(ex.Details["removedNodes"].ToObject<string[]>(), "Stem");
            Assert.AreEqual("v0001", ImportRecord.Load(RecordId).Version);
            Assert.AreEqual(hash, ImportFixture.Hash(LotusAsset));
        }

        [Test]
        public void BreakingUpdateWithConfirmApplies()
        {
            var result = ProductImporter.ImportResolved(
                ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v3_renamed.fbx", "v0003"), confirm: true);
            Assert.AreEqual("v0003", ImportRecord.Load(RecordId).Version);
            Assert.IsTrue(result.Changes.IsBreaking);
        }

        [Test]
        public void NonBreakingUpdateReportsNoChanges()
        {
            var result = ProductImporter.ImportResolved(
                ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v2.fbx", "v0002"), confirm: false);
            Assert.IsFalse(result.Changes.IsBreaking);
        }

        [Test]
        public void StagingCleanedUp()
        {
            HierarchyDiff.Compare(LotusAsset, _fx.Source("lotus_v3_renamed.fbx", "v0003"));
            Assert.IsFalse(AssetDatabase.IsValidFolder("Assets/Prism/_staging"));
            Assert.IsFalse(Directory.Exists(Path.Combine(PrismSettings.ProjectRoot, "Assets/Prism/_staging")));
        }
    }
}
