using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// The Prism tools Claude calls through Unity MCP. Every tool runs non-interactively (no window
    /// opens anywhere) and answers {ok:true, result} or {ok:false, error:{code, message, details}};
    /// Invoke never throws. Documentation~/CLAUDE_TOOLS.md explains each tool to Claude.
    /// </summary>
    public static class PrismMcpTools
    {
        public class ToolSpec
        {
            public string Name;
            public string Description;
            public JObject InputSchema;
            internal Func<JObject, Task<JToken>> Handler;
        }

        /// <summary>Filled by the asset-packaging assembly: record id → package info (prefab, definition, Addressable key, thumbnail).</summary>
        public static Func<string, JObject> PackageInfoProvider;

        /// <summary>Filled by the asset-packaging assembly: package every imported product that has no complete package; returns {generated, repaired, failed}.</summary>
        public static Func<Task<JToken>> GeneratePackagesHandler;

        /// <summary>Filled by the asset-packaging assembly: (className, confirm) → result; throws needs_confirmation without confirm.</summary>
        public static Func<string, bool, JToken> ConvertDefinitionsHandler;

        // Declared before Tools: static fields initialize in textual order.
        static readonly JObject EntitySchema = new JObject
        {
            ["type"] = "object",
            ["description"] = "Prism entity: {\"type\":\"asset\",\"asset_path\":\"Props/Lotus\"} or {\"type\":\"shot\",\"sequence\":\"sq01\",\"shot\":\"sh010\"}",
            ["properties"] = new JObject
            {
                ["type"] = new JObject { ["type"] = "string", ["enum"] = new JArray("asset", "shot") },
                ["asset_path"] = new JObject { ["type"] = "string", ["description"] = "Asset path, e.g. Props/Lotus" },
                ["sequence"] = new JObject { ["type"] = "string", ["description"] = "Sequence" },
                ["shot"] = new JObject { ["type"] = "string", ["description"] = "Shot" },
            },
            ["required"] = new JArray("type"),
        };

        public static readonly IReadOnlyList<ToolSpec> Tools = new List<ToolSpec>
        {
            Tool("prism_list_products", "List the Prism products (published exports) of a Prism entity.",
                Schema(Req("entity", EntitySchema)),
                async a => await PrismApi.ListProducts(UnityCommands.RequireEntity(a))),
            Tool("prism_list_versions", "List the versions of a Prism product with comment, user and file path.",
                Schema(Req("entity", EntitySchema), Req("product", Str("Product name, e.g. lotus_model"))),
                async a => await PrismApi.ListVersions(UnityCommands.RequireEntity(a), UnityCommands.RequireString(a, "product"))),
            Tool("prism_list_imported", "List the Prism products imported into this Unity project, with their versions and asset paths.",
                Schema(),
                a => Task.FromResult<JToken>(new JArray(PrismApi.ListImported().Select(r => WithPackage(JObject.FromObject(r), r.Id))))),
            Tool("prism_import", "Import a Prism product version into Assets/Prism/<entity>/<product>/. Re-importing updates in place and keeps material assignments.",
                Schema(Req("entity", EntitySchema), Req("product", Str("Product name")),
                    Opt("version", Str("'latest' (default), 'master' or e.g. 'v0002'")),
                    Opt("confirm", Bool("Apply even if the new version renames/removes objects or materials (only after asking the user)"))),
                async a => WithPackage(await PrismApi.ImportProduct(UnityCommands.RequireEntity(a), UnityCommands.RequireString(a, "product"),
                    (string)a["version"] ?? "latest", (bool?)a["confirm"] ?? false))),
            Tool("prism_update", "Update an imported product (by record id from prism_list_imported) to another version, 'latest' by default.",
                Schema(Req("recordId", Str("Record id, e.g. Props__Lotus__lotus_model")), Opt("version", Str("'latest' (default) or e.g. 'v0003'")),
                    Opt("confirm", Bool("Apply a breaking update (only after asking the user)"))),
                async a => WithPackage(await PrismApi.UpdateProduct(UnityCommands.RequireString(a, "recordId"),
                    (string)a["version"] ?? "latest", (bool?)a["confirm"] ?? false))),
            Tool("prism_check_updates", "List imported products that have a newer version in Prism.",
                Schema(),
                async a => await PrismApi.CheckForUpdates()),
            Tool("prism_save_version", "Save the active Unity scene as a new Prism version. The first save of a scene needs entity and task.",
                Schema(Opt("comment", Str("Version comment")), Opt("entity", EntitySchema), Opt("department", Str("Prism department, default 'Unity'")),
                    Opt("task", Str("Prism task, e.g. 'layout'")), Opt("createDepartment", Bool("Create the department if missing (only after asking the user)"))),
                async a => await PrismApi.SaveVersion((string)a["comment"] ?? "", a["entity"] is JObject e ? PrismEntity.FromJson(e) : null,
                    (string)a["department"], (string)a["task"], (bool?)a["createDepartment"] ?? false)),
            Tool("prism_open_scene_version", "Open a Prism scene version (.unity path inside the Prism project) in Unity.",
                Schema(Req("path", Str("Path of the Prism scene version")),
                    Opt("unsaved", Enum("What to do with unsaved changes in the open scene", "abort", "save", "discard")),
                    Opt("confirmForeign", Bool("Open a version saved from another Unity project (only after asking the user)"))),
                async a => await PrismApi.OpenSceneVersion(UnityCommands.RequireString(a, "path"), (string)a["unsaved"] ?? "abort",
                    (bool?)a["confirmForeign"] ?? false)),
            Tool("prism_playblast", "Render a turntable of objects (mode 'turntable') or a scene camera (mode 'free') and publish it to Prism's media.",
                Schema(Req("mode", Enum("turntable or free", "turntable", "free")),
                    Opt("targetPaths", new JObject { ["type"] = "array", ["items"] = Str("Hierarchy path"), ["description"] = "Turntable objects; default: the selection" }),
                    Opt("cameraPath", Str("Camera hierarchy path for mode 'free'")), Opt("width", Int("Default 1920")), Opt("height", Int("Default 1080")),
                    Opt("frames", Int("Default 120")), Opt("fps", Int("Default 30")), Opt("format", Enum("png sequence or mp4", "png", "mp4")),
                    Opt("comment", Str("Comment")), Opt("task", Str("Prism media task; default Turntable / Playblast")), Opt("entity", EntitySchema)),
                async a => JObject.FromObject(await PrismApi.Playblast(a.ToObject<PlayblastRequest>()))),
            Tool("prism_list_cameras", "List the cameras in the active scene (for prism_playblast mode 'free').",
                Schema(),
                a =>
                {
                    CommandRegistry.TryGet("listCameras", out var h, out _);
                    return Task.FromResult(h(new JObject(), new CommandContext()));
                }),
            Tool("prism_generate_packages", "Create the asset package (prefab variant, definition, thumbnail, Addressable entries, catalog entry) for every imported product that has none. Existing packages are left as they are.",
                Schema(),
                async a =>
                {
                    PrismApi.EnsureEditable();
                    return await RequirePackaging(GeneratePackagesHandler)();
                }),
            Tool("prism_convert_definitions", "Switch every package definition to a team definition class (a subclass of PrismAssetDefinition). Files, GUIDs and same-named fields are kept. Without confirm it only reports how many would change.",
                Schema(Req("className", Str("Class name, e.g. 'WellnessItemDefinition' or 'MyGame.WellnessItemDefinition'")),
                    Opt("confirm", Bool("Convert (only after telling the user how many definitions change)"))),
                a =>
                {
                    PrismApi.EnsureEditable();
                    return Task.FromResult(RequirePackaging(ConvertDefinitionsHandler)(UnityCommands.RequireString(a, "className"), (bool?)a["confirm"] ?? false));
                }),
        };

        static JObject WithPackage(ImportResult result) => WithPackage(JObject.FromObject(result), result.Record?.Id);

        static JObject WithPackage(JObject json, string recordId)
        {
            var package = recordId == null ? null : PackageInfoProvider?.Invoke(recordId);
            if (package != null) json["package"] = package;
            return json;
        }

        static T RequirePackaging<T>(T handler) where T : class =>
            handler ?? throw new PrismCommandException(ErrorCodes.MissingPackage,
                "Asset packaging is not available: the com.prism.assets package is not installed in this Unity project.");

        public static async Task<JObject> Invoke(string toolName, JObject args)
        {
            var tool = Tools.FirstOrDefault(t => t.Name == toolName);
            if (tool == null)
                return Error(ErrorCodes.UnknownCommand, $"Unknown Prism tool '{toolName}'.", null);
            try
            {
                // Start every tool on the main thread (Unity APIs), whichever thread the bridge uses.
                var started = await MainThreadDispatcher.Run(() => tool.Handler(args ?? new JObject()), TimeSpan.FromSeconds(30));
                var result = await started;
                return new JObject { ["ok"] = true, ["result"] = result ?? JValue.CreateNull() };
            }
            catch (PrismCommandException e)
            {
                return Error(e.Code, e.Message, e.Details);
            }
            catch (Exception e) when (e is JsonException || e is ArgumentException || e is FormatException || e is InvalidCastException)
            {
                return Error(ErrorCodes.BadArgs, e.Message, null);
            }
            catch (Exception e)
            {
                return Error(ErrorCodes.Internal, $"{e.GetType().Name}: {e.Message}", null);
            }
        }

        static JObject Error(string code, string message, JObject details) => new JObject
        {
            ["ok"] = false,
            ["error"] = new JObject { ["code"] = code, ["message"] = message, ["details"] = details ?? new JObject() },
        };

        // --- schema helpers ------------------------------------------------------

        static ToolSpec Tool(string name, string description, JObject schema, Func<JObject, Task<JToken>> handler) =>
            new ToolSpec { Name = name, Description = description, InputSchema = schema, Handler = handler };

        static (string, JObject, bool) Req(string name, JObject schema) => (name, schema, true);
        static (string, JObject, bool) Opt(string name, JObject schema) => (name, schema, false);
        static JObject Str(string d) => new JObject { ["type"] = "string", ["description"] = d };
        static JObject Int(string d) => new JObject { ["type"] = "integer", ["description"] = d };
        static JObject Bool(string d) => new JObject { ["type"] = "boolean", ["description"] = d };
        static JObject Enum(string d, params string[] values) => new JObject { ["type"] = "string", ["description"] = d, ["enum"] = new JArray(values) };

        static JObject Schema(params (string name, JObject schema, bool required)[] props) => new JObject
        {
            ["type"] = "object",
            ["properties"] = new JObject(props.Select(p => new JProperty(p.name, p.schema))),
            ["required"] = new JArray(props.Where(p => p.required).Select(p => p.name)),
        };
    }
}
