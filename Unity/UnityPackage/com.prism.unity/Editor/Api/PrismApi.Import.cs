using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace Prism.Unity.Editor
{
    public static partial class PrismApi
    {
        static readonly TimeSpan ImportTimeout = TimeSpan.FromMinutes(10);

        /// <summary>
        /// Resolve a product version in Prism, then import it into Assets/Prism. Never opens a window:
        /// a breaking update fails with needs_confirmation (details = the diff) unless confirm is true.
        /// Call from the main thread.
        /// </summary>
        public static async Task<ImportResult> ImportProduct(PrismEntity entity, string product, string version = "latest", bool confirm = false)
        {
            EnsureEditable();
            var resolved = await Resolve(entity, product, version);
            return await MainThreadDispatcher.Run(() =>
            {
                EnsureEditable();
                return ProductImporter.ImportResolved(entity, product, resolved, confirm);
            }, ImportTimeout);
        }

        /// <summary>Update an imported product (by its record id) to another version, "latest" by default.</summary>
        public static async Task<ImportResult> UpdateProduct(string recordId, string version = "latest", bool confirm = false)
        {
            EnsureEditable();
            var record = RequireRecord(recordId);
            var resolved = await Resolve(record.Entity, record.Product, version);
            return await MainThreadDispatcher.Run(() =>
            {
                EnsureEditable();
                return ProductImporter.ImportResolved(record.Entity, record.Product, resolved, confirm);
            }, ImportTimeout);
        }

        public static IReadOnlyList<ImportRecord> ListImported() => ImportRecord.LoadAll();

        /// <summary>
        /// Raised on the main thread after a check with (record ids whose product no longer exists in Prism,
        /// record ids whose product exists). The packaging assembly sets or clears their definitions'
        /// prismMissing flag; nothing is ever deleted. Records Prism could not reach are in neither list.
        /// </summary>
        public static event Action<IReadOnlyList<string>, IReadOnlyList<string>> AvailabilityReported;

        /// <summary>
        /// Imported products that have a newer version in Prism: [{id, current, latest, entity, product}],
        /// plus [{id, missing: true, entity, product}] for products that disappeared from Prism.
        /// </summary>
        public static async Task<JArray> CheckForUpdates()
        {
            var records = JArray.FromObject(ListImported());
            if (records.Count == 0) return new JArray();
            var answer = (JArray)await PrismClient.SendAsync("checkVersions", new JObject { ["records"] = records, ["includePresent"] = true },
                interactive: false, timeout: TimeSpan.FromSeconds(60));
            var entries = answer.OfType<JObject>().ToList();
            List<string> Ids(Func<JObject, bool> which) =>
                entries.Where(which).Select(e => (string)e["id"]).Where(id => !string.IsNullOrEmpty(id)).ToList();
            var missing = Ids(e => (bool?)e["missing"] == true);
            var present = Ids(e => (bool?)e["present"] == true);
            if ((missing.Count > 0 || present.Count > 0) && AvailabilityReported != null)
                await MainThreadDispatcher.Run(() =>
                {
                    try { AvailabilityReported?.Invoke(missing, present); }
                    catch (Exception e) { UnityEngine.Debug.LogException(e); }
                    return true;
                }, TimeSpan.FromSeconds(60));
            return new JArray(entries.Where(e => (bool?)e["present"] != true));
        }

        public static async Task<JArray> ListProducts(PrismEntity entity) =>
            (JArray)await PrismClient.SendAsync("listProducts", new JObject { ["entity"] = entity.ToJson() }, interactive: false);

        public static async Task<JArray> ListVersions(PrismEntity entity, string product) =>
            (JArray)await PrismClient.SendAsync("listVersions",
                new JObject { ["entity"] = entity.ToJson(), ["product"] = product }, interactive: false);

        static async Task<ResolvedVersion> Resolve(PrismEntity entity, string product, string version)
        {
            var result = await PrismClient.SendAsync("resolveVersion",
                new JObject { ["entity"] = entity.ToJson(), ["product"] = product, ["version"] = version ?? "latest" },
                interactive: false, timeout: TimeSpan.FromSeconds(60));
            return result.ToObject<ResolvedVersion>();
        }

        internal static ImportRecord RequireRecord(string recordId)
        {
            var record = string.IsNullOrEmpty(recordId) ? null : ImportRecord.Load(recordId);
            if (record == null)
                throw new PrismCommandException(ErrorCodes.BadArgs, $"No imported Prism product with id '{recordId}'. Known: " +
                    string.Join(", ", ImportRecord.LoadAll().Select(r => r.Id)));
            return record;
        }
    }
}
