using System.IO;
using System.Text;
using NUnit.Framework;

namespace Prism.Unity.Editor.Tests
{
    public class ProtocolTests
    {
        [Test]
        public void DecodesSharedFixtures()
        {
            var req = LineCodec.DecodeRequest(File.ReadAllText(TestPaths.ProtocolFixture("request_ping.json")));
            Assert.AreEqual(1, req.V);
            Assert.AreEqual("ping", req.Cmd);
            Assert.AreEqual("tok-abc", req.Token);
            Assert.IsFalse(req.Interactive);

            var ok = LineCodec.DecodeResponse(File.ReadAllText(TestPaths.ProtocolFixture("response_ok.json")));
            Assert.IsTrue(ok.Ok);
            Assert.AreEqual("v2.1.2.1", (string)ok.Result["prismVersion"]);

            var err = LineCodec.DecodeResponse(File.ReadAllText(TestPaths.ProtocolFixture("response_error.json")));
            Assert.IsFalse(err.Ok);
            Assert.AreEqual(ErrorCodes.NeedsInput, err.Error.Code);
            Assert.AreEqual("task", (string)err.Error.Details["missing"][2]);
        }

        [Test]
        public void EncodeEndsWithSingleNewline()
        {
            var bytes = LineCodec.Encode(PrismResponse.Success("1", "Çay Bardağı"));
            var text = Encoding.UTF8.GetString(bytes);
            Assert.IsTrue(text.EndsWith("\n"));
            Assert.AreEqual(1, text.Split('\n').Length - 1);
            Assert.IsTrue(text.Contains("Çay Bardağı"));
        }

        [Test]
        public void EncodedRequestRoundTrips()
        {
            var req = PrismRequest.Create("listVersions", new Newtonsoft.Json.Linq.JObject { ["product"] = "lotus_model" }, "tok", true);
            var back = LineCodec.DecodeRequest(Encoding.UTF8.GetString(LineCodec.Encode(req)));
            Assert.AreEqual(req.Id, back.Id);
            Assert.AreEqual("listVersions", back.Cmd);
            Assert.AreEqual("lotus_model", (string)back.Args["product"]);
            Assert.IsTrue(back.Interactive);
        }

        [Test]
        public void DecodeRejectsGarbage()
        {
            var ex = Assert.Throws<PrismCommandException>(() => LineCodec.DecodeRequest("hello"));
            Assert.AreEqual(ErrorCodes.BadRequest, ex.Code);
        }

        [Test]
        public void DecodeRejectsMissingCmd()
        {
            var ex = Assert.Throws<PrismCommandException>(() => LineCodec.DecodeRequest("{\"v\":1,\"id\":\"1\",\"token\":\"t\"}"));
            Assert.AreEqual(ErrorCodes.BadRequest, ex.Code);
        }

        [Test]
        public void ErrorCodesMatchPython()
        {
            CollectionAssert.AreEquivalent(new[]
            {
                "unknown_command", "bad_token", "bad_request", "bad_args", "needs_input", "needs_confirmation",
                "prism_unavailable", "unity_busy", "missing_package", "source_unavailable", "timeout", "internal"
            }, ErrorCodes.All);
        }
    }
}
