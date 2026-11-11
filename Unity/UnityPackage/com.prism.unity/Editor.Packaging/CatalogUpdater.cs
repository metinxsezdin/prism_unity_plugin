using System.Linq;
using Prism.Assets;
using UnityEditor;
using UnityEngine;

namespace Prism.Unity.Editor.Packaging
{
    /// <summary>Keeps Assets/Prism/PrismAssetCatalog.asset listing every definition, sorted.</summary>
    public static class CatalogUpdater
    {
        public const string CatalogPath = ProductImporter.Root + "/PrismAssetCatalog.asset";

        public static PrismAssetCatalog GetOrCreate()
        {
            var catalog = AssetDatabase.LoadAssetAtPath<PrismAssetCatalog>(CatalogPath);
            if (catalog != null) return catalog;
            ProductImporter.EnsureFolder(ProductImporter.Root);
            catalog = ScriptableObject.CreateInstance<PrismAssetCatalog>();
            AssetDatabase.CreateAsset(catalog, CatalogPath);
            AddressablesRegistrar.Register(AssetDatabase.AssetPathToGUID(CatalogPath), PrismAssetCatalog.Address, "Prism", new[] { "prism" });
            return catalog;
        }

        public static void Add(PrismAssetDefinition definition)
        {
            var catalog = GetOrCreate();
            var list = catalog.definitions.Where(d => d != null).ToList();
            if (!list.Contains(definition)) list.Add(definition);
            catalog.definitions = list.OrderBy(d => d.entityPath, System.StringComparer.Ordinal)
                .ThenBy(d => d.product, System.StringComparer.Ordinal).ToList();
            EditorUtility.SetDirty(catalog);
            AssetDatabase.SaveAssetIfDirty(catalog);
        }
    }
}
