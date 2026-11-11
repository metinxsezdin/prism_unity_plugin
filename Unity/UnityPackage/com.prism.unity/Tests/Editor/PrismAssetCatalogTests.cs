using System.Linq;
using NUnit.Framework;
using Prism.Assets;
using UnityEngine;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>A team-defined definition class, as the team would write in its own assembly.</summary>
    public class TestItemDefinition : PrismAssetDefinition
    {
        public int unlockLevel;
    }

    public class PrismAssetCatalogTests
    {
        static T Def<T>(string entityPath, string product) where T : PrismAssetDefinition
        {
            var d = ScriptableObject.CreateInstance<T>();
            d.entityType = "asset";
            d.entityPath = entityPath;
            d.product = product;
            return d;
        }

        static PrismAssetCatalog Catalog(params PrismAssetDefinition[] defs)
        {
            var c = ScriptableObject.CreateInstance<PrismAssetCatalog>();
            c.definitions.AddRange(defs);
            return c;
        }

        [Test]
        public void ByCategoryUsesFirstFolder()
        {
            var c = Catalog(Def<PrismAssetDefinition>("Props/Lotus", "lotus_model"),
                Def<PrismAssetDefinition>("Props/Çay Bardağı", "cay_model"),
                Def<PrismAssetDefinition>("Scenes/MeditationRoom", "room"));
            Assert.AreEqual(2, c.ByCategory("Props").Count());
            Assert.AreEqual("room", c.ByCategory("Scenes").Single().product);
            Assert.AreEqual("Props", c.definitions[1].Category);
        }

        [Test]
        public void FindByEntityAndProduct()
        {
            var lotus = Def<PrismAssetDefinition>("Props/Lotus", "lotus_model");
            var c = Catalog(Def<PrismAssetDefinition>("Props/Lotus", "lotus_rig"), lotus);
            Assert.AreSame(lotus, c.Find("Props/Lotus", "lotus_model"));
            Assert.IsNull(c.Find("Props/Lotus", "nope"));
        }

        [Test]
        public void OfTypeReturnsSubclassesOnly()
        {
            var item = Def<TestItemDefinition>("Props/Lotus", "lotus_model");
            var c = Catalog(item, Def<PrismAssetDefinition>("Props/Stone", "stone_model"));
            Assert.AreSame(item, c.OfType<TestItemDefinition>().Single());
        }

        [Test]
        public void DefinitionHasAddressableReferences()
        {
            var d = Def<PrismAssetDefinition>("Props/Lotus", "lotus_model");
            Assert.IsInstanceOf<UnityEngine.AddressableAssets.AssetReferenceGameObject>(d.prefab);
            Assert.IsInstanceOf<UnityEngine.AddressableAssets.AssetReferenceTexture2D>(d.thumbnail);
        }

        [Test]
        public void RuntimeAssemblyHasNoEditorReference()
        {
            var refs = typeof(PrismAssetDefinition).Assembly.GetReferencedAssemblies().Select(a => a.Name).ToArray();
            CollectionAssert.DoesNotContain(refs, "UnityEditor");
            CollectionAssert.DoesNotContain(refs, "UnityEditor.CoreModule");
        }
    }
}
