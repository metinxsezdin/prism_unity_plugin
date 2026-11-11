using System;
using System.Collections;
using NUnit.Framework;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests
{
    public class PrismProcessTests
    {
        string _savedRoot;

        [SetUp]
        public void SetUp() => _savedRoot = PrismSettings.PrismRoot;

        [TearDown]
        public void TearDown() => PrismSettings.PrismRoot = _savedRoot;

        [Test]
        public void StartInfoHasEnvAndArgs()
        {
            var session = new SessionInfo { UnityPort = 50001, PrismPort = 50002, Token = "tok", UnityPid = 4242 };
            var binding = new ProjectBinding { PrismProjectConfig = "M:/Wellness App/00_Pipeline/pipeline.json" };
            var psi = PrismProcess.BuildStartInfo(session, binding, @"C:\Program Files\Prism2",
                @"C:\Dev Folder\prism_unity_plugin\Unity", @"C:\Projects\Wellness Unity", "launch");

            StringAssert.EndsWith(@"\Python313\python.exe", psi.FileName);
            StringAssert.StartsWith(@"C:\Program Files\Prism2", psi.FileName);
            StringAssert.Contains("\"C:\\Dev Folder\\prism_unity_plugin\\Unity\\Scripts\\Prism_Unity_Launcher.py\"", psi.Arguments);
            StringAssert.EndsWith(" launch", psi.Arguments);
            Assert.IsFalse(psi.UseShellExecute);
            Assert.IsTrue(psi.CreateNoWindow);

            Assert.AreEqual("50001", psi.EnvironmentVariables["PRISM_UNITY_PORT"]);
            Assert.AreEqual("50002", psi.EnvironmentVariables["PRISM_UNITY_PRISM_PORT"]);
            Assert.AreEqual("tok", psi.EnvironmentVariables["PRISM_UNITY_TOKEN"]);
            Assert.AreEqual("4242", psi.EnvironmentVariables["PRISM_UNITY_PID"]);
            Assert.AreEqual(@"C:\Projects\Wellness Unity", psi.EnvironmentVariables["PRISM_UNITY_PROJECT"]);
            Assert.AreEqual("M:/Wellness App/00_Pipeline/pipeline.json", psi.EnvironmentVariables["PRISM_UNITY_PRISM_PROJECT"]);
            Assert.AreEqual(@"C:\Program Files\Prism2", psi.EnvironmentVariables["PRISM_ROOT"]);
        }

        [Test]
        public void StartInfoWithoutBindingLeavesProjectEmpty()
        {
            var session = new SessionInfo { UnityPort = 1, PrismPort = 2, Token = "t", UnityPid = 3 };
            var psi = PrismProcess.BuildStartInfo(session, null, @"C:\P", @"C:\U", @"C:\Proj", "launch");
            Assert.AreEqual("", psi.EnvironmentVariables["PRISM_UNITY_PRISM_PROJECT"]);
        }

        [UnityTest]
        public IEnumerator SendAsyncFailsFastWhenPrismMissing()
        {
            PrismSettings.PrismRoot = @"C:\does\not\exist\Prism2";
            PrismProcess.ForgetRunningProcess();
            var started = DateTime.UtcNow;
            var frames = 0;
            var task = PrismClient.SendAsync("ping", null, interactive: false);
            while (!task.IsCompleted && (DateTime.UtcNow - started).TotalSeconds < 10)
            {
                frames++;
                yield return null;
            }
            Assert.IsTrue(task.IsFaulted, "Expected the call to fail.");
            var ex = task.Exception.GetBaseException() as PrismCommandException;
            Assert.IsNotNull(ex, task.Exception.ToString());
            Assert.AreEqual(ErrorCodes.PrismUnavailable, ex.Code);
            StringAssert.Contains("does\\not\\exist", ex.Message);
            Assert.Less((DateTime.UtcNow - started).TotalSeconds, 2.0);
        }

        [Test]
        public void ProjectBindingRoundTrip()
        {
            var backup = ProjectBinding.Load();
            try
            {
                new ProjectBinding { PrismProjectConfig = "M:/X/00_Pipeline/pipeline.json" }.Save();
                Assert.AreEqual("M:/X/00_Pipeline/pipeline.json", ProjectBinding.Load().PrismProjectConfig);
            }
            finally
            {
                if (backup != null) backup.Save();
                else ProjectBinding.Delete();
            }
        }

        [Test]
        public void PrismEntityJsonUsesPrismKeys()
        {
            var asset = new PrismEntity { Type = "asset", AssetPath = "Props/Çay Bardağı" };
            var json = asset.ToJson();
            Assert.AreEqual("asset", (string)json["type"]);
            Assert.AreEqual("Props/Çay Bardağı", (string)json["asset_path"]);
            Assert.IsNull(json["shot"]);

            var shot = PrismEntity.FromJson(new Newtonsoft.Json.Linq.JObject { ["type"] = "shot", ["sequence"] = "sq01", ["shot"] = "sh010" });
            Assert.AreEqual("sq01", shot.Sequence);
            Assert.AreEqual("sh010", shot.Shot);
        }

        [Test]
        public void SessionCommandsAreRegistered()
        {
            foreach (var cmd in new[] { "getPid", "getAppVersion", "getProjectInfo", "getFrameRange", "setFrameRange", "getFPS", "setFPS" })
                Assert.IsTrue(CommandRegistry.TryGet(cmd, out _, out _), cmd);
        }

        [Test]
        public void FrameRangeAndFpsRoundTrip()
        {
            CommandRegistry.TryGet("setFrameRange", out var setRange, out _);
            CommandRegistry.TryGet("getFrameRange", out var getRange, out _);
            CommandRegistry.TryGet("setFPS", out var setFps, out _);
            CommandRegistry.TryGet("getFPS", out var getFps, out _);
            var ctx = new CommandContext();
            setRange(new Newtonsoft.Json.Linq.JObject { ["start"] = 10, ["end"] = 50 }, ctx);
            var r = getRange(new Newtonsoft.Json.Linq.JObject(), ctx);
            Assert.AreEqual(10, (int)r["start"]);
            Assert.AreEqual(50, (int)r["end"]);
            setFps(new Newtonsoft.Json.Linq.JObject { ["fps"] = 24 }, ctx);
            Assert.AreEqual(24, (int)getFps(new Newtonsoft.Json.Linq.JObject(), ctx));
        }
    }
}
