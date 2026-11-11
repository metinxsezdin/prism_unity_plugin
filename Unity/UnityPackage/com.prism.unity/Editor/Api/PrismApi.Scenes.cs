using System;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    public static partial class PrismApi
    {
        /// <summary>
        /// Save the active scene as a new Prism version. The first save of a scene needs entity and
        /// task (department defaults to "Unity"); later saves reuse the scene's binding.
        /// Returns {path, version}. With interactive=false no window opens: missing data fails with
        /// needs_input, a missing department with needs_confirmation (pass createDepartment).
        /// </summary>
        public static async Task<JObject> SaveVersion(string comment = "", PrismEntity entity = null, string department = null,
            string task = null, bool createDepartment = false, bool interactive = false)
        {
            var args = new JObject { ["comment"] = comment ?? "", ["createDepartment"] = createDepartment, ["_timeoutSec"] = 300 };
            if (entity != null) args["entity"] = entity.ToJson();
            if (!string.IsNullOrEmpty(department)) args["department"] = department;
            if (!string.IsNullOrEmpty(task)) args["task"] = task;
            return (JObject)await PrismClient.SendAsync("saveVersion", args, interactive, TimeSpan.FromMinutes(5));
        }

        /// <summary>
        /// Open a Prism scene version (its .unity path in the Prism project) in its working path.
        /// unsaved: "abort" | "save" | "discard". Needs no Prism call; returns {workingPath}.
        /// </summary>
        public static Task<JObject> OpenSceneVersion(string prismScenePath, string unsaved = "abort", bool confirmForeign = false) =>
            MainThreadDispatcher.Run(() => new JObject
            {
                ["workingPath"] = SceneVersioning.OpenFrom(prismScenePath, unsaved, null, confirmForeign),
            }, TimeSpan.FromMinutes(5));
    }
}
