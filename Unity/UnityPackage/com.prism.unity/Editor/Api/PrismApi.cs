using System;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// The one entry point for every Prism operation in Unity. The menu, commands coming from
    /// Prism and the Claude (MCP) tools all go through here.
    /// </summary>
    public static partial class PrismApi
    {
        /// <summary>Send an interactive command to Prism (Prism may open its own windows).</summary>
        public static Task<JToken> RunInteractive(string cmd, JObject args = null) =>
            PrismClient.SendAsync(cmd, args, interactive: true);

        /// <summary>Menu helper: run a command and report failures in the console and a dialog.</summary>
        internal static void RunFromMenu(string cmd, JObject args = null)
        {
            RunInteractive(cmd, args).ContinueWith(t =>
            {
                if (!t.IsFaulted) return;
                var e = t.Exception.GetBaseException();
                var message = e is PrismCommandException p ? $"{p.Message} ({p.Code})" : e.Message;
                EditorApplication.delayCall += () =>
                {
                    Debug.LogError($"[Prism] {cmd} failed: {message}");
                    EditorUtility.DisplayDialog("Prism", message, "OK");
                };
            });
        }
    }
}
