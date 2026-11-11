using System.IO;
using UnityEditor;

namespace Prism.Unity.Editor
{
    /// <summary>Machine-specific paths, kept in EditorPrefs (not in the shared project).</summary>
    public static class PrismSettings
    {
        const string PrismRootKey = "PrismUnity.PrismRoot";
        public const string DefaultPrismRoot = @"C:\Program Files\Prism2";

        public static string PrismRoot
        {
            get => EditorPrefs.GetString(PrismRootKey, DefaultPrismRoot);
            set => EditorPrefs.SetString(PrismRootKey, value);
        }

        /// <summary>The Prism plugin folder ("Unity"), two levels above this package.</summary>
        public static string PluginDir
        {
            get
            {
                var info = UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(PrismSettings).Assembly);
                return Path.GetFullPath(Path.Combine(info.resolvedPath, "..", ".."));
            }
        }

        public static string ProjectRoot => Path.GetFullPath(Path.Combine(UnityEngine.Application.dataPath, ".."));
    }
}
