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
| `unity_busy` | Unity is in Play Mode. | Ask the user to leave Play Mode. |
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
- **Returns:** `[{id, entity, product, version, assetPath, sourcePath, ...}]`. `id` is what `prism_update` takes.

### prism_import
Import a product version into `Assets/Prism/<entity>/<product>/<product>.<ext>`.
- **Arguments:** `entity`, `product`, optional `version` (`latest` by default; also `master` or `v0002`), optional `confirm`.
- **Re-import:** Importing an already imported product updates it in place. The asset GUID, material remaps, prefab links and
  scene placement are kept.
- **Breaking update:** If the new version renames or removes objects or materials, the answer is `needs_confirmation` with the
  diff, and nothing changes until you call again with `"confirm": true`.
- **Example:** `{"entity":{"type":"asset","asset_path":"Props/Lotus"},"product":"lotus_model"}`

### prism_update
Update an imported product.
- **Arguments:** `recordId` (from `prism_list_imported`), optional `version` (`latest`), optional `confirm`.
- **Breaking update:** Same confirmation rule as `prism_import`.

### prism_check_updates
List imported products that have a newer version in Prism.
- **Returns:** `[{id, current, latest, entity, product}]`

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
- **Unsaved changes:** With unsaved changes the answer is `needs_confirmation` (`reason: unsaved_changes`). Ask whether to save or
  discard them.
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

## Typical flow

"Import the latest lotus, put it in the scene, give it a new material, take a turntable":

1. `prism_import` with Props/Lotus and lotus_model.
2. Instantiate the asset at `result.record.assetPath` and set up the material, using Unity MCP's own scene and asset tools.
3. `prism_playblast` with `{"mode":"turntable","targetPaths":["<instance name>"]}`.
4. If asked, `prism_save_version`.
