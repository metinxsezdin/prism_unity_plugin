using System.IO;

namespace Prism.Unity.Editor.Tests
{
    internal static class TestPaths
    {
        /// <summary>Absolute path of this package (…/Unity/UnityPackage/com.prism.unity).</summary>
        public static string PackageRoot =>
            Path.GetFullPath(UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(TestPaths).Assembly).resolvedPath);

        /// <summary>Repository root (three levels above the package).</summary>
        public static string RepoRoot => Path.GetFullPath(Path.Combine(PackageRoot, "..", "..", ".."));

        public static string ProtocolFixture(string name) => Path.Combine(RepoRoot, "protocol", "fixtures", name);

        public static string Fixture(string name) => Path.Combine(PackageRoot, "Tests", "Editor", "Fixtures~", name);
    }
}
