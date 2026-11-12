# Prism MCP tools

These tools let Claude work in a Prism Pipeline 2 project directly: look things up, set up work for the Maya and Blender
artists, and tidy up versions. Unity does not need to be open, and no tool ever opens a window.

## Connection

- **Server:** `PrismMcp/server.py`, run with Prism's own Python (`<PrismRoot>\Python313\python.exe`), speaking MCP over stdio.
  The MCP server name is `prism`; in Claude Code the tools appear as `mcp__prism__<name>`.
- **Install:** `Install.bat` in the repository root adds it to Claude Code for the current Windows user (see the README).
- **Prism:** the first call loads Prism without UI; that can take a few seconds. Team Prism version: **2.1.2.1**. `status`
  warns when the machine has another version.
- **Project:** Claude starts in the user's current Prism project. `set_project` switches only Claude's session; the user's own
  Prism, Maya, Blender and Unity keep their project unless `persist: true` is confirmed.
- **User:** changes are made as the machine's Prism user, and logged to `Documents\Prism2\PrismMcp.log` (one JSON line per
  change: time, user, project, tool, arguments, outcome).

Entities use Prism's own shape: `{"type":"asset","asset_path":"Props/Lotus"}` or `{"type":"shot","sequence":"sq01","shot":"sh010"}`.
`rename` also takes `{"type":"sequence","sequence":"sq01"}`.

## Results and errors

Every tool answers JSON text:

- **Success:** `{"ok": true, "project": {"name", "path"}, "result": ...}`
- **Failure:** `{"ok": false, "project": ..., "error": {"code", "message", "details"}}` (the MCP result has `isError: true`)

| code | meaning | what Claude does |
|---|---|---|
| `needs_confirmation` | The call would change or remove existing data. Nothing changed. `details.summary`, `details.changes`, `details.confirmToken`. | Show the user the summary and changes and ask. Only after a yes, call again with the same arguments plus `confirm: <confirmToken>`. Never confirm on your own. |
| `needs_input` | Something only the user can supply: no Prism user name (`missing: ["prismUser"]`), no project, a department that does not exist yet, two projects with the same name (`candidates`). | Ask the user, or create the missing piece after asking. |
| `source_unavailable` | A project, scene file or drive is not reachable (e.g. the `M:` drive is not connected). | Tell the user. |
| `prism_unavailable` | Prism is not installed or did not start. | Tell the user; `status` and `Install.bat` show the details. |
| `bad_args` | Wrong arguments, an unknown entity/version/department/preset. The message lists the valid choices. | Fix the call. |
| `internal` | Prism refused or failed (e.g. a file is open in another program). `details.locked` names the open folder. | Report the message. |

**Confirmation tokens.** A token belongs to one preview of one state. If someone else changes the same thing before the user
says yes (another master, another comment), the second call answers `needs_confirmation` again with the new state and a new
token. Show the new preview.

**Lists** take `limit` (default 200) and answer `{"items": [...], "truncated": bool}`.

## Session and project

### status
Prism version, team version, Prism user and abbreviation, active project, server version; `warning` when Prism is not 2.1.2.1.
`needs_input` (`missing: ["prismUser"]`) when no Prism user name is set.

### list_projects
Recently opened projects: `{name, configPath, reachable, current}`.

### set_project
Switch Claude's project. **Arguments:** `name` (a recent project) or `configPath` (`pipeline.json` or the project folder);
optional `persist`, `confirm`.
- Without `persist`, only this Claude session switches; no confirmation.
- With `persist: true` the user's Prism selection changes too; asks for confirmation (`changes: {from, to}`).
- **Returns:** `{changed, persisted, project}`.

## Queries (never change anything)

### list_entities
Assets (`type: "asset"`, default) or shots (`type: "shot"`). **Arguments:** optional `path` (asset folder prefix, e.g. `Props`),
`contains`, `includeOmitted`, `limit`. **Items:** `{entity, omitted}`.

### get_entity
**Arguments:** `entity`. **Returns:** `{entity, omitted, description (assets), metaData, previewPath, frameRange (shots), departments: [{name, tasks}]}`.
Department names are Prism's folder abbreviations (e.g. `mod`).

### list_scenefiles
Scene files of an entity. **Arguments:** `entity`, optional `department`, `task`, `limit`.
**Items:** `{path, entity, department, task, version, comment, user, date, app}`; `app` is Maya, Blender, Unity, Houdini or the extension.

### list_products
**Arguments:** `entity`. **Items:** `{product, entity}`.

### list_versions
**Arguments:** `entity`, `product`. **Items:** `{version, contentVersion, comment, user, date, filepath, location, previewPath, isMaster}`.
The `master` entry and the version it copies both have `isMaster: true`.

### list_media
Playblasts, renders and other media. **Arguments:** `entity`. **Items:** `{kind, identifier, versions: [{version, comment, user, date, path}]}`.

