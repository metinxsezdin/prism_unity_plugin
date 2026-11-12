# Prism ↔ Unity

A Unity integration for [Prism Pipeline](https://github.com/PrismPipeline/Prism) 2. Models published to Prism from Maya or Blender come into Unity with their version, and stay updatable in place. Unity scenes are saved as Prism versions, and turntables and camera playblasts are published to Prism's media browser.

Everything can be done from a **Prism** menu in the Unity editor, or by Claude through Unity MCP.

Tested on Windows 11 with Prism 2.1.2.1 and Unity 6000.5.6f1 (URP).

## What it does

- **Import products.** Bring any version of a Prism product (`.fbx`, `.obj`, `.abc`) into `Assets/Prism/<entity>/<product>/`. The path never contains a version number.
- **Update in place.**
  - A new version overwrites the same file and keeps its `.meta`.
  - Material remaps, prefab links and scene placement survive the update.
  - If the new version renames or removes objects or material slots, the update stops and shows the differences before anything changes.
  - A change of file format (e.g. FBX → OBJ) also asks first.
- **Check for new versions.**
  - Lists imported products that have a newer version in Prism, including products imported as Prism `master`.
  - Runs on editor start when Prism's "check import versions" setting is on.
- **Version scenes.**
  - *Save Version* writes the working scene (which stays in `Assets/`) to Prism's scene folder as the next version, with a comment.
  - Opening an old version from Prism's Project Browser brings it back into the working path. It refuses to overwrite work that isn't saved as a Prism version unless you explicitly discard it.
- **Publish playblasts.**
  - *Turntable* orbits the selected objects in an isolated preview scene, so your scene is never touched.
  - *Camera* records any scene camera and steps Timelines frame by frame.
  - Output is a PNG sequence or MP4, written as a versioned Prism media product.
- **Package every product.** Each import also gets a prefab variant, a ScriptableObject definition, a thumbnail and Addressable entries, all listed in one catalog. See [Asset packages](#asset-packages).
- **Work with Claude.**
  - Twelve MCP tools expose the same operations.
  - Calls coming from Claude never open a window. Anything that needs a decision comes back as a question for the user.

## How it works

The plugin has two halves that talk to each other over `127.0.0.1`:

```
Unity editor                                   Prism process (Python + Qt)
┌──────────────────────────────┐              ┌──────────────────────────────┐
│ com.prism.unity (C#, Editor) │  JSON lines  │ Prism "Unity" app plugin     │
│  Prism menu / MCP tools      │ ───────────► │  Prism_Unity_Launcher.py     │
│  PrismApi                    │ ◄─────────── │  unity_bridge/commands.py    │
│  command server              │   + token    │  PrismCore                   │
└──────────────────────────────┘              └──────────────────────────────┘
```

**Prism process**
- Unity has no Python, so Prism runs as its own process, the same way Prism's After Effects and Photoshop plugins work.
- Unity starts it on first use, one instance per Unity project, and it quits when the editor closes.

**Protocol**
- One JSON object per line.
- Every request carries a per-session token.
- Each side accepts only a fixed list of commands. Nothing received over the socket is executed as code.

**Ports**
- Neither side reserves a port.
- Each side binds whatever port is free and publishes it in the Unity project's `Library/PrismUnity/` folder: `session.json` for Unity, `prism.json` for Prism.

**Deadlock rule**
- The side that is waiting is never called back.
- When Prism starts an import or a playblast, it resolves the file or output path itself before calling Unity.

**Pinned project**
- A Unity project is pinned to one Prism project in `ProjectSettings/PrismUnity/project.json`.
- The plugin never changes which project Prism, Maya or Blender open by default.

## Requirements

- Windows
- Prism Pipeline 2.1.x installed in `C:\Program Files\Prism2`
- Unity 6000.5 with URP
- For Claude in Unity: the Unity AI Assistant package (`com.unity.ai.assistant`) in the Unity project and the `unity-mcp` server in your Claude client
- For Claude in Prism without Unity: Claude Code (the Prism MCP, see [Prism MCP](#prism-mcp-claude-without-unity))

## Installation

### 1. Set up the machine (once per machine)

Clone the repository, then double-click **`Install.bat`** in its root. It:
- registers the `Unity/` folder (the Prism plugin) with Prism,
- adds the Prism MCP to Claude Code for your Windows user,
- checks that the Prism MCP can start Prism, and ends with a line such as `Prism MCP OK: Prism v2.1.2.1, user Ayşe, 3 projects`.

It is safe to run again. `Uninstall.bat` undoes it. If Prism is not in `C:\Program Files\Prism2`, it asks for the folder once
(or run `tools\install.ps1 -PrismRoot D:\Prism2`). If it says Prism's settings were not found, start Prism once and run it again.

Developers can register only the plugin with `tools\deploy_dev.ps1`: it adds `Unity/` to `%USERPROFILE%\Documents\Prism2\PluginPaths.json`. A backup of the original is kept as `PluginPaths.json.bak`, and `tools\deploy_dev.ps1 -Remove` undoes the change.

Then restart Prism (tray icon → **Exit**, and start it again). Prism reads its plugin list only at startup, so a Prism that was already running won't show **Unity** under **DCC apps** until it restarts.

You can also add the same folder from the plugins section of Prism's settings.

### 2. Add it to a Unity project (once per project)

1. In Prism, switch to the project the Unity project belongs to.
2. Open **Prism Settings → DCC apps → Unity** and select the Unity project folder (the one containing `Assets`, `Packages` and `ProjectSettings`).
3. Prism copies two packages into the project's `Packages/` folder and pins the current Prism project:
   - `com.prism.unity`: the editor integration.
   - `com.prism.assets`: the runtime types of asset packages. It pulls in Addressables 2.9.1, which ships with Unity 6000.5.
4. Open the project in Unity. A **Prism** menu appears.

The packages are copies, not links to this repository, so the project works on machines without the plugin, and they go into Git with the project. To upgrade, run step 2 again. When the plugin on a machine is newer than the copy in the project, Unity says so in the Console and on Project Settings → Prism. Bump `version` in a package's `package.json` whenever you change it, so the warning can tell. Removing the integration in Prism removes `com.prism.unity` only; `com.prism.assets` stays because game code and the definitions use its types.

If Prism is installed somewhere else, set the path once in Unity: `EditorPrefs.SetString("PrismUnity.PrismRoot", @"D:\Prism2")`.

### 3. Version control

Commit the imported assets and the plugin's records so everyone works with the same versions:

- `Assets/Prism/**`, including `.meta` files
- `Assets/AddressableAssetsData/**`: the Addressables settings and groups
- `Packages/com.prism.unity/` and `Packages/com.prism.assets/`
- `ProjectSettings/PrismUnity/**`:
  - `project.json`: the pinned Prism project
  - `settings.json`: the packaging settings from Project Settings → Prism
  - `imports/`: one file per imported product
  - `scenes/`: one file per bound scene

`Library/` stays out of Git, as usual. Use Git LFS for the binaries:

```
*.fbx filter=lfs diff=lfs merge=lfs -text
*.abc filter=lfs diff=lfs merge=lfs -text
*.obj filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
```

## Using the Prism menu

| Item | What it does |
|---|---|
| Project Browser | Opens Prism's Project Browser. Opening a Unity scene version there opens it in Unity. |
| Save Version | Saves the active scene as the next Prism version. The first save asks for the Prism asset and task; the department defaults to `Unity`. |
| Save Comment... | Same, asking for a comment first. |
| Import... | Opens Prism's product browser and imports the version you pick. |
| Check for New Versions... | Lists imported products with newer versions and updates the ones you select. Products that were removed from Prism are flagged, not deleted. |
| Generate Missing Asset Packages | Packages products imported before packaging was turned on. Existing packages are left alone. |
| Convert Definitions to Selected Class | Switches every definition to the class selected in the Project window (or the one in Project Settings → Prism), after asking. |
| Playblast... | Turntable of the selection or recording of a camera, as PNG or MP4. |
| Prism Settings... | Opens Prism's settings. |

**For modellers:** keep object and material names stable between exports. Renaming `Stem` to `StemMain` in Maya means material assignments on `Stem` in Unity have to be redone, which is why the update stops and asks.

**Scene versions:** a scene file references models, materials and shaders; it doesn't contain them. An old scene version opens correctly as long as those assets still exist in the project.

## Asset packages

Every imported product is packaged next to its model:

```
Assets/Prism/Props/Lotus/lotus_model/
  lotus_model.fbx          the model; Prism overwrites it on every update
  lotus_model.prefab       prefab variant of the model; yours, never overwritten
  lotus_model.asset        definition (ScriptableObject); Prism fields refreshed, the rest kept
  lotus_model_thumb.png    Prism's preview image, or a rendered frame when there is none
Assets/Prism/PrismAssetCatalog.asset   every definition, sorted
```

**Use the prefab, not the model.** Colliders, scripts and material overrides belong on the prefab variant. A model update flows into it, and your additions stay.

**Definitions.**
- Prism writes `entityType`, `entityPath`, `product`, `version`, `contentVersion`, `addressableKey`, `prefab`, `thumbnail` and `prismMissing`.
- `displayName` starts as the entity name, and the team can change it.
- For game data such as price or unlock level, write a subclass of `Prism.Assets.PrismAssetDefinition` in a file of the same name, then pick it in **Project Settings → Prism**. New packages use it, and **Prism → Convert Definitions to Selected Class** switches the existing ones. Files, GUIDs and every existing field stay the same.

**Addressables.**
- The prefab is addressable as `{entity}/{product}` (`Props/Lotus/lotus_model`), the definition as `…#definition` and the thumbnail as `…#thumb`.
- Each category gets its own group (`Prism Props`), so content can be shipped per category.
- Labels are `prism`, the category and the product.
- The catalog's address is `PrismAssetCatalog`.
- The first package creates the Addressables settings if the project has none.
- If an address is already taken by another asset, that asset is left alone and a warning is logged.
- An entry the team moved to another group or renamed keeps its group and address.

```csharp
var catalog = await Addressables.LoadAssetAsync<PrismAssetCatalog>(PrismAssetCatalog.Address).Task;
foreach (var item in catalog.ByCategory("Props"))
    await item.prefab.InstantiateAsync().Task;
```

**Removed in Prism.** When *Check for New Versions* finds that a product (or its whole asset) no longer exists in Prism, its definition gets `prismMissing = true`. Nothing is deleted. The flag clears by itself when the product is back. The startup check mentions a removed product once, not on every launch. If the Prism project's drive is offline, nothing is flagged.

**Things the team owns are never replaced.**
- A moved or renamed prefab variant is followed through the definition's `prefab` reference, and no second one is created.
- A renamed Addressable address is kept and becomes the definition's `addressableKey`.
- A definition file that no longer loads, typically after renaming its class, is left untouched with a warning.
- Conversion only goes to a class that extends the current one, so no field is lost.

**Project Settings → Prism** turns packaging on or off and sets the definition class and the address and group formats. The class list shows only classes that reach player builds (not ones in an editor-only assembly). An empty format means the default; characters a file name cannot hold, such as the `/` of `{entity}`, become `-` in group names; the page warns when the address format lacks `{entity}` or `{product}`. If the chosen class no longer exists, new definitions are created as `PrismAssetDefinition` and the package reports a warning. With packaging off, imports behave as before: only the model is written.

## Using it with Claude

With Unity AI Assistant installed and the editor open, Claude gets these tools:

- `prism_list_products`, `prism_list_versions`, `prism_list_imported`
- `prism_import`, `prism_update`, `prism_check_updates`
- `prism_save_version`, `prism_open_scene_version`
- `prism_playblast`, `prism_list_cameras`
- `prism_generate_packages`, `prism_convert_definitions`

Import, update and list results include each product's package (prefab path, definition path, Addressable key, thumbnail).

A request like *"import the latest lotus, put it in the scene, give it a pink URP Lit material, take a turntable"* runs end to end.

Claude's calls never open a window. When a decision belongs to the user, the tool returns an error instead of acting, and Claude has to ask the user before calling again:
- `needs_input`: something is missing, such as the Prism task for a scene's first save.
- `needs_confirmation`: the action could lose work, such as a renaming update, a new department, or overwriting unversioned scene work.

[`Documentation~/CLAUDE_TOOLS.md`](Unity/UnityPackage/com.prism.unity/Documentation~/CLAUDE_TOOLS.md) documents every tool, argument and error code. Claude reads it as its guide.

If the tools don't show up, use **Prism → Debug → Re-register Claude (MCP) Tools**.

## Prism MCP (Claude without Unity)

The Prism MCP gives Claude the Prism project itself, with Unity closed: what is in it, who published what, setting up assets,
shots, departments and tasks for the Maya and Blender artists, and tidying up versions. It never opens a window.
`Install.bat` sets it up; after that, ask Claude Code things like:

- *"Lotus'a Modeling departmanı aç, Sculpt ve Retopo task'larıyla"*
- *"Bu hafta kim ne publish etti?"*
- *"Modeli olmayan asset'ler hangileri?"*
- *"lotus_model master'ını v0003 yap"*

What it can do:
- **Look things up:** projects, assets and shots, departments and tasks, scene files, products and versions, playblasts and renders,
  scene dependencies, and reports (recent activity, assets without a model, masters behind the latest version, tasks not started).
- **Set up work:** create assets, shots, departments and tasks (also from Prism's task presets); set descriptions, metadata, preview
  pictures and frame ranges.
- **Manage versions:** set or delete masters, edit comments, omit or show entities, rename shots and sequences, delete shots.

Rules it follows:
- Anything that changes or removes existing data (a master, a comment, a rename, a delete) is shown to you first, and happens only
  after you say yes. If someone else changed the same thing in the meantime, you are shown the new state again.
- Deleting a shot moves it to `00_Pipeline/Trash` in the project; nothing is erased.
- Renaming or deleting a shot lists the scenes that use it. Unity imports of it will show as removed from Prism.
- Switching project switches only Claude; your own Prism keeps its project unless you ask Claude to change that too.
- Every change is logged in `Documents\Prism2\PrismMcp.log`.

Everyone on the team uses Prism **2.1.2.1**; the Prism MCP is written and tested against that version and warns on another one.
After a `git pull`, restart your Claude Code session to load the new tools; running `Install.bat` again is not needed.

[`PrismMcp/TOOLS.md`](PrismMcp/TOOLS.md) documents every tool, argument and error code.

## Troubleshooting

| Message | Meaning |
|---|---|
| *Prism was not found at …* | Prism is not where Unity looks. Set `PrismUnity.PrismRoot` (see Installation). |
| *The Prism project of this Unity project is not reachable* | The pinned `pipeline.json` can't be read, usually because the project drive isn't connected. Prism stops without opening a dialog. |
| *The Prism file is not reachable* | The product version's file is missing or offline. The existing asset in `Assets/` is left untouched. |
| *Unity is in Play Mode* | Imports, updates and scene operations are refused in Play Mode. |
| *Unity is not answering (it may be compiling scripts)* | Prism waited for a script reload to finish and gave up. Try again. |

The first call after opening Unity starts Prism and can take up to a minute. If Prism crashes, the next call starts it again.

## Development

```
Unity/                          Prism plugin (pluginDirectory)
  Scripts/Prism_Unity_*.py      Prism app plugin hooks, launcher, installer
  Scripts/unity_bridge/         protocol, servers/clients, commands, dialogs
  UnityPackage/com.prism.unity/ Unity editor package (Editor/, Editor.Mcp/, Editor.Packaging/, Tests/)
  UnityPackage/com.prism.assets/ runtime types of asset packages (definition, catalog)
PrismMcp/                       Prism MCP server (server.py, prism_mcp/, TOOLS.md)
Install.bat, Uninstall.bat      machine setup (tools/install.ps1)
TestProject/                    Unity 6000.5.6f1 URP project used by the tests
tests/python/                   Prism-side unit tests (integration/ needs real Prism; mcp_server/ for the Prism MCP)
fixtures/make_fbx.py            builds the test FBX files with Blender
tools/                          test runners, deploy script, test Prism project builder
docs/                           design spec, implementation plan, acceptance results
```

Run the tests from PowerShell:

```powershell
tools\run_py_tests.ps1                    # Prism side and Prism MCP, Prism's bundled Python
$env:PRISM_UNITY_IT=1; tools\run_py_tests.ps1 -Pattern "test_*_it.py"   # against a real Prism and the test Prism project
tools\run_unity_tests.ps1                 # Unity EditMode tests in TestProject
tools\run_unity_tests.ps1 -Category E2E   # against a real Prism and the test Prism project
tools\run_all_tests.ps1 -E2E              # everything
```

**What the end-to-end tests need**
- **A test Prism project:** create it with `"C:\Program Files\Prism2\Python313\python.exe" tools\make_test_prism_project.py`. It goes to `%USERPROFILE%\PrismUnityTest Project` by default.
- **No windows:** during these tests any Prism window that tries to open fails the test (`PRISM_UNITY_FAIL_ON_DIALOG=1`). That's how "Claude never opens a window" is verified.
- **Test FBX files:** they are generated with Blender 4.5: `blender -b --factory-startup -P fixtures/make_fbx.py -- <output folder>`.

## Limitations

- Windows only.
- No export from Unity back to Prism.
- Saving a scene version doesn't package the assets it references.
- The Prism-side windows (installer, Import, Check for New Versions, Playblast dialog) have been exercised by hand only in part. See [`docs/acceptance`](docs/acceptance/2026-11-11-v1-acceptance.md) for what is still to be checked manually.
