using System.Collections;
using NUnit.Framework;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests.E2E
{
    /// <summary>
    /// Needs a real Prism: tools/deploy_dev.ps1 run once, and ProjectSettings/PrismUnity/project.json
    /// pointing at the test Prism project (tools/make_test_prism_project.py).
    /// Run with: tools/run_unity_tests.ps1 -Category E2E
    /// </summary>
    [Category("E2E")]
    public class BridgeE2ETests
    {
        [TearDown]
        public void TearDown() => PrismProcess.StopOwnedProcess();

        [UnityTest]
        public IEnumerator PingRealPrism()
        {
            var task = PrismClient.SendAsync("ping", null, interactive: false, timeout: System.TimeSpan.FromSeconds(30));
            yield return Support.E2EWait.For(task, 120);
            var result = task.Result;
            StringAssert.StartsWith("v2.", (string)result["prismVersion"]);
            Assert.IsNotNull(result["checkImportVersions"]);
        }
    }
}
