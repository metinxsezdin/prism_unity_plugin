using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>The Claude tools, with Prism faked through PrismClient.Override.</summary>
    public class PrismMcpToolsTests
    {
        ImportFixture _fx;
        readonly List<(string cmd, bool interactive)> _calls = new List<(string, bool)>();

        [SetUp]
        public void SetUp()
        {
            _fx = new ImportFixture();
            _calls.Clear();
            PrismClient.Observer = (cmd, interactive) => _calls.Add((cmd, interactive));
            PrismClient.Override = (cmd, args, interactive) =>
            {
                if (cmd == "resolveVersion")
                {
                    var v = (string)args["version"];
                    var fixture = v == "v0003" ? "lotus_v3_renamed.fbx" : v == "v0002" ? "lotus_v2.fbx" : "lotus_v1.fbx";
                    var version = v == "latest" ? "v0001" : v;
                    return JObject.FromObject(_fx.Version(fixture, version));
                }
                if (cmd == "listProducts") return new JArray(new JObject { ["product"] = "lotus_model", ["entity"] = args["entity"] });
                if (cmd == "checkVersions") return new JArray();
                throw new PrismCommandException(ErrorCodes.UnknownCommand, "fake Prism: " + cmd);
            };
        }

        [TearDown]
        public void TearDown()
        {
            PrismClient.Override = null;
            PrismClient.Observer = null;
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            _fx.Cleanup();
        }

        static IEnumerator Run(string tool, JObject args, JObject[] result)
        {
            var task = PrismMcpTools.Invoke(tool, args);
            while (!task.IsCompleted) yield return null;
            Assert.IsFalse(task.IsFaulted, "Invoke must never throw: " + task.Exception);
            result[0] = task.Result;
        }

        static JObject Lotus => new JObject { ["type"] = "asset", ["asset_path"] = "Props/Lotus" };

        [UnityTest]
        public IEnumerator ImportReturnsJsonResult()
        {
            var r = new JObject[1];
            yield return Run("prism_import", new JObject { ["entity"] = Lotus, ["product"] = "lotus_model", ["version"] = "v0001" }, r);
            Assert.IsTrue((bool)r[0]["ok"], r[0].ToString());
            Assert.AreEqual("v0001", (string)r[0]["result"]["record"]["version"]);
            Assert.AreEqual("Assets/Prism/Props/Lotus/lotus_model/lotus_model.fbx", (string)r[0]["result"]["record"]["assetPath"]);
        }

        [UnityTest]
        public IEnumerator NeedsConfirmationIsReturnedNotThrown()
        {
            var r = new JObject[1];
            yield return Run("prism_import", new JObject { ["entity"] = Lotus, ["product"] = "lotus_model", ["version"] = "v0001" }, r);
            yield return Run("prism_update", new JObject { ["recordId"] = "Props__Lotus__lotus_model", ["version"] = "v0003" }, r);
            Assert.IsFalse((bool)r[0]["ok"]);
            Assert.AreEqual("needs_confirmation", (string)r[0]["error"]["code"]);
            CollectionAssert.Contains(r[0]["error"]["details"]["removedNodes"].ToObject<string[]>(), "Stem");

            yield return Run("prism_update", new JObject { ["recordId"] = "Props__Lotus__lotus_model", ["version"] = "v0003", ["confirm"] = true }, r);
            Assert.IsTrue((bool)r[0]["ok"], r[0].ToString());
        }

        [UnityTest]
        public IEnumerator BadJsonReturnsBadArgs()
        {
            var r = new JObject[1];
            yield return Run("prism_import", new JObject { ["product"] = "lotus_model" }, r);
            Assert.IsFalse((bool)r[0]["ok"]);
            Assert.AreEqual("bad_args", (string)r[0]["error"]["code"]);
        }

        [UnityTest]
        public IEnumerator UnknownToolIsUnknownCommand()
        {
            var r = new JObject[1];
            yield return Run("prism_format_c_drive", new JObject(), r);
            Assert.AreEqual("unknown_command", (string)r[0]["error"]["code"]);
        }

        [UnityTest]
        public IEnumerator AllToolsAreNonInteractive()
        {
            var r = new JObject[1];
            yield return Run("prism_list_products", new JObject { ["entity"] = Lotus }, r);
            yield return Run("prism_import", new JObject { ["entity"] = Lotus, ["product"] = "lotus_model" }, r);
            yield return Run("prism_check_updates", new JObject(), r);
            yield return Run("prism_list_imported", new JObject(), r);
            Assert.Greater(_calls.Count, 0);
            Assert.IsTrue(_calls.All(c => !c.interactive), string.Join(", ", _calls.Select(c => c.cmd + ":" + c.interactive)));
            Assert.AreEqual(1, ((JArray)r[0]["result"]).Count);
        }

        [UnityTest]
        public IEnumerator ProjectChangingToolsAreRefusedInPlayMode()
        {
            var r = new JObject[1];
            yield return Run("prism_import", new JObject { ["entity"] = Lotus, ["product"] = "lotus_model", ["version"] = "v0001" }, r);
            Assert.IsTrue((bool)r[0]["ok"], r[0].ToString());
            _calls.Clear();
            PrismSession.PlayModeOverride = true;
            try
            {
                var calls = new[]
                {
                    ("prism_import", new JObject { ["entity"] = Lotus, ["product"] = "lotus_model", ["version"] = "v0002" }),
                    ("prism_update", new JObject { ["recordId"] = "Props__Lotus__lotus_model", ["version"] = "v0002" }),
                    ("prism_open_scene_version", new JObject { ["path"] = "C:/nowhere/x_v0001.unity", ["unsaved"] = "discard" }),
                    ("prism_save_version", new JObject { ["comment"] = "x", ["entity"] = Lotus, ["task"] = "layout" }),
                };
                foreach (var (tool, args) in calls)
                {
                    yield return Run(tool, args, r);
                    Assert.AreEqual("unity_busy", (string)r[0]["error"]?["code"], tool + ": " + r[0]);
                }
                Assert.AreEqual(0, _calls.Count, "Nothing may reach Prism while Unity is in Play Mode.");
                Assert.AreEqual("v0001", ImportRecord.Load("Props__Lotus__lotus_model").Version);
            }
            finally
            {
                PrismSession.PlayModeOverride = null;
            }
        }

        [UnityTest]
        public IEnumerator ImportResultIncludesPackage()
        {
            var r = new JObject[1];
            yield return Run("prism_import", new JObject { ["entity"] = Lotus, ["product"] = "lotus_model", ["version"] = "v0001" }, r);
            Assert.IsTrue((bool)r[0]["ok"], r[0].ToString());
            var package = r[0]["result"]["package"];
            Assert.IsNotNull(package, r[0].ToString());
            Assert.AreEqual("Assets/Prism/Props/Lotus/lotus_model/lotus_model.prefab", (string)package["prefabPath"]);
            Assert.AreEqual("Assets/Prism/Props/Lotus/lotus_model/lotus_model.asset", (string)package["definitionPath"]);
            Assert.AreEqual("Props/Lotus/lotus_model", (string)package["addressableKey"]);

            yield return Run("prism_list_imported", new JObject(), r);
            Assert.AreEqual("Props/Lotus/lotus_model", (string)r[0]["result"][0]["package"]["addressableKey"], r[0].ToString());
        }

        [UnityTest]
        public IEnumerator ConvertWithoutConfirmNeedsConfirmation()
        {
            var r = new JObject[1];
            yield return Run("prism_import", new JObject { ["entity"] = Lotus, ["product"] = "lotus_model", ["version"] = "v0001" }, r);
            yield return Run("prism_convert_definitions", new JObject { ["className"] = "TestItemDefinition" }, r);
            Assert.IsFalse((bool)r[0]["ok"], r[0].ToString());
            Assert.AreEqual("needs_confirmation", (string)r[0]["error"]["code"]);
            Assert.AreEqual(1, (int)r[0]["error"]["details"]["count"]);
            Assert.IsNotInstanceOf<TestItemDefinition>(AssetDatabase.LoadMainAssetAtPath("Assets/Prism/Props/Lotus/lotus_model/lotus_model.asset"));

            yield return Run("prism_convert_definitions", new JObject { ["className"] = "TestItemDefinition", ["confirm"] = true }, r);
            Assert.IsTrue((bool)r[0]["ok"], r[0].ToString());
            Assert.AreEqual(1, (int)r[0]["result"]["converted"]);
            Assert.IsInstanceOf<TestItemDefinition>(AssetDatabase.LoadMainAssetAtPath("Assets/Prism/Props/Lotus/lotus_model/lotus_model.asset"));
        }

        [UnityTest]
        public IEnumerator GeneratePackagesReturnsCount()
        {
            var r = new JObject[1];
            yield return Run("prism_import", new JObject { ["entity"] = Lotus, ["product"] = "lotus_model", ["version"] = "v0001" }, r);
            yield return Run("prism_generate_packages", new JObject(), r);
            Assert.IsTrue((bool)r[0]["ok"], r[0].ToString());
            Assert.AreEqual(0, (int)r[0]["result"]["generated"], "import already packaged it");
        }

        [Test]
        public void EveryToolHasDescriptionAndObjectSchema()
        {
            var names = PrismMcpTools.Tools.Select(t => t.Name).ToArray();
            CollectionAssert.AreEquivalent(new[]
            {
                "prism_list_products", "prism_list_versions", "prism_list_imported", "prism_import", "prism_update",
                "prism_check_updates", "prism_save_version", "prism_open_scene_version", "prism_playblast", "prism_list_cameras",
                "prism_generate_packages", "prism_convert_definitions",
            }, names);
            foreach (var t in PrismMcpTools.Tools)
            {
                Assert.IsFalse(string.IsNullOrWhiteSpace(t.Description), t.Name);
                Assert.AreEqual("object", (string)t.InputSchema["type"], t.Name);
            }
        }

        [Test]
        public void GuideDocumentsEveryTool()
        {
            var guide = File.ReadAllText(Path.Combine(TestPaths.PackageRoot, "Documentation~", "CLAUDE_TOOLS.md"));
            foreach (var t in PrismMcpTools.Tools)
                StringAssert.Contains(t.Name, guide);
            StringAssert.Contains("needs_confirmation", guide);
            StringAssert.Contains("needs_input", guide);
        }
    }
}
