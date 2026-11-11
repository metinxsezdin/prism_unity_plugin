using System;
using System.Collections;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEngine.TestTools;
using Prism.Unity.Editor.Tests.Support;

namespace Prism.Unity.Editor.Tests.E2E
{
    /// <summary>Import and update through the real Prism and the test Prism project; Prism must open no window.</summary>
    [Category("E2E")]
    public class ImportE2ETests
    {
        const string RecordId = "Props__Lotus__lotus_model";

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
            AssetDatabase.DeleteAsset("Assets/Prism");
            if (System.IO.Directory.Exists(ImportRecord.Folder))
                System.IO.Directory.Delete(ImportRecord.Folder, true);
        }

        [UnityTest]
        public IEnumerator ImportLatestThenUpdateAfterNewPublish()
        {
            var import = PrismApi.ImportProduct(PrismEntity.Asset("Props/Lotus"), "lotus_model", "v0001");
            yield return E2EWait.For(import, 120);
            Assert.AreEqual("v0001", import.Result.Record.Version);

            var check = PrismApi.CheckForUpdates();
            yield return E2EWait.For(check, 60);
            var entry = check.Result.Single(t => (string)t["id"] == RecordId);
            Assert.AreEqual("v0001", (string)entry["current"]);
            Assert.AreEqual("v0003", (string)entry["latest"]);

            var update = PrismApi.UpdateProduct(RecordId, "v0002");
            yield return E2EWait.For(update, 60);
            Assert.IsTrue(update.Result.Updated);
            Assert.AreEqual("v0002", ImportRecord.Load(RecordId).Version);
        }

        [UnityTest]
        public IEnumerator HeadlessBreakingUpdateReturnsDiff()
        {
            var import = PrismApi.ImportProduct(PrismEntity.Asset("Props/Lotus"), "lotus_model", "v0001");
            yield return E2EWait.For(import, 120);

            var update = PrismApi.UpdateProduct(RecordId, "v0003", confirm: false);
            while (!update.IsCompleted) yield return null;
            Assert.IsTrue(update.IsFaulted, "A breaking update must not apply without confirmation.");
            var ex = update.Exception.GetBaseException() as PrismCommandException;
            Assert.IsNotNull(ex, update.Exception.ToString());
            Assert.AreEqual(ErrorCodes.NeedsConfirmation, ex.Code, ex.Message);
            CollectionAssert.Contains(ex.Details["removedNodes"].ToObject<string[]>(), "Stem");
            Assert.AreEqual("v0001", ImportRecord.Load(RecordId).Version);
        }

        [UnityTest]
        public IEnumerator UnknownVersionIsSourceUnavailable()
        {
            var import = PrismApi.ImportProduct(PrismEntity.Asset("Props/Lotus"), "lotus_model", "v0099");
            while (!import.IsCompleted) yield return null;
            var ex = import.Exception?.GetBaseException() as PrismCommandException;
            Assert.IsNotNull(ex);
            Assert.AreEqual(ErrorCodes.SourceUnavailable, ex.Code);
        }
    }
}
