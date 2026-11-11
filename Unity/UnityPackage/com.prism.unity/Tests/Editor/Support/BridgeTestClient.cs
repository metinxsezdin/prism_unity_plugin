using System;
using System.Collections;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;
using NUnit.Framework;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>Talks to a CommandServer from a background task so the main thread keeps pumping.</summary>
    internal static class BridgeTestClient
    {
        public static Task<PrismResponse> Send(int port, PrismRequest request) => Task.Run(() =>
        {
            using (var client = new TcpClient())
            {
                client.Connect("127.0.0.1", port);
                var stream = client.GetStream();
                var bytes = LineCodec.Encode(request);
                stream.Write(bytes, 0, bytes.Length);
                using (var reader = new StreamReader(stream, new UTF8Encoding(false)))
                    return LineCodec.DecodeResponse(reader.ReadLine());
            }
        });

        public static Task<string> SendRaw(int port, string line) => Task.Run(() =>
        {
            using (var client = new TcpClient())
            {
                client.Connect("127.0.0.1", port);
                var stream = client.GetStream();
                var bytes = Encoding.UTF8.GetBytes(line + "\n");
                stream.Write(bytes, 0, bytes.Length);
                using (var reader = new StreamReader(stream, new UTF8Encoding(false)))
                    return reader.ReadLine();
            }
        });

        /// <summary>Yield inside a [UnityTest] until the task finishes (fails after the timeout).</summary>
        public static IEnumerator Wait(Task task, double timeoutSec = 15)
        {
            var deadline = DateTime.UtcNow.AddSeconds(timeoutSec);
            while (!task.IsCompleted)
            {
                if (DateTime.UtcNow > deadline)
                    Assert.Fail("Timed out waiting for bridge response.");
                yield return null;
            }
            if (task.IsFaulted)
                throw task.Exception.GetBaseException();
        }
    }
}
