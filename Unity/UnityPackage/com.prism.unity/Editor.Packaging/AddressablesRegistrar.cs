using System.Linq;
using UnityEditor;
using UnityEditor.AddressableAssets;
using UnityEditor.AddressableAssets.Settings;
using UnityEditor.AddressableAssets.Settings.GroupSchemas;

namespace Prism.Unity.Editor.Packaging
{
    /// <summary>Registers Prism assets with Addressables without ever taking over someone else's entry.</summary>
    public static class AddressablesRegistrar
    {
        /// <summary>
        /// Make the asset Addressable at address, in group (created if missing), with labels.
        /// Returns a warning when the address already belongs to another asset (nothing is changed then).
        /// An asset already in another group keeps its group and address; only labels are added.
        /// </summary>
        public static string Register(string assetGuid, string address, string group, string[] labels)
        {
            var settings = AddressableAssetSettingsDefaultObject.GetSettings(true); // creates them on first use, no dialog

            var taken = settings.groups.Where(g => g != null).SelectMany(g => g.entries)
                .FirstOrDefault(e => e.address == address && e.guid != assetGuid);
            if (taken != null)
                return $"Addressable address '{address}' already belongs to {taken.AssetPath}; it was left unchanged and this asset was not registered.";

            var entry = settings.FindAssetEntry(assetGuid);
            if (entry == null)
            {
                var target = settings.FindGroup(group) ?? settings.CreateGroup(group, false, false, true, null,
                    typeof(BundledAssetGroupSchema), typeof(ContentUpdateGroupSchema));
                entry = settings.CreateOrMoveEntry(assetGuid, target, false, false);
                entry.address = address;
            }
            foreach (var label in labels.Where(l => !string.IsNullOrEmpty(l)))
            {
                settings.AddLabel(label, false);
                entry.SetLabel(label, true, false, false);
            }
            settings.SetDirty(AddressableAssetSettings.ModificationEvent.EntryModified, entry, true, true);
            return null;
        }
    }
}
