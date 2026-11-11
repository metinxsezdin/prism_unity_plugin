using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using Unity.AI.MCP.Editor.ToolRegistry;
using UnityEditor;

namespace Prism.Unity.Editor.Mcp
{
    /// <summary>
    /// Registers the Prism tools with Unity AI Assistant's MCP bridge. This assembly only compiles
    /// when com.unity.ai.assistant is installed (asmdef versionDefines → PRISM_UNITY_AI_MCP).
    /// </summary>
    [InitializeOnLoad]
    public static class PrismMcpRegistration
    {
        static PrismMcpRegistration()
        {
            // McpToolRegistry.RefreshTools() drops dynamically registered tools, and the bridge refreshes
            // after startup in the interactive editor, so register again after every refresh.
            McpToolRegistry.ToolsChanged += e =>
            {
                if (e.ChangeType == McpToolRegistry.ToolChangeType.Refreshed)
                    MainThreadDispatcher.Defer(RegisterAll);
            };
            MainThreadDispatcher.Defer(RegisterAll);
        }

        [MenuItem("Prism/Debug/Re-register Claude (MCP) Tools", priority = 200)]
        static void RegisterFromMenu() => RegisterAll();

        public static void RegisterAll()
        {
            foreach (var tool in PrismMcpTools.Tools)
            {
                try
                {
                    McpToolRegistry.RegisterTool(tool.Name, new PrismMcpTool(tool), tool.Description,
                        enabledByDefault: true, groups: new[] { "Prism" });
                }
                catch (System.Exception e)
                {
                    UnityEngine.Debug.LogError($"[Prism] Could not register MCP tool {tool.Name}: {e}");
                }
            }
        }
    }

    sealed class PrismMcpTool : IUnityMcpTool
    {
        readonly PrismMcpTools.ToolSpec _spec;

        public PrismMcpTool(PrismMcpTools.ToolSpec spec) => _spec = spec;

        public async Task<object> ExecuteAsync(object parameters)
        {
            var args = parameters as JObject ?? (parameters == null ? new JObject() : JObject.FromObject(parameters));
            return ToBridgeShape(_spec.Name, await PrismMcpTools.Invoke(_spec.Name, args));
        }

        /// <summary>The bridge reads {success, message, data} / {success:false, code, error, data}.</summary>
        internal static JObject ToBridgeShape(string tool, JObject envelope)
        {
            if ((bool?)envelope["ok"] == true)
                return new JObject { ["success"] = true, ["message"] = $"{tool} succeeded", ["data"] = envelope["result"] };
            var error = (JObject)envelope["error"] ?? new JObject();
            return new JObject
            {
                ["success"] = false,
                ["code"] = error["code"],
                ["error"] = $"{error["code"]}: {error["message"]}",
                ["data"] = error["details"] ?? new JObject(),
            };
        }

        public object GetInputSchema() => _spec.InputSchema;

        public object GetOutputSchema() => null;
    }
}
