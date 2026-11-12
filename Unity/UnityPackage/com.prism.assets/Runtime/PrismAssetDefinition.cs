using UnityEngine;
using UnityEngine.AddressableAssets;

namespace Prism.Assets
{
    /// <summary>
    /// One Prism product as the game sees it. The Prism plugin creates and updates the fields below;
    /// it never touches fields a team adds in its own subclass, and sets displayName only while it is empty.
    /// References are Addressable so loading the catalog does not load every prefab.
    /// </summary>
    [CreateAssetMenu(menuName = "Prism/Asset Definition", fileName = "AssetDefinition")]
    public class PrismAssetDefinition : ScriptableObject
    {
        [Tooltip("Shown to players or in tools. Set once from the Prism entity name; yours to change.")]
        public string displayName;

        [Header("Managed by Prism")]
        public string entityType;
        public string entityPath;
        public string product;
        public string version;
        [Tooltip("The numbered version the files contain (\"master\" is a copy of one).")]
        public string contentVersion;
        public string addressableKey;
        public AssetReferenceGameObject prefab = new AssetReferenceGameObject("");
        public AssetReferenceTexture2D thumbnail = new AssetReferenceTexture2D("");
        [Tooltip("The product no longer exists in Prism. Nothing was deleted.")]
        public bool prismMissing;

        /// <summary>First folder of the entity path: "Props" for "Props/Lotus", the sequence for a shot.</summary>
        public string Category
        {
            get
            {
                if (string.IsNullOrEmpty(entityPath)) return "";
                var slash = entityPath.IndexOf('/');
                return slash < 0 ? entityPath : entityPath.Substring(0, slash);
            }
        }
    }
}
