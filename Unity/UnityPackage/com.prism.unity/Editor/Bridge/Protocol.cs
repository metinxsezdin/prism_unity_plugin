using System;
using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    /// <summary>Error codes shared with the Python side (unity_bridge/protocol.py).</summary>
    public static class ErrorCodes
    {
        public const string UnknownCommand = "unknown_command";
        public const string BadToken = "bad_token";
        public const string BadRequest = "bad_request";
        public const string BadArgs = "bad_args";
        public const string NeedsInput = "needs_input";
        public const string NeedsConfirmation = "needs_confirmation";
        public const string PrismUnavailable = "prism_unavailable";
        public const string UnityBusy = "unity_busy";
        public const string MissingPackage = "missing_package";
        public const string SourceUnavailable = "source_unavailable";
        public const string Timeout = "timeout";
        public const string Internal = "internal";

        public static readonly IReadOnlyCollection<string> All = new[]
        {
            UnknownCommand, BadToken, BadRequest, BadArgs, NeedsInput, NeedsConfirmation,
            PrismUnavailable, UnityBusy, MissingPackage, SourceUnavailable, Timeout, Internal
        };

        public static bool IsKnown(string code) => code != null && ((ICollection<string>)All).Contains(code);
    }

    /// <summary>An error that travels over the bridge as {code, message, details}.</summary>
    public class PrismCommandException : Exception
    {
        public string Code { get; }
        public JObject Details { get; }

        public PrismCommandException(string code, string message, JObject details = null) : base(message)
        {
            Code = ErrorCodes.IsKnown(code) ? code : ErrorCodes.Internal;
            Details = details ?? new JObject();
        }

        public PrismError ToError() => new PrismError { Code = Code, Message = Message, Details = Details };
    }

    public class PrismError
    {
        [JsonProperty("code")] public string Code;
        [JsonProperty("message")] public string Message;
        [JsonProperty("details")] public JObject Details = new JObject();
    }

    public class PrismRequest
    {
        public const int ProtocolVersion = 1;

        [JsonProperty("v")] public int V = ProtocolVersion;
        [JsonProperty("id")] public string Id;
        [JsonProperty("token")] public string Token;
        [JsonProperty("cmd")] public string Cmd;
        [JsonProperty("args")] public JObject Args = new JObject();
        [JsonProperty("interactive")] public bool Interactive;

        public static PrismRequest Create(string cmd, JObject args, string token, bool interactive) => new PrismRequest
        {
            Id = Guid.NewGuid().ToString("N"),
            Token = token,
            Cmd = cmd,
            Args = args ?? new JObject(),
            Interactive = interactive,
        };
    }

    public class PrismResponse
    {
        [JsonProperty("v")] public int V = PrismRequest.ProtocolVersion;
        [JsonProperty("id")] public string Id;
        [JsonProperty("ok")] public bool Ok;
        [JsonProperty("result", NullValueHandling = NullValueHandling.Ignore)] public JToken Result;
        [JsonProperty("error", NullValueHandling = NullValueHandling.Ignore)] public PrismError Error;

        public static PrismResponse Success(string id, object result) => new PrismResponse
        {
            Id = id,
            Ok = true,
            Result = result == null ? JValue.CreateNull() : JToken.FromObject(result),
        };

        public static PrismResponse Failure(string id, string code, string message, JObject details = null) => new PrismResponse
        {
            Id = id,
            Ok = false,
            Error = new PrismError { Code = ErrorCodes.IsKnown(code) ? code : ErrorCodes.Internal, Message = message, Details = details ?? new JObject() },
        };

        public static PrismResponse Failure(string id, PrismCommandException e) => Failure(id, e.Code, e.Message, e.Details);
    }

    /// <summary>One UTF-8 JSON object per line.</summary>
    public static class LineCodec
    {
        static readonly JsonSerializerSettings Settings = new JsonSerializerSettings
        {
            Formatting = Formatting.None,
            StringEscapeHandling = StringEscapeHandling.Default,
        };

        public static byte[] Encode(object msg) => Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(msg, Settings) + "\n");

        public static PrismRequest DecodeRequest(string line)
        {
            var obj = Parse(line);
            if (obj["cmd"]?.Type != JTokenType.String)
                throw new PrismCommandException(ErrorCodes.BadRequest, "Request has no command.");
            return obj.ToObject<PrismRequest>();
        }

        public static PrismResponse DecodeResponse(string line)
        {
            var obj = Parse(line);
            if (obj["ok"]?.Type != JTokenType.Boolean)
                throw new PrismCommandException(ErrorCodes.BadRequest, "Response has no 'ok' field.");
            return obj.ToObject<PrismResponse>();
        }

        static JObject Parse(string line)
        {
            JObject obj;
            try
            {
                obj = JObject.Parse(line);
            }
            catch (JsonException)
            {
                throw new PrismCommandException(ErrorCodes.BadRequest, "Message is not valid JSON.");
            }
            if ((int?)obj["v"] != PrismRequest.ProtocolVersion)
                throw new PrismCommandException(ErrorCodes.BadRequest, "Unsupported protocol version.");
            return obj;
        }
    }
}
