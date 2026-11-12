using System.IO;
using NUnit.Framework;

namespace Prism.Unity.Editor.Tests
{
    public class PackagingSettingsTests
    {
        string _backup;
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _backup = File.Exists(PackagingSettings.FilePath) ? File.ReadAllText(PackagingSettings.FilePath) : null;
            if (_backup != null) File.Delete(PackagingSettings.FilePath);
            _tmp = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "settings", Path.GetRandomFileName());
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (_backup != null) File.WriteAllText(PackagingSettings.FilePath, _backup);
            else if (File.Exists(PackagingSettings.FilePath)) File.Delete(PackagingSettings.FilePath);
            Directory.Delete(_tmp, true);
            PrismProcess.StopObserver = null;
        }

        [Test]
        public void DefaultsWhenFileMissing()
        {
            var s = PackagingSettings.Load();
            Assert.IsTrue(s.Enabled);
            Assert.AreEqual("Prism.Assets.PrismAssetDefinition, Prism.Assets", s.DefinitionType);
            Assert.AreEqual("{entity}/{product}", s.AddressFormat);
            Assert.AreEqual("Prism {category}", s.GroupFormat);
        }

        [Test]
        public void SaveLoadRoundTrip()
        {
            new PackagingSettings { Enabled = false, AddressFormat = "{product}", GroupFormat = "Art {category}" }.Save();
            var s = PackagingSettings.Load();
            Assert.IsFalse(s.Enabled);
            Assert.AreEqual("{product}", s.AddressFormat);
            Assert.AreEqual("Art {category}", s.GroupFormat);
            StringAssert.Contains("\"addressFormat\"", File.ReadAllText(PackagingSettings.FilePath));
        }

        [Test]
        public void FormatAddressAndGroup()
        {
            var s = new PackagingSettings();
            var cay = PrismEntity.Asset("Props/Çay Bardağı");
            Assert.AreEqual("Props/Çay Bardağı/cay_model", s.FormatAddress(cay, "cay_model"));
            Assert.AreEqual("Prism Props", s.FormatGroup(cay));
        }

        [Test]
        public void ShotEntityFormats()
        {
            var s = new PackagingSettings();
            var shot = new PrismEntity { Type = "shot", Sequence = "sq01", Shot = "sh010" };
            Assert.AreEqual("sq01/sh010/cam", s.FormatAddress(shot, "cam"));
            Assert.AreEqual("Prism sq01", s.FormatGroup(shot));
        }

        [Test]
        public void GroupFormatNeverYieldsSlashes()
        {
            // M5: an Addressables group name is a file name; {entity} brings a slash with it.
            var s = new PackagingSettings { GroupFormat = "{entity}" };
            Assert.AreEqual("Props-Lotus", s.FormatGroup(PrismEntity.Asset("Props/Lotus")));
        }

        [Test]
        public void EmptyFormatsFallBackToDefaults()
        {
            var s = new PackagingSettings { AddressFormat = " ", GroupFormat = "" };
            Assert.AreEqual("Props/Lotus/lotus_model", s.FormatAddress(PrismEntity.Asset("Props/Lotus"), "lotus_model"));
            Assert.AreEqual("Prism Props", s.FormatGroup(PrismEntity.Asset("Props/Lotus")));
        }

        [Test]
        public void ProblemsNameAnAddressThatIsNotUnique()
        {
            Assert.IsEmpty(new PackagingSettings().Problems());
            var problems = new PackagingSettings { AddressFormat = "{category}" }.Problems();
            Assert.AreEqual(1, problems.Count);
            StringAssert.Contains("{product}", problems[0]);
        }

        [Test]
        public void PickerListsOnlyClassesThatReachPlayerBuilds()
        {
            // M1: a class in an editor-only assembly is lost from player builds.
            var types = PrismSettingsProvider.DefinitionTypes();
            CollectionAssert.Contains(types, typeof(Prism.Assets.PrismAssetDefinition));
            CollectionAssert.DoesNotContain(types, typeof(TestItemDefinition));
        }

        [Test]
        public void PickerSelectionToleratesNullType()
        {
            // M3: "definitionType": null in settings.json.
            Assert.AreEqual(0, PrismSettingsProvider.SelectedIndex(PrismSettingsProvider.DefinitionTypes(), null));
        }

        [Test]
        public void SettingsPageRereadsAFileChangedOnDisk()
        {
            // M3: after a git pull the page must not write its stale copy back.
            new PackagingSettings { AddressFormat = "{product}" }.Save();
            Assert.AreEqual("{product}", PrismSettingsProvider.CurrentSettings().AddressFormat);
            new PackagingSettings { AddressFormat = "pulled/{product}" }.Save();
            File.SetLastWriteTimeUtc(PackagingSettings.FilePath, System.DateTime.UtcNow.AddMinutes(1));
            Assert.AreEqual("pulled/{product}", PrismSettingsProvider.CurrentSettings().AddressFormat);
        }

        [Test]
        public void SettingsPageLooksForThePluginOnce()
        {
            // M10: the page repaints often; finding the plugin reads files.
            var calls = 0;
            var original = PrismSettingsProvider.PluginDirSource;
            PrismSettingsProvider.PluginDirSource = () => { calls++; return "X"; };
            try
            {
                PrismSettingsProvider.ResetCache();
                Assert.AreEqual("X", PrismSettingsProvider.CachedPluginDir());
                Assert.AreEqual("X", PrismSettingsProvider.CachedPluginDir());
                Assert.AreEqual(1, calls);
            }
            finally
            {
                PrismSettingsProvider.PluginDirSource = original;
                PrismSettingsProvider.ResetCache();
            }
        }

        string Pipeline(string folder, string name)
        {
            var dir = Path.Combine(_tmp, folder, "00_Pipeline");
            Directory.CreateDirectory(dir);
            var path = Path.Combine(dir, "pipeline.json");
            File.WriteAllText(path, "{\"globals\": {\"project_name\": \"" + name + "\"}}");
            return path;
        }

        [Test]
        public void RelocationSameProjectAccepted()
        {
            Assert.IsNull(ProjectBinding.ValidateRelocation(Pipeline("new", "Wellness"), Pipeline("old", "Wellness")));
        }

        [Test]
        public void RelocationOtherProjectRejected()
        {
            var error = ProjectBinding.ValidateRelocation(Pipeline("new", "OtherProject"), Pipeline("old", "Wellness"));
            StringAssert.Contains("OtherProject", error);
            StringAssert.Contains("Wellness", error);
        }

        [Test]
        public void RelocationOtherProjectRejectedWhenOldIsOffline()
        {
            // The usual reason to relocate is that the old path is gone; the stored name still decides.
            var error = ProjectBinding.ValidateRelocation(Pipeline("new", "OtherProject"), Path.Combine(_tmp, "offline.json"), "Wellness");
            StringAssert.Contains("OtherProject", error);
        }

        [Test]
        public void RelocationToMissingFileRejected()
        {
            Assert.IsNotNull(ProjectBinding.ValidateRelocation(Path.Combine(_tmp, "nope.json"), Pipeline("old", "Wellness")));
        }

        [Test]
        public void RelocationStopsRunningPrism()
        {
            var backup = ProjectBinding.Load();
            var stopped = false;
            PrismProcess.StopObserver = () => stopped = true;
            try
            {
                var oldCfg = Pipeline("old", "Wellness");
                new ProjectBinding { PrismProjectConfig = oldCfg }.Save();
                var newCfg = Pipeline("moved", "Wellness");
                Assert.IsNull(ProjectBinding.Relocate(newCfg));
                Assert.AreEqual(newCfg.Replace('\\', '/'), ProjectBinding.Load().PrismProjectConfig);
                Assert.IsTrue(stopped, "the running Prism must restart with the new project path");
                Assert.AreEqual("Wellness", ProjectBinding.Load().ProjectName);
            }
            finally
            {
                if (backup != null) backup.Save(); else ProjectBinding.Delete();
            }
        }
    }
}
