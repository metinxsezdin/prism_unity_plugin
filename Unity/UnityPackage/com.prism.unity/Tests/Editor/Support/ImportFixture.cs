using System.IO;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>Copies fixture FBX files into a fake "Prism" source folder and cleans up imports.</summary>
    internal class ImportFixture
    {
        public readonly string SourceDir;
        public static readonly PrismEntity Lotus = PrismEntity.Asset("Props/Lotus");
        public const string LotusProduct = "lotus_model";

        public ImportFixture()
        {
            SourceDir = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "source", Path.GetRandomFileName());
            Directory.CreateDirectory(SourceDir);
        }

        /// <summary>Path of a fixture copied into a fake versioned Prism folder (…/v0001/lotus_v1.fbx).</summary>
        public string Source(string fixtureName, string version)
        {
            var dir = Path.Combine(SourceDir, version);
            Directory.CreateDirectory(dir);
            var dst = Path.Combine(dir, fixtureName);
            File.Copy(TestPaths.Fixture(fixtureName), dst, true);
            return dst;
        }

        public ResolvedVersion Version(string fixtureName, string version) =>
            new ResolvedVersion { Version = version, FilePath = Source(fixtureName, version), Location = "global" };

        public void Cleanup()
        {
            AssetDatabase.DeleteAsset("Assets/Prism");
            if (Directory.Exists(ImportRecord.Folder))
                Directory.Delete(ImportRecord.Folder, true);
            if (Directory.Exists(SourceDir))
                Directory.Delete(SourceDir, true);
            AssetDatabase.Refresh();
        }

        public static string Hash(string projectRelativePath)
        {
            using (var sha = SHA1.Create())
            using (var f = File.OpenRead(Path.Combine(PrismSettings.ProjectRoot, projectRelativePath)))
                return System.BitConverter.ToString(sha.ComputeHash(f));
        }
    }
}
