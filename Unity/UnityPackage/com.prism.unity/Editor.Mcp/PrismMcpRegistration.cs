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
    static class PrismMcpRegistration
    {
        static PrismMcpRegistration() => EditorApplication.delayCall += RegisterAll;

        static void RegisterAll()
        {
            foreach (var tool in PrismMcpTools.Tools)
                McpToolRegistry.RegisterTool(tool.Name, new PrismMcpTool(tool), tool.Description,
                    enabledByDefault: true, groups: new[] { "Prism" });
        }
    }

    sealed class PrismMcpTool : IUnityMcpTool
    {
        readonly PrismMcpTools.ToolSpec _spec;

        public PrismMcpTool(PrismMcpTools.ToolSpec spec) => _spec = spec;

        public async Task<object> ExecuteAsync(object parameters)
        {
            var args = parameters as JObject ?? (parameters == null ? new JObject() : JObject.FromObject(parameters));
            return await PrismMcpTools.Invoke(_spec.Name, args);
        }

        public object GetInputSchema() => _spec.InputSchema;

        public object GetOutputSchema() => null;
    }
}
