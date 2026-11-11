using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests
{
    public class CommandServerTests
    {
        const string Token = "test-token";
        CommandServer _server;
        int _mainThreadId;

        [SetUp]
        public void SetUp()
        {
            _mainThreadId = Thread.CurrentThread.ManagedThreadId;
            CommandRegistry.Register("test.ping", (a, c) => "pong", mutatesProject: false);
            CommandRegistry.Register("test.thread", (a, c) => Thread.CurrentThread.ManagedThreadId, mutatesProject: false);
            CommandRegistry.Register("test.mutate", (a, c) => true, mutatesProject: true);
            CommandRegistry.Register("test.needsInput", (a, c) =>
                throw new PrismCommandException(ErrorCodes.NeedsInput, "Pick a task", new JObject { ["missing"] = new JArray("task") }), false);
            CommandRegistry.Register("test.echoArgs", (a, c) => a, false);
            CommandRegistry.Register("test.interactive", (a, c) => c.Interactive, false);
            CommandRegistry.Register("test.slow", (a, c) => { Thread.Sleep(1000); return true; }, false);
            _server = new CommandServer(Token);
            _server.Start();
        }

        [TearDown]
        public void TearDown()
        {
            _server.Stop();
            foreach (var cmd in new[] { "test.ping", "test.thread", "test.mutate", "test.needsInput", "test.echoArgs", "test.interactive", "test.slow" })
                CommandRegistry.Unregister(cmd);
            PrismSession.PlayModeOverride = null;
        }

        PrismRequest Req(string cmd, JObject args = null, string token = Token, bool interactive = false) =>
            PrismRequest.Create(cmd, args, token, interactive);

        [UnityTest]
        public IEnumerator PingCommandRespondsOk()
        {
            var t = BridgeTestClient.Send(_server.Port, Req("test.ping"));
            yield return BridgeTestClient.Wait(t);
            Assert.IsTrue(t.Result.Ok);
            Assert.AreEqual("pong", (string)t.Result.Result);
        }

        [UnityTest]
        public IEnumerator RejectsWrongToken()
        {
            var t = BridgeTestClient.Send(_server.Port, Req("test.ping", token: "wrong"));
            yield return BridgeTestClient.Wait(t);
            Assert.IsFalse(t.Result.Ok);
            Assert.AreEqual(ErrorCodes.BadToken, t.Result.Error.Code);
        }

        [UnityTest]
        public IEnumerator RejectsUnknownCommand()
        {
            var t = BridgeTestClient.Send(_server.Port, Req("System.Diagnostics.Process.Start"));
            yield return BridgeTestClient.Wait(t);
            Assert.AreEqual(ErrorCodes.UnknownCommand, t.Result.Error.Code);
        }

        [UnityTest]
        public IEnumerator RejectsGarbageAndKeepsRunning()
        {
            var raw = BridgeTestClient.SendRaw(_server.Port, "not json");
            yield return BridgeTestClient.Wait(raw);
            Assert.AreEqual(ErrorCodes.BadRequest, LineCodec.DecodeResponse(raw.Result).Error.Code);
            var t = BridgeTestClient.Send(_server.Port, Req("test.ping"));
            yield return BridgeTestClient.Wait(t);
            Assert.IsTrue(t.Result.Ok);
        }

        [UnityTest]
        public IEnumerator HandlerRunsOnMainThread()
        {
            var t = BridgeTestClient.Send(_server.Port, Req("test.thread"));
            yield return BridgeTestClient.Wait(t);
            Assert.AreEqual(_mainThreadId, (int)t.Result.Result);
        }

        [UnityTest]
        public IEnumerator PassesInteractiveFlagAndStripsPrivateArgs()
        {
            var t = BridgeTestClient.Send(_server.Port, Req("test.echoArgs", new JObject { ["a"] = 1, ["_timeoutSec"] = 5 }));
            yield return BridgeTestClient.Wait(t);
            var args = (JObject)t.Result.Result;
            Assert.AreEqual(1, (int)args["a"]);
            Assert.IsNull(args["_timeoutSec"]);

            var i = BridgeTestClient.Send(_server.Port, Req("test.interactive", interactive: true));
            yield return BridgeTestClient.Wait(i);
            Assert.IsTrue((bool)i.Result.Result);
        }

        [UnityTest]
        public IEnumerator ListensOnLoopbackOnly()
        {
            var lan = Dns.GetHostAddresses(Dns.GetHostName())
                .FirstOrDefault(a => a.AddressFamily == AddressFamily.InterNetwork && !IPAddress.IsLoopback(a));
            if (lan == null)
                Assert.Ignore("No non-loopback IPv4 address on this machine.");
            var client = new TcpClient();
            var connect = client.ConnectAsync(lan, _server.Port);
            var deadline = DateTime.UtcNow.AddSeconds(5);
            while (!connect.IsCompleted && DateTime.UtcNow < deadline)
                yield return null;
            Assert.IsFalse(connect.Status == System.Threading.Tasks.TaskStatus.RanToCompletion && client.Connected,
                "Server accepted a connection on a non-loopback address.");
            client.Close();
        }

        [UnityTest]
        public IEnumerator MutatingCommandRejectedInPlayMode()
        {
            PrismSession.PlayModeOverride = true;
            var t = BridgeTestClient.Send(_server.Port, Req("test.mutate"));
            yield return BridgeTestClient.Wait(t);
            Assert.AreEqual(ErrorCodes.UnityBusy, t.Result.Error.Code);

            var ro = BridgeTestClient.Send(_server.Port, Req("test.ping"));
            yield return BridgeTestClient.Wait(ro);
            Assert.IsTrue(ro.Result.Ok, "Read-only commands still work in Play Mode.");
        }

        [UnityTest]
        public IEnumerator MutatingCommandRunsWhenNotPlaying()
        {
            PrismSession.PlayModeOverride = null; // the real Play Mode check must run on the main thread
            var t = BridgeTestClient.Send(_server.Port, Req("test.mutate"));
            yield return BridgeTestClient.Wait(t);
            Assert.IsTrue(t.Result.Ok, t.Result.Error?.Message);
        }

        [UnityTest]
        public IEnumerator HandlerExceptionBecomesError()
        {
            var t = BridgeTestClient.Send(_server.Port, Req("test.needsInput"));
            yield return BridgeTestClient.Wait(t);
            Assert.AreEqual(ErrorCodes.NeedsInput, t.Result.Error.Code);
            Assert.AreEqual("task", (string)t.Result.Error.Details["missing"][0]);

            var again = BridgeTestClient.Send(_server.Port, Req("test.ping"));
            yield return BridgeTestClient.Wait(again);
            Assert.IsTrue(again.Result.Ok);
        }

        [UnityTest]
        public IEnumerator SlowHandlerTimesOut()
        {
            var t = BridgeTestClient.Send(_server.Port, Req("test.slow", new JObject { ["_timeoutSec"] = 0.2 }));
            yield return BridgeTestClient.Wait(t);
            Assert.AreEqual(ErrorCodes.Timeout, t.Result.Error.Code);
        }
    }

    public class PrismSessionTests
    {
        [SetUp]
        public void SetUp() => PrismSession.Shutdown();

        [TearDown]
        public void TearDown() => PrismSession.Shutdown();

        [Test]
        public void SessionFileRoundTrip()
        {
            var s = PrismSession.EnsureStarted();
            Assert.IsTrue(File.Exists(PrismSession.SessionFilePath));
            var json = JObject.Parse(File.ReadAllText(PrismSession.SessionFilePath));
            Assert.AreEqual(s.UnityPort, (int)json["unityPort"]);
            Assert.AreEqual(s.PrismPort, (int)json["prismPort"]);
            Assert.AreEqual(s.Token, (string)json["token"]);
            Assert.AreEqual(System.Diagnostics.Process.GetCurrentProcess().Id, (int)json["unityPid"]);
            Assert.AreNotEqual(s.UnityPort, s.PrismPort);
            Assert.GreaterOrEqual(s.Token.Length, 32);
        }

        [Test]
        public void RestartAfterReloadReusesPortAndToken()
        {
            var first = PrismSession.EnsureStarted();
            PrismSession.Shutdown();   // what beforeAssemblyReload does
            var second = PrismSession.EnsureStarted();
            Assert.AreEqual(first.UnityPort, second.UnityPort);
            Assert.AreEqual(first.PrismPort, second.PrismPort);
            Assert.AreEqual(first.Token, second.Token);
        }

        [Test]
        public void StaleSessionFromOtherProcessGetsNewToken()
        {
            Directory.CreateDirectory(Path.GetDirectoryName(PrismSession.SessionFilePath));
            File.WriteAllText(PrismSession.SessionFilePath,
                "{\"unityPort\":1,\"prismPort\":2,\"token\":\"old\",\"unityPid\":-5}");
            var s = PrismSession.EnsureStarted();
            Assert.AreNotEqual("old", s.Token);
            Assert.AreNotEqual(1, s.UnityPort);
        }
    }
}
