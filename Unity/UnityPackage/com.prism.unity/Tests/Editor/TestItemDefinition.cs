using Prism.Assets;

namespace Prism.Unity.Editor.Tests
{
    /// <summary>A team-defined definition class, as the team would write in its own assembly.
    /// It has its own file so Unity can resolve the script of saved .asset files.</summary>
    public class TestItemDefinition : PrismAssetDefinition
    {
        public int unlockLevel;
    }
}
