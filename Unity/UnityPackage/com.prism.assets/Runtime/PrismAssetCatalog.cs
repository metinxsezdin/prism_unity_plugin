using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace Prism.Assets
{
    /// <summary>
    /// Every Prism asset definition in the project, kept up to date by the Prism plugin.
    /// Addressable under the address "PrismAssetCatalog".
    /// </summary>
    public class PrismAssetCatalog : ScriptableObject
    {
        public const string Address = "PrismAssetCatalog";

        public List<PrismAssetDefinition> definitions = new List<PrismAssetDefinition>();

        /// <summary>Definitions whose entity path starts with this folder, e.g. "Props".</summary>
        public IEnumerable<PrismAssetDefinition> ByCategory(string category) =>
            definitions.Where(d => d != null && d.Category == category);

        public PrismAssetDefinition Find(string entityPath, string product) =>
            definitions.FirstOrDefault(d => d != null && d.entityPath == entityPath && d.product == product);

        /// <summary>Definitions of a team class derived from PrismAssetDefinition.</summary>
        public IEnumerable<T> OfType<T>() where T : PrismAssetDefinition => definitions.OfType<T>();
    }
}
