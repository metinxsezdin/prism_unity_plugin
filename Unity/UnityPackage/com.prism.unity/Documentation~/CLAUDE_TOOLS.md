# Prism tools for Claude (Unity MCP)

These tools let Claude work with Prism Pipeline from the Unity Editor: import and update Prism
products, save and open scene versions, and publish playblasts. None of them ever opens a window.

## Connection

- **Bridge:** Unity AI Assistant's MCP bridge (package `com.unity.ai.assistant`, relay `~/.unity/relay/relay_win.exe`).
- **Registration:** When that package is installed, the assembly `Prism.Unity.Editor.Mcp` registers every tool below with
  `McpToolRegistry.RegisterTool` in the group `Prism`. They then appear as MCP tools named `prism_*`.
- **Without that package:** The same operations exist as C# methods on `Prism.Unity.Editor.PrismMcpTools.Invoke(name, JObject)`
  and on `Prism.Unity.Editor.PrismApi`.
- **Prism itself:** Prism runs as a separate process that Unity starts on first use. The first call can take up to a minute.

## Results and errors

Through Unity MCP every tool answers one of two shapes:

- **Success:** `{"success": true, "message", "data": <result>}`
- **Failure:** `{"success": false, "code", "error": "<code>: <message>", "data": <details>}`

The C# API `PrismMcpTools.Invoke` uses the same content as `{"ok", "result"}` / `{"ok": false, "error": {"code", "message", "details"}}`.

| code | meaning | what Claude does |
|---|---|---|
| `needs_input` | Something only the user can choose is missing (`details.missing`), e.g. the Prism entity/task of a scene's first save. | Ask the user, then call again with the missing arguments. |
| `needs_confirmation` | The action could lose work or break references. `details.reason` / `details.removedNodes` / `removedMaterials` say why. | Show the user the details and ask. Only after a yes, call again with `confirm` / `createDepartment` / `confirmForeign` / `unsaved`. Never confirm on your own. |
| `source_unavailable` | The Prism file or version is not reachable (wrong version, offline drive). | Tell the user; list versions with `prism_list_versions`. |
| `missing_package` | A Unity package is needed (e.g. Alembic for `.abc`). | Tell the user which package to add. |
| `unity_busy` | Unity is in Play Mode, or is compiling scripts. | Ask the user to leave Play Mode, or retry after compilation. |
| `prism_unavailable` | Prism is not installed or did not start. | Tell the user; check the Prism install. |
| `bad_args` | Wrong or missing arguments. | Fix the call. |
| `timeout`, `internal` | Something else went wrong. | Report the message. |

Entities use Prism's own shape: `{"type":"asset","asset_path":"Props/Lotus"}` or `{"type":"shot","sequence":"sq01","shot":"sh010"}`.

## Tools

### prism_list_products
List the products of an entity.
- **Arguments:** `entity`
- **Example:** `{"entity":{"type":"asset","asset_path":"Props/Lotus"}}`

### prism_list_versions
List the versions of a product.
- **Arguments:** `entity`, `product`
- **Returns:** `[{version, comment, user, date, filepath, location}]`

