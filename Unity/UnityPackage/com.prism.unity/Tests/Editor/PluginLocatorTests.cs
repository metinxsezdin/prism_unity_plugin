using System;
using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests
{
    public class PluginLocatorTests
    {
        string _root;

        [SetUp]
        public void SetUp()
        {
            _root = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "locator", Path.GetRandomFileName());
            Directory.CreateDirectory(_root);
        }

        [TearDown]
        public void TearDown()
        {
            PluginLocator.TestSearch = null;
            Directory.Delete(_root, true);
        }

        string MakePlugin(string name)
        {
            var dir = Path.Combine(_root, name);
            Directory.CreateDirectory(Path.Combine(dir, "Scripts"));
            File.WriteAllText(Path.Combine(dir, "Scripts", "Prism_Unity_Launcher.py"), "# launcher");
            return dir;
        }

        string PluginPaths(params string[] paths)
        {
            var file = Path.Combine(_root, "PluginPaths.json");
            var items = string.Join(",", Array.ConvertAll(paths, p => $"{{\"path\": \"{p.Replace("\\", "\\\\")}\"}}"));
            File.WriteAllText(file, $"{{\"plugins\": [{items}], \"searchPaths\": []}}");
            return file;
        }

        [Test]
        public void PrefsOverrideWins()
        {
            var a = MakePlugin("A");
            var b = MakePlugin("B");
            Assert.AreEqual(Path.GetFullPath(a), PluginLocator.Find(PluginPaths(b), null, a, null));
        }

        [Test]
        public void FindsLauncherFromPluginPaths()
        {
            var other = Path.Combine(_root, "Maya");
            Directory.CreateDirectory(other);
            var unity = MakePlugin("Unity Plugin Ğ");
            Assert.AreEqual(Path.GetFullPath(unity), PluginLocator.Find(PluginPaths(other, unity), null, null, null));
        }

        [Test]
        public void FallsBackToProgramData()
        {
            var programData = Path.Combine(_root, "ProgramData", "plugins");
            var unity = Path.Combine(programData, "Unity");
            Directory.CreateDirectory(Path.Combine(unity, "Scripts"));
            File.WriteAllText(Path.Combine(unity, "Scripts", "Prism_Unity_Launcher.py"), "#");
            Assert.AreEqual(Path.GetFullPath(unity), PluginLocator.Find(Path.Combine(_root, "missing.json"), programData, null, null));
        }

        [Test]
        public void RepoLayoutFallbackForTheTestProject()
        {
            var plugin = MakePlugin("RepoUnity");
            var package = Path.Combine(plugin, "UnityPackage", "com.prism.unity");
            Directory.CreateDirectory(package);
            Assert.AreEqual(Path.GetFullPath(plugin), PluginLocator.Find(null, null, null, package));
        }

        [Test]
        public void EmbeddedPackageIsNotMistakenForThePlugin()
        {
            var project = Path.Combine(_root, "UnityProject");
            var package = Path.Combine(project, "Packages", "com.prism.unity");
            Directory.CreateDirectory(package);
            Assert.IsNull(PluginLocator.Find(null, null, null, package));
        }

        [UnityTest]
        public IEnumerator SendAsyncWithoutPluginIsPrismUnavailable()
        {
            PluginLocator.TestSearch = () => null;
            var started = DateTime.UtcNow;
            var task = PrismClient.SendAsync("ping", null, interactive: false);
            while (!task.IsCompleted && (DateTime.UtcNow - started).TotalSeconds < 10) yield return null;
            var ex = task.Exception?.GetBaseException() as PrismCommandException;
            Assert.IsNotNull(ex);
            Assert.AreEqual(ErrorCodes.PrismUnavailable, ex.Code);
            StringAssert.Contains("plugin", ex.Message);
            Assert.Less((DateTime.UtcNow - started).TotalSeconds, 2.0);
        }
    }
}
