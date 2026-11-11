using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// Once per editor session: when Prism's "check import versions" setting is on and this project
    /// has Prism imports, ask Prism to show its "new versions available" window (silent if all current).
    /// </summary>
    [InitializeOnLoad]
    public static class StartupVersionCheck
    {
        const string DoneKey = "PrismUnity.StartupVersionCheckDone";

        static StartupVersionCheck()
        {
            if (Application.isBatchMode || SessionState.GetBool(DoneKey, false))
                return;
            EditorApplication.delayCall += Run;
        }

        static void Run()
        {
            SessionState.SetBool(DoneKey, true);
            if (ImportRecord.LoadAll().Count == 0 || ProjectBinding.Load() == null)
                return;
            PrismClient.SendAsync("ping", null, interactive: false, timeout: System.TimeSpan.FromSeconds(60)).ContinueWith(t =>
            {
                if (t.IsFaulted || !((bool?)t.Result?["checkImportVersions"] ?? false))
                    return;
                EditorApplication.delayCall += () =>
                    PrismClient.SendAsync("checkVersionsDialog", new JObject { ["quiet"] = true }, interactive: true);
            });
        }
    }
}
