using System.IO;
using NUnit.Framework;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>M9: the project carries a copy of the packages; warn when the plugin on this machine is newer.</summary>
    public class EmbeddedPackagesTests
    {
        string _tmp;
        string _project;
        string _plugin;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "embedded", Path.GetRandomFileName());
            _project = Path.Combine(_tmp, "Project");
            _plugin = Path.Combine(_tmp, "Unity");
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static void Package(string dir, string name, string version)
        {
            Directory.CreateDirectory(Path.Combine(dir, name));
            File.WriteAllText(Path.Combine(dir, name, "package.json"), "{\"name\": \"" + name + "\", \"version\": \"" + version + "\"}");
        }

        [Test]
        public void OlderEmbeddedCopyIsReported()
        {
            Package(Path.Combine(_project, "Packages"), "com.prism.unity", "0.1.0");
            Package(Path.Combine(_plugin, "UnityPackage"), "com.prism.unity", "0.10.0");
            Package(Path.Combine(_project, "Packages"), "com.prism.assets", "0.1.0");
            Package(Path.Combine(_plugin, "UnityPackage"), "com.prism.assets", "0.1.0");
            var outdated = EmbeddedPackages.Outdated(_project, _plugin);
            Assert.AreEqual(1, outdated.Count);
            StringAssert.Contains("com.prism.unity 0.1.0", outdated[0]);
            StringAssert.Contains("0.10.0", outdated[0]);
        }

        [Test]
        public void NewerOrEqualEmbeddedCopyIsFine()
        {
            Package(Path.Combine(_project, "Packages"), "com.prism.unity", "0.3.0");
            Package(Path.Combine(_plugin, "UnityPackage"), "com.prism.unity", "0.2.0-pre");
            Assert.IsEmpty(EmbeddedPackages.Outdated(_project, _plugin));
        }

        [Test]
        public void NothingEmbeddedOrNoPluginIsFine()
        {
            Package(Path.Combine(_plugin, "UnityPackage"), "com.prism.unity", "0.2.0");
            Assert.IsEmpty(EmbeddedPackages.Outdated(_project, _plugin));
            Assert.IsEmpty(EmbeddedPackages.Outdated(_project, null));
        }
    }
}
