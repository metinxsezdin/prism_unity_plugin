using System;
using System.Collections;
using System.IO;
using System.Linq;
using NUnit.Framework;
using Prism.Assets;
using Prism.Unity.Editor.Tests.Support;
using UnityEditor;
using UnityEditor.AddressableAssets;
using UnityEngine;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests.E2E
{
    /// <summary>Asset packaging through the real Prism and the test Prism project; Prism must open no window.</summary>
    [Category("E2E")]
    public class PackagingE2ETests
    {
        const string TempProduct = "lotus_temp";
        string _settingsBackup;

        static string LotusExport
        {
            get
            {
                var config = ProjectBinding.Load().PrismProjectConfig;
                var projectRoot = Path.GetDirectoryName(Path.GetDirectoryName(config));
                return Path.Combine(projectRoot, "03_Production", "Assets", "Props", "Lotus", "Export");
            }
        }

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
        public void SetUp()
        {
            _settingsBackup = File.Exists(PackagingSettings.FilePath) ? File.ReadAllText(PackagingSettings.FilePath) : null;
            new PackagingSettings().Save();
        }

        [TearDown]
        public void TearDown()
        {
            var temp = Path.Combine(LotusExport, TempProduct);
            if (Directory.Exists(temp)) Directory.Delete(temp, true);
            AssetDatabase.DeleteAsset("Assets/Prism");
            if (Directory.Exists(ImportRecord.Folder)) Directory.Delete(ImportRecord.Folder, true);
            var settings = AddressableAssetSettingsDefaultObject.Settings;
            if (settings != null)
                foreach (var g in settings.groups.Where(g => g != null && g.Name.StartsWith("Prism")).ToList())
                    settings.RemoveGroup(g);
            if (_settingsBackup != null) File.WriteAllText(PackagingSettings.FilePath, _settingsBackup);
            else File.Delete(PackagingSettings.FilePath);
        }

        [UnityTest]
        public IEnumerator ImportLatestBuildsPackageWithPrismPreview()
        {
            var import = PrismApi.ImportProduct(PrismEntity.Asset("Props/Lotus"), "lotus_model", "v0002");
            yield return E2EWait.For(import, 120);

            const string folder = "Assets/Prism/Props/Lotus/lotus_model";
            var tex = new Texture2D(2, 2);
            tex.LoadImage(File.ReadAllBytes(Path.Combine(PrismSettings.ProjectRoot, folder, "lotus_model_thumb.png")));
            Assert.AreEqual(64, tex.width, "the thumbnail is Prism's 64x64 product preview, not a rendered frame");
            var c = tex.GetPixel(32, 32);
            Assert.Greater(c.r, 0.9f);
            Assert.Less(c.g, 0.1f);

            var entry = AddressableAssetSettingsDefaultObject.Settings.FindAssetEntry(AssetDatabase.AssetPathToGUID($"{folder}/lotus_model.prefab"));
            Assert.IsNotNull(entry);
            Assert.AreEqual("Props/Lotus/lotus_model", entry.address);
            Assert.AreEqual("v0002", AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>($"{folder}/lotus_model.asset").version);
        }

        [UnityTest]
        public IEnumerator ProductRemovedFromPrismIsMarkedMissing()
        {
            // A temporary product: a copy of lotus_model v0001 under another name.
            var source = Path.Combine(LotusExport, "lotus_model", "v0001");
            var target = Path.Combine(LotusExport, TempProduct, "v0001");
            Directory.CreateDirectory(target);
            foreach (var file in Directory.GetFiles(source))
                File.Copy(file, Path.Combine(target, Path.GetFileName(file)));
            var info = Path.Combine(target, "versioninfo.json");
            File.WriteAllText(info, File.ReadAllText(info).Replace("\"lotus_model\"", "\"" + TempProduct + "\""));

            var import = PrismApi.ImportProduct(PrismEntity.Asset("Props/Lotus"), TempProduct, "v0001");
            yield return E2EWait.For(import, 120);
            var definitionPath = $"Assets/Prism/Props/Lotus/{TempProduct}/{TempProduct}.asset";
            Assert.IsFalse(AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(definitionPath).prismMissing);

            Directory.Delete(Path.Combine(LotusExport, TempProduct), true);
            var check = PrismApi.CheckForUpdates();
            yield return E2EWait.For(check, 60);

            var entry = check.Result.Single(t => (string)t["id"] == import.Result.Record.Id);
            Assert.IsTrue((bool)entry["missing"], entry.ToString());
            var definition = AssetDatabase.LoadAssetAtPath<PrismAssetDefinition>(definitionPath);
            Assert.IsTrue(definition.prismMissing);
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Prism/Props/Lotus/{TempProduct}/{TempProduct}.prefab"), "nothing is deleted");
        }
    }
}
