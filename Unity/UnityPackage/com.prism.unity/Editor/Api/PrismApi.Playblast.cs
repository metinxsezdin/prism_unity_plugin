using System;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    public static partial class PrismApi
    {
        /// <summary>
        /// Render a playblast and publish it as a Prism media version. Turntables belong to the
        /// imported asset of the first target, camera playblasts to the scene's Prism entity.
        /// Call from the main thread. Never opens a window.
        /// </summary>
        public static async Task<PlayblastResult> Playblast(PlayblastRequest req)
        {
            var ctx = await MainThreadDispatcher.Run(() => PlayblastRunner.ResolveContext(req), TimeSpan.FromSeconds(30));
            var extension = req.Format == "mp4" ? ".mp4" : ".png";
            var target = await PrismClient.SendAsync("playblastTarget", new JObject
            {
                ["entity"] = ctx.Entity.ToJson(), ["task"] = ctx.Task, ["extension"] = extension, ["comment"] = req.Comment ?? "",
            }, interactive: false, timeout: TimeSpan.FromSeconds(60));

            var result = await MainThreadDispatcher.Run(() => PlayblastRunner.Run(req, (string)target["path"]), TimeSpan.FromMinutes(10));
            result.Version = (string)target["version"];

            await PrismClient.SendAsync("playblastDone", new JObject
            {
                ["path"] = result.OutputPath, ["entity"] = ctx.Entity.ToJson(), ["task"] = ctx.Task, ["comment"] = req.Comment ?? "",
                ["details"] = new JObject
                {
                    ["mode"] = req.Mode, ["frames"] = req.Frames, ["fps"] = req.Fps,
                    ["width"] = req.Width, ["height"] = req.Height, ["format"] = req.Format,
                },
            }, interactive: false, timeout: TimeSpan.FromSeconds(60));
            return result;
        }
    }
}
