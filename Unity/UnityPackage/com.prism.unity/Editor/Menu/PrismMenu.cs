using UnityEditor;

namespace Prism.Unity.Editor
{
    /// <summary>The Prism menu. Every item sends an interactive command; Prism shows its own windows.</summary>
    public static class PrismMenu
    {
        [MenuItem("Prism/Project Browser", priority = 1)]
        static void ProjectBrowser() => PrismApi.RunFromMenu("projectBrowser");

        [MenuItem("Prism/Save Version", priority = 20)]
        static void SaveVersion() => PrismApi.RunFromMenu("saveVersion");

        [MenuItem("Prism/Save Comment...", priority = 21)]
        static void SaveComment() => PrismApi.RunFromMenu("saveComment");

        [MenuItem("Prism/Import...", priority = 40)]
        static void Import() => PrismApi.RunFromMenu("importDialog");

        [MenuItem("Prism/Check for New Versions...", priority = 41)]
        static void CheckVersions() => PrismApi.RunFromMenu("checkVersionsDialog");

        [MenuItem("Prism/Playblast...", priority = 60)]
        static void Playblast() => PrismApi.RunFromMenu("playblastDialog");

        [MenuItem("Prism/Prism Settings...", priority = 80)]
        static void Settings() => PrismApi.RunFromMenu("settings");
    }
}
