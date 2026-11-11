using System;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    /// <summary>Unity → Prism calls. Never blocks the main thread; starts Prism when needed.</summary>
    public static class PrismClient
    {
        public static readonly TimeSpan DefaultTimeout = TimeSpan.FromSeconds(10);
        public static readonly TimeSpan InteractiveTimeout = TimeSpan.FromMinutes(30);
        public static readonly TimeSpan StartupTimeout = TimeSpan.FromSeconds(60);

        /// <summary>Test hook: when set, replaces the network call (cmd, args, interactive) → result.</summary>
        public static Func<string, JObject, bool, JToken> Override;

        /// <summary>Test hook: every call's (cmd, interactive) is reported here.</summary>
        public static Action<string, bool> Observer;

        /// <summary>Call from the main thread. The returned task completes off the main thread.</summary>
        public static Task<JToken> SendAsync(string cmd, JObject args, bool interactive, TimeSpan? timeout = null)
        {
            Observer?.Invoke(cmd, interactive);
            if (Override != null)
            {
                try { return Task.FromResult(Override(cmd, args ?? new JObject(), interactive)); }
                catch (Exception e) { return Task.FromException<JToken>(e); }
            }

            LaunchContext ctx;
            try { ctx = LaunchContext.Capture(); }
            catch (Exception e) { return Task.FromException<JToken>(e); }
            var limit = timeout ?? (interactive ? InteractiveTimeout : DefaultTimeout);
            return Task.Run(() => Send(ctx, cmd, args, interactive, limit));
        }

        static JToken Send(LaunchContext ctx, string cmd, JObject args, bool interactive, TimeSpan timeout)
        {
            PrismProcess.CheckInstalled(ctx); // fails fast with prism_unavailable
            try
            {
                return Call(ctx.Session, cmd, args, interactive, timeout);
            }
            catch (Exception e) when (PrismWentAway(e))
            {
                // Nobody listens on the Prism port, or Prism died mid-call: start Prism (once) and retry.
                PrismProcess.ForgetExitedProcess();
                PrismProcess.EnsureRunning(ctx);
                WaitUntilReady(ctx);
                return Call(ctx.Session, cmd, args, interactive, timeout);
            }
        }

        /// <summary>Refused, or accepted and then reset (a Prism process that is exiting).</summary>
        static bool PrismWentAway(Exception e)
        {
            if (e is SocketException) return true;
            if (e is IOException io && io.InnerException is SocketException se)
                return se.SocketErrorCode == SocketError.ConnectionReset || se.SocketErrorCode == SocketError.ConnectionAborted;
            return false;
        }

        static void WaitUntilReady(LaunchContext ctx)
        {
            var deadline = DateTime.UtcNow + StartupTimeout;
            while (DateTime.UtcNow < deadline)
            {
                try
                {
                    Call(ctx.Session, "ping", null, false, TimeSpan.FromSeconds(5));
                    return;
                }
                catch (Exception e) when (PrismWentAway(e) || e is IOException) { }
                if (!PrismProcess.IsRunning() && PrismProcess.HasOwnedExitedWithError(out var code))
                    throw new PrismCommandException(ErrorCodes.PrismUnavailable, $"Prism exited during startup (exit code {code}).");
                Thread.Sleep(500);
            }
            throw new PrismCommandException(ErrorCodes.PrismUnavailable,
                $"Prism did not start within {StartupTimeout.TotalSeconds:0} s.");
        }

        static JToken Call(SessionInfo s, string cmd, JObject args, bool interactive, TimeSpan timeout)
        {
            var request = PrismRequest.Create(cmd, args, s.Token, interactive);
            using (var client = new TcpClient())
            {
                var connect = client.ConnectAsync("127.0.0.1", s.PrismPort);
                try
                {
                    if (!connect.Wait(TimeSpan.FromSeconds(5)) || !client.Connected)
                        throw new SocketException((int)SocketError.ConnectionRefused);
                }
                catch (AggregateException ae) when (ae.GetBaseException() is SocketException se)
                {
                    throw se; // Task.Wait wraps the refusal; callers rely on SocketException
                }
                client.ReceiveTimeout = (int)Math.Min(int.MaxValue, timeout.TotalMilliseconds);
                var stream = client.GetStream();
                var bytes = LineCodec.Encode(request);
                stream.Write(bytes, 0, bytes.Length);
                string line;
                try
                {
                    using (var reader = new StreamReader(stream, new UTF8Encoding(false)))
                        line = reader.ReadLine();
                }
                catch (IOException e) when (e.InnerException is SocketException se && se.SocketErrorCode == SocketError.TimedOut)
                {
                    throw new PrismCommandException(ErrorCodes.Timeout, $"Prism did not answer '{cmd}' within {timeout.TotalSeconds:0} s.");
                }
                if (line == null)
                    throw new PrismCommandException(ErrorCodes.PrismUnavailable, "Prism closed the connection.");
                var response = LineCodec.DecodeResponse(line);
                if (!response.Ok)
                    throw new PrismCommandException(response.Error.Code, response.Error.Message, response.Error.Details);
                return response.Result;
            }
        }
    }
}