### prism_list_imported
List what this Unity project imported from Prism.
- **Returns:** `[{id, entity, product, version, assetPath, sourcePath, ..., package}]`. `id` is what `prism_update` takes.
  `package` is described under [Asset packages](#asset-packages).

### prism_import
Import a product version into `Assets/Prism/<entity>/<product>/<product>.<ext>`.
- **Arguments:** `entity`, `product`, optional `version` (`latest` by default; also `master` or `v0002`), optional `confirm`.
- **Re-import:** Importing an already imported product updates it in place. The asset GUID, material remaps, prefab links and
  scene placement are kept.
- **Breaking update:** If the new version renames or removes objects or materials, the answer is `needs_confirmation` with the
  diff, and nothing changes until you call again with `"confirm": true`.
- **Format change:** If the new version has a different file format (e.g. `.fbx` → `.obj`), the answer is `needs_confirmation`
  (`reason: format_changed`). Confirming creates a second asset; scenes and materials keep using the old one until switched.
- **Returns:** `{record, updated, changes, package}`. Use `package.prefabPath` to place the model in a scene, not the raw model file.
- **Example:** `{"entity":{"type":"asset","asset_path":"Props/Lotus"},"product":"lotus_model"}`

### prism_update
Update an imported product.
- **Arguments:** `recordId` (from `prism_list_imported`), optional `version` (`latest`), optional `confirm`.
- **Breaking update:** Same confirmation rule as `prism_import`.

### prism_check_updates
List imported products that have a newer version in Prism.
- **Returns:** `[{id, current, latest, entity, product}]`, plus `{id, missing: true, entity, product}` for products that no longer
  exist in Prism (the product or its whole entity was deleted). A missing product's package is flagged `prismMissing` and
  kept; nothing is deleted. Tell the user. The flag clears by itself once the product exists in Prism again.

### prism_save_version
Save the active scene as a new Prism version.
- **Arguments:** optional `comment`, `entity`, `task`, `department`, `createDepartment`.
- **First save:** The first save of a scene needs `entity` and `task`; `department` defaults to `Unity`. Without them the answer is
  `needs_input`; ask the user which Prism asset and task the scene belongs to.
- **Missing department:** If the department does not exist yet, the answer is `needs_confirmation`
  (`reason: create_department`). Ask, then repeat with `"createDepartment": true`.
- **Returns:** `{path, version}`
- **Example (first save):** `{"comment":"first layout","entity":{"type":"asset","asset_path":"Scenes/MeditationRoom"},"task":"layout"}`

### prism_open_scene_version
Open a scene version from Prism.
- **Arguments:** `path` (a Prism scene file), optional `unsaved` (`abort` | `save` | `discard`, default `abort`), optional `confirmForeign`.
- **Unsaved changes:** With unsaved changes in any loaded scene the answer is `needs_confirmation` (`reason: unsaved_changes`).
- **Unversioned changes:** If the working scene file holds work that is not saved as a Prism version, the answer is
  `needs_confirmation` (`reason: unversioned_changes`). This covers work saved with Ctrl+S, or just saved with `unsaved: "save"`.
- **What to do:** For either answer, ask the user. To keep the work, call `prism_save_version` first and then open again; to drop
  it, call again with `"unsaved": "discard"`. `"save"` alone never protects the work, because the working file is replaced.
- **Other projects:** A version saved from another Unity project answers `needs_confirmation` (`reason: foreign_project`).

### prism_playblast
Render and publish a playblast to Prism's media.
- **Arguments:** `mode` (`turntable` | `free`), optional `targetPaths`, `cameraPath`, `width`, `height`, `frames`, `fps`,
  `format` (`png` | `mp4`), `comment`, `task`, `entity`.
- **Turntable:** Orbits the selected (or given) objects in an isolated preview, so the scene is never changed. It is published
  under the Prism asset the objects were imported from. Objects that did not come from Prism need `entity`.
- **Free:** Records a scene camera (use `prism_list_cameras`). It is published under the scene's Prism entity, so save a version
  first.
- **Returns:** `{outputPath, version, frameCount}`
- **Example:** `{"mode":"turntable","targetPaths":["Lotus"],"frames":120,"format":"mp4","comment":"new petals"}`

### prism_list_cameras
List the cameras of the active scene.
- **Returns:** `[{name, path}]`

### prism_generate_packages
Create the asset package for every imported product that has none (for example products imported before packaging was turned
on). Existing packages are left untouched.
It also re-registers the Addressable and catalog entries of complete packages, which repairs a reset Addressables setup.
- **Returns:** `{generated, repaired, failed: [{id, error}]}`. A product that fails (e.g. its model file is gone) is listed and skipped.

### prism_convert_definitions
Switch every package definition to a team definition class, a subclass of `Prism.Assets.PrismAssetDefinition`.
- **Arguments:** `className` (simple name, full name or assembly-qualified name), optional `confirm`.
- **Confirmation:** Without `confirm` the answer is `needs_confirmation` with `{count, paths, className}`. Tell the user how many
  definitions change, then call again with `"confirm": true`.
- **Which:** Only definitions whose class the target extends (e.g. `PrismAssetDefinition` → `WellnessItemDefinition`), so no
  field is ever lost. Definitions of another team class, or a conversion back to a base class, are left alone.
- **Kept:** Files, GUIDs, every reference to the definitions and every existing field. New fields start empty.
- **Returns:** `{converted, className}`
- **Class file:** The class must be in a script file of the same name (`WellnessItemDefinition.cs`), or Unity cannot save assets of it.

## Asset packages

Every imported product gets a package next to its model in `Assets/Prism/<entity>/<product>/`:

| File | What it is | Who owns it |
|---|---|---|
| `<product>.fbx` | The model from Prism | Prism (overwritten on update) |
| `<product>.prefab` | Prefab variant of the model | The team: created once, never overwritten. Add colliders, scripts and materials here. |
| `<product>.asset` | Definition (ScriptableObject) | The team: Prism fields are refreshed on update, every other field is kept. |
| `<product>_thumb.png` | Thumbnail from Prism's preview, else a rendered frame | Prism (rewritten on update) |

`package` in tool results is `{prefabPath, definitionPath, addressableKey, thumbnailPath, complete, definitionClass, prismMissing, warning?}`.
- `prefabPath` follows the definition's `prefab` reference, so it is right even if the team moved the prefab.
- `addressableKey` is the address the prefab actually has (the team may have renamed it). It is `null` when the prefab is
  not addressable, usually because the address was taken by another asset: then `warning` says which, that asset was left
  alone, and the prefab is not loadable by key until the team frees the address or picks another one.
- `warning` also reports a definition file that exists but no longer loads (a renamed script); it is never replaced.
- Use `prefabPath` only when `complete` is true; otherwise run `prism_generate_packages` first.

**Definition fields set by Prism:** `entityType`, `entityPath`, `product`, `version`, `contentVersion`, `addressableKey`, `prefab`
(`AssetReferenceGameObject`), `thumbnail` (`AssetReferenceTexture2D`), `prismMissing`. `displayName` is set only while empty.

**Addressables** (defaults; Project Settings → Prism can change them):
- Prefab address `{entity}/{product}`, e.g. `Props/Lotus/lotus_model`; definition `…#definition`; thumbnail `…#thumb`.
- Group `Prism {category}`, where category is the entity's first folder (`Prism Props`).
- Labels `prism`, the category and the product name.
- The catalog `Assets/Prism/PrismAssetCatalog.asset` lists every definition, at address `PrismAssetCatalog`.

**Loading at runtime** (assembly reference `Prism.Assets`, `Unity.Addressables`, `Unity.ResourceManager`):

```csharp
using Prism.Assets;
using UnityEngine.AddressableAssets;

var catalog = await Addressables.LoadAssetAsync<PrismAssetCatalog>(PrismAssetCatalog.Address).Task;
foreach (var item in catalog.ByCategory("Props"))
{
    var icon = await item.thumbnail.LoadAssetAsync().Task;
    var go = await item.prefab.InstantiateAsync().Task;
}
// Or one product directly:
var lotus = await Addressables.InstantiateAsync("Props/Lotus/lotus_model").Task;
```

When writing game code for a team definition class, use `catalog.OfType<WellnessItemDefinition>()`.

## Typical flow

"Import the latest lotus, put it in the scene, give it a new material, take a turntable":

1. `prism_import` with Props/Lotus and lotus_model.
2. Instantiate the prefab at `result.package.prefabPath` (or `result.record.assetPath` when there is no package) and set up the
   material on the prefab, using Unity MCP's own scene and asset tools.
3. `prism_playblast` with `{"mode":"turntable","targetPaths":["<instance name>"]}`.
4. If asked, `prism_save_version`.
