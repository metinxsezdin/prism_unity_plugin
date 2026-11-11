using System.Diagnostics;
using System.IO;
using NUnit.Framework;

namespace Prism.Unity.Editor.Tests
{
    public class PrismEndpointTests
    {
        string _root;

        [SetUp]
        public void SetUp()
        {
            _root = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "ep", Path.GetRandomFileName());
            Directory.CreateDirectory(Path.Combine(_root, "Library", "PrismUnity"));
        }

        [TearDown]
        public void TearDown() => Directory.Delete(_root, true);

        void Write(string json) => File.WriteAllText(Path.Combine(_root, "Library", "PrismUnity", "prism.json"), json);

        [Test]
        public void ReadsPortOfLivePrism()
        {
            Write($"{{\"port\": 51234, \"pid\": {Process.GetCurrentProcess().Id}}}");
            Assert.AreEqual(51234, PrismEndpoint.ReadPrismPort(_root));
        }

        [Test]
        public void IgnoresEndpointOfExitedPrism()
        {
            Write("{\"port\": 51234, \"pid\": 2147483000}");
            Assert.IsNull(PrismEndpoint.ReadPrismPort(_root));
        }

        [Test]
        public void MissingOrBrokenFileIsNull()
        {
            Assert.IsNull(PrismEndpoint.ReadPrismPort(_root));
            Write("{not json");
            Assert.IsNull(PrismEndpoint.ReadPrismPort(_root));
        }
    }
}
