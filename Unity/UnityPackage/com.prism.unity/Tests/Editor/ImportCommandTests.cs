using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>The Prism → Unity import commands (what Prism's import windows call).</summary>
    public class ImportCommandTests
    {
        ImportFixture _fx;

        [SetUp]
        public void SetUp() => _fx = new ImportFixture();

        [TearDown]
        public void TearDown() => _fx.Cleanup();

        static JToken Run(string cmd, JObject args)
        {
            Assert.IsTrue(CommandRegistry.TryGet(cmd, out var h, out var mutates), cmd);
            Assert.IsTrue(mutates, cmd + " changes the project");
            return h(args, new CommandContext { Interactive = true });
        }

        JObject Resolved(string fixture, string version) => JObject.FromObject(_fx.Version(fixture, version));

        [Test]
        public void ImportProductUsesResolvedVersion()
        {
            var result = Run("importProduct", new JObject
            {
                ["entity"] = ImportFixture.Lotus.ToJson(),
                ["product"] = "lotus_model",
                ["version"] = "v0001",
                ["resolved"] = Resolved("lotus_v1.fbx", "v0001"),
            });
            Assert.AreEqual("v0001", (string)result["record"]["version"]);
            Assert.AreEqual("Props__Lotus__lotus_model", (string)result["record"]["id"]);
        }

        [Test]
        public void ImportProductWithoutResolvedIsBadArgs()
        {
            var ex = Assert.Throws<PrismCommandException>(() => Run("importProduct", new JObject
            {
                ["entity"] = ImportFixture.Lotus.ToJson(),
                ["product"] = "lotus_model",
            }));
            Assert.AreEqual(ErrorCodes.BadArgs, ex.Code);
        }

        [Test]
        public void UpdateProductByRecordId()
        {
            Run("importProduct", new JObject
            {
                ["entity"] = ImportFixture.Lotus.ToJson(), ["product"] = "lotus_model", ["resolved"] = Resolved("lotus_v1.fbx", "v0001"),
            });
            var result = Run("updateProduct", new JObject
            {
                ["recordId"] = "Props__Lotus__lotus_model", ["version"] = "v0002", ["resolved"] = Resolved("lotus_v2.fbx", "v0002"),
            });
            Assert.IsTrue((bool)result["updated"]);
            Assert.AreEqual("v0002", ImportRecord.Load("Props__Lotus__lotus_model").Version);
        }

        [Test]
        public void UpdateUnknownRecordIsBadArgs()
        {
            var ex = Assert.Throws<PrismCommandException>(() => Run("updateProduct", new JObject
            {
                ["recordId"] = "nope", ["resolved"] = Resolved("lotus_v2.fbx", "v0002"),
            }));
            Assert.AreEqual(ErrorCodes.BadArgs, ex.Code);
        }

        [Test]
        public void ListImportedReturnsRecords()
        {
            Run("importProduct", new JObject
            {
                ["entity"] = ImportFixture.Lotus.ToJson(), ["product"] = "lotus_model", ["resolved"] = Resolved("lotus_v1.fbx", "v0001"),
            });
            Assert.IsTrue(CommandRegistry.TryGet("listImported", out var h, out var mutates));
            Assert.IsFalse(mutates);
            var list = (JArray)h(new JObject(), new CommandContext());
            Assert.AreEqual(1, list.Count);
            Assert.AreEqual("lotus_model", (string)list[0]["product"]);
            Assert.AreEqual("Props/Lotus", (string)list[0]["entity"]["asset_path"]);
        }
    }
}
