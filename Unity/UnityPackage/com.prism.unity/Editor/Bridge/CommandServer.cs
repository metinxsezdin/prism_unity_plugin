using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// Loopback-only line server for Prism → Unity commands. Connections are read on
    /// background threads; handlers always run on the main thread through MainThreadDispatcher.
    /// </summary>
    public class CommandServer
    {
        public const double DefaultTimeoutSec = 10;
        public const double MaxTimeoutSec = 600;

        readonly string _token;
        TcpListener _listener;
        Thread _acceptThread;
        volatile bool _running;

        public int Port { get; private set; }

        public CommandServer(string token)
        {
            _token = token;
        }

        /// <summary>Listen on 127.0.0.1. Falls back to a free port when preferredPort is taken.</summary>
        public int Start(int preferredPort = 0)
        {
            try
            {
                _listener = new TcpListener(IPAddress.Loopback, preferredPort);
                _listener.Start();
            }
            catch (SocketException) when (preferredPort != 0)
            {
                _listener = new TcpListener(IPAddress.Loopback, 0);
                _listener.Start();
            }
            Port = ((IPEndPoint)_listener.LocalEndpoint).Port;
            _running = true;
            _acceptThread = new Thread(AcceptLoop) { IsBackground = true, Name = "PrismUnity.CommandServer" };
            _acceptThread.Start();
            return Port;
        }

        public void Stop()
        {
            _running = false;
            try { _listener?.Stop(); } catch (SocketException) { }
            _listener = null;
        }

        void AcceptLoop()
        {
            var listener = _listener;
            while (_running)
            {
                TcpClient client;
                try { client = listener.AcceptTcpClient(); }
                catch (SocketException) { return; }
                catch (ObjectDisposedException) { return; }
                new Thread(() => Serve(client)) { IsBackground = true, Name = "PrismUnity.Connection" }.Start();
            }
        }

        void Serve(TcpClient client)
        {
            using (client)
            {
                try
                {
                    var stream = client.GetStream();
                    var reader = new StreamReader(stream, new UTF8Encoding(false));
                    string line;
                    while ((line = reader.ReadLine()) != null)
                    {
                        if (line.Trim().Length == 0) continue;
                        var bytes = LineCodec.Encode(Respond(line));
                        stream.Write(bytes, 0, bytes.Length);
                    }
                }
                catch (IOException) { }
                catch (ObjectDisposedException) { }
            }
        }

        PrismResponse Respond(string line)
        {
            PrismRequest req;
            try { req = LineCodec.DecodeRequest(line); }
            catch (PrismCommandException e) { return PrismResponse.Failure(null, e); }

            if (!TokenMatches(req.Token))
                return PrismResponse.Failure(req.Id, ErrorCodes.BadToken, "Invalid session token.");
            if (!CommandRegistry.TryGet(req.Cmd, out var handler, out var mutates))
                return PrismResponse.Failure(req.Id, ErrorCodes.UnknownCommand, $"Unknown command: {req.Cmd}");
            if (mutates && PrismSession.IsPlaying())
                return PrismResponse.Failure(req.Id, ErrorCodes.UnityBusy, "Unity is in Play Mode; leave Play Mode and try again.");

            var args = req.Args ?? new JObject();
            var timeout = TimeSpan.FromSeconds(Math.Min(MaxTimeoutSec, (double?)args["_timeoutSec"] ?? DefaultTimeoutSec));
            foreach (var p in new System.Collections.Generic.List<JProperty>(args.Properties()))
                if (p.Name.StartsWith("_")) p.Remove();

            var ctx = new CommandContext { Interactive = req.Interactive };
            try
            {
                var result = MainThreadDispatcher.Run(() => handler(args, ctx), timeout).GetAwaiter().GetResult();
                return PrismResponse.Success(req.Id, result);
            }
            catch (PrismCommandException e) { return PrismResponse.Failure(req.Id, e); }
            catch (TimeoutException e) { return PrismResponse.Failure(req.Id, ErrorCodes.Timeout, e.Message); }
            catch (Exception e)
            {
                Debug.LogException(e);
                return PrismResponse.Failure(req.Id, ErrorCodes.Internal, $"{e.GetType().Name}: {e.Message}");
            }
        }

        bool TokenMatches(string candidate)
        {
            if (candidate == null) return false;
            var a = Encoding.UTF8.GetBytes(candidate);
            var b = Encoding.UTF8.GetBytes(_token);
            var diff = a.Length ^ b.Length;
            for (var i = 0; i < Math.Min(a.Length, b.Length); i++)
                diff |= a[i] ^ b[i];
            return diff == 0;
        }
    }
}
