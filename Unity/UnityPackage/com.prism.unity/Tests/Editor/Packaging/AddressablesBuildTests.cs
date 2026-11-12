using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.AddressableAssets;
using UnityEditor.AddressableAssets.Settings;
using UnityEngine;
using UnityEngine.Rendering;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>The groups and entries packaging creates must survive a real Addressables content build.</summary>
    public class AddressablesBuildTests
    {
        ImportFixture _fx;
        string _settingsBackup;
        Dictionary<string, string> _pipelineBackup;

        [SetUp]
        public void SetUp()
        {
            _fx = new ImportFixture();
            _settingsBackup = File.Exists(PackagingSettings.FilePath) ? File.ReadAllText(PackagingSettings.FilePath) : null;
            new PackagingSettings().Save();
            // A content build makes URP rewrite its shader prefiltering in the render pipeline assets.
            var pipelines = new List<RenderPipelineAsset> { GraphicsSettings.defaultRenderPipeline };
            for (var i = 0; i < QualitySettings.count; i++) pipelines.Add(QualitySettings.GetRenderPipelineAssetAt(i));
            _pipelineBackup = pipelines.Where(p => p != null).Select(AssetDatabase.GetAssetPath).Where(p => !string.IsNullOrEmpty(p)).Distinct()
                .ToDictionary(p => p, p => File.ReadAllText(Path.Combine(PrismSettings.ProjectRoot, p)));
        }

        [TearDown]
        public void TearDown()
        {
            AddressableAssetSettings.CleanPlayerContent();
            AssetDatabase.SaveAssets();
            foreach (var pair in _pipelineBackup)
            {
                File.WriteAllText(Path.Combine(PrismSettings.ProjectRoot, pair.Key), pair.Value);
                AssetDatabase.ImportAsset(pair.Key, ImportAssetOptions.ForceUpdate);
            }
            _fx.Cleanup();
            var settings = AddressableAssetSettingsDefaultObject.Settings;
            if (settings != null)
                foreach (var g in settings.groups.Where(g => g != null && g.Name.StartsWith("Prism")).ToList())
                    settings.RemoveGroup(g);
            if (_settingsBackup != null) File.WriteAllText(PackagingSettings.FilePath, _settingsBackup);
            else File.Delete(PackagingSettings.FilePath);
        }

        [Test]
        public void ContentBuildIncludesPackagedProduct()
        {
            ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v1.fbx", "v0001"), true);

            AddressableAssetSettings.BuildPlayerContent(out var result);

            Assert.IsTrue(string.IsNullOrEmpty(result.Error), result.Error);
            var groups = result.AssetBundleBuildResults.Select(b => b.SourceAssetGroup?.Name).ToList();
            CollectionAssert.Contains(groups, "Prism Props", "the product's bundle");
            CollectionAssert.Contains(groups, "Prism", "the catalog's bundle");
        }
    }
}
