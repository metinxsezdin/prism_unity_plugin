using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    public delegate JToken CommandHandler(JObject args, CommandContext ctx);

    public class CommandContext
    {
        /// <summary>False when the call came from Claude: the handler must not open any window.</summary>
        public bool Interactive;
    }

    /// <summary>The fixed set of commands Prism may call. Nothing outside this table can run.</summary>
    public static class CommandRegistry
    {
        struct Entry
        {
            public CommandHandler Handler;
            public bool MutatesProject;
        }

        static readonly Dictionary<string, Entry> Commands = new Dictionary<string, Entry>();
        static readonly object Lock = new object();

        public static void Register(string cmd, CommandHandler h, bool mutatesProject)
        {
            lock (Lock) Commands[cmd] = new Entry { Handler = h, MutatesProject = mutatesProject };
        }

        public static void Unregister(string cmd)
        {
            lock (Lock) Commands.Remove(cmd);
        }

        public static bool TryGet(string cmd, out CommandHandler h, out bool mutatesProject)
        {
            lock (Lock)
            {
                if (cmd != null && Commands.TryGetValue(cmd, out var e))
                {
                    h = e.Handler;
                    mutatesProject = e.MutatesProject;
                    return true;
                }
            }
            h = null;
            mutatesProject = false;
            return false;
        }
    }
}