### get_dependencies
**Arguments:** `scenefile` (path). **Returns:** `{scenefile, dependencies: [paths]}` as Prism recorded them when the scene was saved.

### report
**Arguments:** `kind`, plus:
- `recent_activity`: optional `since` (`YYYY-MM-DD`, default 7 days ago). Scene files, product versions and media saved since then,
  newest first (by file time): `{kind, entity, name, version, user, comment, date, path}`, plus `byUser: {user: count}`.
- `missing_products`: optional `product` pattern (default `*`, e.g. `*_model`) and `category` (asset folder prefix).
  Assets with no matching product: `{entity, products}`.
- `master_behind`: products whose master is missing or older than the latest version: `{entity, product, latest, master}`.
- `empty_tasks`: tasks with no scene file yet: `{entity, department, task}`.

## Setting up work (adds; never overwrites without asking)

Creating something that exists already changes nothing and answers `created: false`.

### create_entity
**Arguments:** `entity`; optional `description` (assets), `frameRange: [start, end]` (shots), `taskPreset` (see `list_task_presets`).
Folders in `asset_path` are created as needed. Names may not be empty, start or end with spaces, or contain `< > : " / \ | ? *`;
Prism's own folder names (`Export`, `Scenefiles`, ...) are refused. **Returns:** `{created, entity, omitted}`.

### create_department
**Arguments:** `entity`, `department` (name such as `Modeling` or abbreviation such as `mod`), optional `defaultTasks` (true).
Prism's default tasks of that department are created too. **Returns:** `{created, entity, department, tasks}`.

### create_task
**Arguments:** `entity`, `department`, `task`. The department must exist: otherwise `needs_input` with `missing: ["department"]`;
ask the user, then `create_department`. **Returns:** `{created, entity, department, task}`.

### list_task_presets
**Arguments:** optional `type` (`asset`/`shot`). **Returns:** `[{name, departments: [{name, tasks}]}]`.

### apply_task_preset
**Arguments:** `entity`, `preset`, optional `dryRun`. `dryRun: true` only lists what the preset contains.
**Returns:** `{departments, created: [{department, task}]}`.

### set_description
Asset description. **Arguments:** `entity`, `description`, `confirm`. Replacing a non-empty description asks for confirmation.

### set_metadata
**Arguments:** `entity`, `metaData: {field: value}`, `confirm`. New fields are added directly; changing a field that has a value asks
for confirmation (`changes: {field: {from, to}}`). Stored in Prism's `{value, show}` form.

### set_preview
**Arguments:** `entity`, `imagePath` (local `.jpg`/`.png`), `confirm`. Replacing an existing preview asks for confirmation.

### set_shot_range
**Arguments:** `entity` (shot), `start`, `end`, `confirm`. Changing an existing range asks for confirmation.

## Managing versions (always confirmed)

### set_master
Make a version the master. **Arguments:** `entity`, `version`, and either `product` or `identifier` (media; optional `kind`), `confirm`.
`changes: {from, to}`. Already the master: `{changed: false}` without a question.

### delete_master
Remove a product's master (a copy of one version; the version itself stays). **Arguments:** `entity`, `product`, `confirm`.
No master: `{changed: false}`. A file open in another program: `internal`.

### set_comment
**Arguments:** `target`, `comment`, `confirm`. `target` is `{entity, product, version}`, `{entity, identifier, version}` (media) or
`{scenefile}`. Filling an empty comment needs no confirmation; replacing one does.

### omit
Hide an asset or shot in Prism. Its files are not touched. **Arguments:** `entity`, `confirm`.

### unomit
Show an omitted asset or shot again. **Arguments:** `entity`, `confirm`.

### rename
Rename a shot or a sequence. **Arguments:** `entity`, `newName`, `confirm`. Assets and episodes cannot be renamed.
- The preview lists `folders`, `dependents` (scene files elsewhere in the project that use the entity's products; their links
  break) and a `note`: Unity imports are not in the list, and Unity's *Check for updates* will show them as removed from Prism.
- Before renaming, every folder is checked; if a file inside is open, nothing is renamed (`internal`, `details.locked`).
- If Prism still stops halfway, the error lists `renamed` and `remaining` folders. There is no automatic undo.
- **Returns:** `{from, to}`.

### delete_shot
Move a shot's folders into the project's Trash: `<project>/00_Pipeline/Trash/<YYYYMMDD-HHMMSS>_<sequence>-<shot>/global`
(a local-files copy goes to the local project's own `00_Pipeline/Trash`). Nothing is erased; to undo, move the folder back.
**Arguments:** `entity` (shot), `confirm`. The preview lists `dependents` and the Unity `note`, like `rename`. If a file inside is
open, nothing moves. **Returns:** `{deleted, trash, folders}`.
