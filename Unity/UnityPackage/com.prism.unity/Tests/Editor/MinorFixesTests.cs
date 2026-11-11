using System.Collections;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>Regression tests for the minor findings of the final review.</summary>
    public class MinorFixesTests
    {
        CommandServer _server;
        ImportFixture _fx;

        [SetUp]
        public void SetUp()
        {
            CommandRegistry.Register("test.ping", (a, c) => "pong", false);
            _server = new CommandServer("tok");
            _server.Start();
            _fx = new ImportFixture();
        }

        [TearDown]
        public void TearDown()
        {
            _server.Stop();
            CommandRegistry.Unregister("test.ping");
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            _fx.Cleanup();
        }

        // --- malformed requests -------------------------------------------------

        [UnityTest]
        public IEnumerator WrongTypedVersionIsBadRequestAndServerKeepsRunning()
        {
            var raw = BridgeTestClient.SendRaw(_server.Port, "{\"v\":\"x\",\"id\":\"1\",\"token\":\"tok\",\"cmd\":\"test.ping\"}");
            yield return BridgeTestClient.Wait(raw);
            Assert.AreEqual(ErrorCodes.BadRequest, LineCodec.DecodeResponse(raw.Result).Error.Code);

            var ok = BridgeTestClient.Send(_server.Port, PrismRequest.Create("test.ping", null, "tok", false));
            yield return BridgeTestClient.Wait(ok);
            Assert.IsTrue(ok.Result.Ok);
        }

        [UnityTest]
        public IEnumerator ArrayArgsIsBadRequest()
        {
            var raw = BridgeTestClient.SendRaw(_server.Port, "{\"v\":1,\"id\":\"1\",\"token\":\"tok\",\"cmd\":\"test.ping\",\"args\":[1]}");
            yield return BridgeTestClient.Wait(raw);
            Assert.AreEqual(ErrorCodes.BadRequest, LineCodec.DecodeResponse(raw.Result).Error.Code);
        }

        // --- prism_list_cameras off the main thread ------------------------------

        [UnityTest]
        public IEnumerator ListCamerasWorksWhenCalledFromABackgroundThread()
        {
            new GameObject("ShotCam").AddComponent<Camera>();
            var task = Task.Run(() => PrismMcpTools.Invoke("prism_list_cameras", new JObject()));
            for (var i = 0; i < 300 && !task.IsCompleted; i++) yield return null;
            Assert.IsTrue(task.IsCompleted);
            var result = task.Result;
            Assert.IsTrue((bool)result["ok"], result.ToString());
            Assert.AreEqual("ShotCam", (string)result["result"][0]["name"]);
        }

        // --- file format change between versions ---------------------------------

        string WriteObjVersion(string version)
        {
            var dir = Path.Combine(_fx.SourceDir, version);
            Directory.CreateDirectory(dir);
            var obj = Path.Combine(dir, "lotus.obj");
            File.WriteAllText(obj, "o Lotus\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n");
            return obj;
        }

        [Test]
        public void FormatChangeNeedsConfirmation()
        {
            ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v1.fbx", "v0001"), false);
            var obj = new ResolvedVersion { Version = "v0002", FilePath = WriteObjVersion("v0002"), Location = "global" };

            var ex = Assert.Throws<PrismCommandException>(() =>
                ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, obj, false));
            Assert.AreEqual(ErrorCodes.NeedsConfirmation, ex.Code);
            Assert.AreEqual("format_changed", (string)ex.Details["reason"]);
            Assert.AreEqual(".fbx", (string)ex.Details["from"]);
            Assert.AreEqual(".obj", (string)ex.Details["to"]);
            Assert.AreEqual("v0001", ImportRecord.Load("Props__Lotus__lotus_model").Version);
        }

        [Test]
        public void ConfirmedFormatChangeImportsTheNewAssetAndSaysSo()
        {
            ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v1.fbx", "v0001"), false);
            var obj = new ResolvedVersion { Version = "v0002", FilePath = WriteObjVersion("v0002"), Location = "global" };
            var result = ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, obj, true);
            Assert.AreEqual("Assets/Prism/Props/Lotus/lotus_model/lotus_model.obj", result.Record.AssetPath);
            Assert.IsFalse(result.Updated, "a new asset was created; references still point at the old one");
        }

        // --- one broken record must not break the rest ---------------------------

        [Test]
        public void MalformedRecordIsSkipped()
        {
            ProductImporter.ImportResolved(ImportFixture.Lotus, ImportFixture.LotusProduct, _fx.Version("lotus_v1.fbx", "v0001"), false);
            File.WriteAllText(Path.Combine(ImportRecord.Folder, "Props__Broken__x.json"), "<<<<<<< HEAD\n{\n=======\n}\n>>>>>>> theirs\n");
            LogAssert.Expect(LogType.Warning, new Regex("Props__Broken__x.json"));
            var all = ImportRecord.LoadAll();
            Assert.AreEqual(1, all.Count);
            Assert.AreEqual("Props__Lotus__lotus_model", all[0].Id);
        }

        // --- launcher exit codes ------------------------------------------------------

        [Test]
        public void UnreachableProjectExitCodeHasAClearMessage()
        {
            StringAssert.Contains("Prism project", PrismProcess.ExitMessage(3));
            StringAssert.Contains("exit code 7", PrismProcess.ExitMessage(7));
        }

        // --- camera aspect after a capture ---------------------------------------------

        [Test]
        public void CaptureLeavesCameraAspectFollowingItsTarget()
        {
            var cam = new GameObject("Cam").AddComponent<Camera>();
            FrameCapture.CaptureFrame(cam, 512, 256, Path.Combine(_fx.SourceDir, "f.png"));
            var rt = new RenderTexture(100, 400, 16);
            try
            {
                cam.targetTexture = rt;
                Assert.AreEqual(0.25f, cam.aspect, 0.01f, "the camera aspect stayed locked after the capture");
            }
            finally
            {
                cam.targetTexture = null;
                Object.DestroyImmediate(rt);
            }
        }

        [Test]
        public void CaptureKeepsAManuallySetAspect()
        {
            var cam = new GameObject("Cam").AddComponent<Camera>();
            cam.aspect = 3f;
            FrameCapture.CaptureFrame(cam, 64, 64, Path.Combine(_fx.SourceDir, "g.png"));
            Assert.AreEqual(3f, cam.aspect, 0.001f);
        }

        // --- Prism windows in front --------------------------------------------------------

        [Test]
        public void PrismEndpointReportsPid()
        {
            var root = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "ep2", Path.GetRandomFileName());
            Directory.CreateDirectory(Path.Combine(root, "Library", "PrismUnity"));
            try
            {
                var pid = System.Diagnostics.Process.GetCurrentProcess().Id;
                File.WriteAllText(Path.Combine(root, "Library", "PrismUnity", "prism.json"), $"{{\"port\": 5, \"pid\": {pid}}}");
                Assert.AreEqual(pid, PrismEndpoint.ReadPrismPid(root));
            }
            finally
            {
                Directory.Delete(root, true);
            }
        }
    }
}
