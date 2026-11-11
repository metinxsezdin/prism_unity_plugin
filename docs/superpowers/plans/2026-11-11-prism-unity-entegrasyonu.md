# Prism ↔ Unity Entegrasyonu — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prism Pipeline 2 için bir Unity app eklentisi. Prism ürünlerini Unity'ye versiyonlu import eder ve günceller, Unity sahnelerini Prism'de versiyonlar, turntable ve serbest playblast'leri Prism'e yazar. Tüm işlemler hem Unity menüsünden hem de Claude'dan (Unity MCP), pencere açmadan yapılabilir.

**Architecture:** İki parçadan oluşur.
- **Prism tarafı:** Ayrı bir süreçte çalışan Python app eklentisi (`Unity/Scripts`, Prism'in `PluginEmpty` şablonundan türetilir).
- **Unity tarafı:** Editor-only bir UPM paketi (`Unity/UnityPackage/com.prism.unity`).

İki taraf `127.0.0.1` üzerinde, token'lı ve satır başına bir JSON mesajlı bir protokolle iki yönlü konuşur. Yalnızca tanımlı komutlar kabul edilir. Unity tarafındaki tüm işlemler tek bir `PrismApi` katmanından geçer. Menü, Prism'den gelen komutlar ve MCP aynı kodu çağırır.

**Tech Stack:**
- Prism 2.1.2.1: gömülü Python 3.13 ve qtpy. Testler stdlib `unittest` ile.
- Unity `6000.5.6f1`, URP, C#, `com.unity.nuget.newtonsoft-json`, Unity Test Framework (EditMode).
- Blender 4.5 (test FBX'lerini üretmek için).
- Unity MCP relay (`~/.unity/relay/relay_win.exe`).

**Spec:** `docs/superpowers/specs/2026-11-11-prism-unity-entegrasyonu-design.md`

## Global Constraints

- Unity sürümü `6000.5.6f1`, render pipeline URP. Platform yalnızca Windows.
- Prism kurulumu `C:\Program Files\Prism2`, Python `C:\Program Files\Prism2\Python313\python.exe`, FFmpeg `C:\Program Files\Prism2\Tools\FFmpeg`. Prism API'leri kurulu sürümde (`C:\Program Files\Prism2\Scripts`) doğrulanır. GitHub 2.1.4.3 kaynağı yalnızca referans.
- Prism eklenti adı `Unity`. Sahne formatı `[".unity"]`. Unity paket adı `com.prism.unity`. C# assembly `Prism.Unity.Editor`, namespace `Prism.Unity.Editor`.
- Bağlantı yalnızca `127.0.0.1` üzerinden kurulur. Her istek oturum token'ı taşır. Tanımsız komut `unknown_command` ile reddedilir. Hiçbir komut gelen kodu çalıştırmaz.
- `interactive: false` olan (Claude'dan gelen) hiçbir işlem pencere açmaz. Eksik bilgi `needs_input`, onay gereken durum `needs_confirmation` hatası olarak döner.
- Import yolu `Assets/Prism/<entity yolu>/<ürün>/<ürün><uzantı>`. Yolda versiyon numarası yer almaz. Güncelleme aynı dosyanın üstüne yazar, `.meta` ve GUID korunur.
- Proje içi kayıtlar `ProjectSettings/PrismUnity/` altında, ürün ve sahne başına ayrı küçük JSON dosyaları olarak tutulur (Git ile paylaşılır).
- "Latest" = Prism'in `getLatestVersionFromProduct(..., includeMaster=True)` sonucu.
- Unity sahneleri varsayılan olarak asset entity altında, `Unity` departmanında tutulur. Shot entity'leri de desteklenir.
- Turntable modelin kendi asset'ine yazılır. Serbest playblast sahnenin bağlı olduğu entity'ye yazılır.
- Unity'nin ana thread'i hiçbir zaman ağ beklemesiyle bloklanmaz. Her çağrının zaman aşımı vardır (varsayılan 10 sn, playblast 600 sn).

## Review Focus

1. **Prism kapalıyken, açılırken ya da çökmüşken Unity'den komut gelmesi:** Unity donmamalı. Prism kapalıysa başlatılmalı, en fazla 60 sn içinde ya cevap dönmeli ya da `prism_unavailable` hatası. Test: Task 4.
2. **Aynı anda iki Unity editörünün (iki farklı projenin) açık olması:** Her proje kendi Prism örneğine ve kendi portlarına bağlanmalı, istekler birbirine karışmamalı. Test: Task 3.
3. **Boşluk veya Türkçe karakter içeren yollar** (`G:\Shared drives\...`, `Çay Bardağı`): Import, sahne kaydı ve playblast sorunsuz çalışmalı. Test: Task 6 ve Task 10.
4. **Unity'de script derlemesi (domain reload) olması ya da Play Mode'da olunması:** Sunucu aynı portta yeniden ayağa kalkmalı. Play Mode'da sahne veya asset değiştiren komutlar `unity_busy` ile reddedilmeli. Test: Task 2.
5. **Kaynak dosyanın erişilemez olması** (ağ sürücüsü `M:` bağlı değil, versiyon silinmiş): Açık bir hata dönmeli, `Assets/` içindeki mevcut dosyaya dokunulmamalı. Test: Task 6.

---

## Dosya Yapısı

```
prism_unity_plugin/                      (git repo kökü)
├─ Unity/                                Prism app eklentisi kökü (pluginDirectory)
│  ├─ Scripts/
│  │  ├─ Prism_Unity_init.py / _init_unloaded.py / _Variables.py
│  │  ├─ Prism_Unity_Functions.py        Prism app hook'ları → UnityClient
│  │  ├─ Prism_Unity_Integration.py      Unity projesine paketi kur/kaldır
│  │  ├─ Prism_Unity_externalAccess_Functions.py
│  │  ├─ Prism_Unity_Launcher.py         Unity'nin başlattığı süreç girişi
│  │  └─ unity_bridge/
│  │     ├─ protocol.py                  mesaj biçimi, hata kodları
│  │     ├─ unity_client.py              Prism → Unity çağrıları
│  │     ├─ command_server.py            Unity → Prism dinleyici
│  │     ├─ headless.py                  pencere bastırma bağlamı
│  │     ├─ commands.py                  Prism tarafı komut uygulamaları
│  │     ├─ manifest.py                  Packages/manifest.json düzenleme
│  │     └─ dialogs.py                   Playblast ayar penceresi (Qt)
│  └─ UnityPackage/com.prism.unity/
│     ├─ package.json
│     ├─ Documentation~/CLAUDE_TOOLS.md
│     ├─ Editor/Prism.Unity.Editor.asmdef
│     │  ├─ Bridge/   Protocol.cs, CommandRegistry.cs, CommandServer.cs,
│     │  │            MainThreadDispatcher.cs, PrismClient.cs, PrismSession.cs, PrismProcess.cs
│     │  ├─ Project/  ProjectBinding.cs, PrismEntity.cs
│     │  ├─ Import/   ImportRecord.cs, ProductImporter.cs, HierarchyDiff.cs
│     │  ├─ Scenes/   SceneBinding.cs, SceneVersioning.cs
│     │  ├─ Playblast/ FrameCapture.cs, TurntableRig.cs, PlayblastRunner.cs
│     │  ├─ Api/      PrismApi.cs, UnityCommands.cs (Prism'in çağırdığı handler'lar)
│     │  ├─ Menu/     PrismMenu.cs
│     │  └─ Mcp/      PrismMcpTools.cs
│     └─ Tests/Editor/ Prism.Unity.Editor.Tests.asmdef, *Tests.cs, Fixtures~/
├─ protocol/fixtures/*.json              iki dilin ortak protokol örnekleri
├─ tests/python/                         unittest (unit) + integration/ (gerçek Prism)
├─ fixtures/make_fbx.py                  Blender ile test FBX üretimi
├─ tools/  run_py_tests.ps1, run_unity_tests.ps1, deploy_dev.ps1, make_test_prism_project.py
├─ TestProject/                          Unity 6000.5.6f1 URP test projesi
└─ docs/
```

## Ortak Arayüzler (tüm görevler bunlara uyar)

**Protokol (v1):** UTF-8 kodlu, her satırda bir JSON mesajı (`\n` ile biter).
- İstek: `{"v":1,"id":"<uuid>","token":"<oturum>","cmd":"<ad>","args":{...},"interactive":true|false}`
- Başarılı cevap: `{"v":1,"id":"<aynı>","ok":true,"result":<json>}`
- Hata cevabı: `{"v":1,"id":"<aynı>","ok":false,"error":{"code":"<kod>","message":"<insan için>","details":{...}}}`
- Hata kodları: `unknown_command`, `bad_token`, `bad_request`, `bad_args`, `needs_input`, `needs_confirmation`, `prism_unavailable`, `unity_busy`, `missing_package`, `source_unavailable`, `timeout`, `internal`.

**Entity:** Prism'in kendi dict biçimi kullanılır.
- Asset için `{"type":"asset","asset_path":"Props/Lotus"}`.
- Shot için `{"type":"shot","sequence":"sq01","shot":"sh010"}`.

**Oturum dosyası:** `Library/PrismUnity/session.json` içeriği `{"unityPort":int,"prismPort":int,"token":str,"unityPid":int}`. Library klasöründe durur, Git'e girmez.

**Prism sürecinin aldığı ortam değişkenleri:** `PRISM_UNITY_PORT`, `PRISM_UNITY_PRISM_PORT`, `PRISM_UNITY_TOKEN`, `PRISM_UNITY_PID`, `PRISM_UNITY_PROJECT` (Unity proje kökü), `PRISM_UNITY_PRISM_PROJECT` (Prism `pipeline.json` yolu).

**Unity → Prism komutları** (`unity_bridge/commands.py` içindeki `PrismCommands`):

| Komut | Parametreler | Ne yapar / ne döner |
|---|---|---|
| `ping` | | `{"prismVersion","checkImportVersions"}` döner |
| `projectBrowser` | | Prism Project Browser'ı açar |
| `settings` | | Prism ayarlarını açar |
| `saveVersion` | `comment=""`, `entity?`, `department?`, `task?`, `createDepartment=false` | `{"path","version"}` döner |
| `saveComment` | | Prism'in yorumlu kayıt penceresini açar |
| `importDialog` | | Prism'in ürün tarayıcısını açar |
| `listProducts` | `entity` | `[{"product","entity"}]` döner |
| `listVersions` | `entity`, `product` | `[{"version","comment","user","date","filepath","location"}]` döner |
| `resolveVersion` | `entity`, `product`, `version="latest"` | `{"version","filepath","location","comment","user"}` döner |
| `checkVersions` | `records:[{"id","entity","product","version"}]` | `[{"id","current","latest"}]` döner |
| `checkVersionsDialog` | | Güncel olmayanları listeleyen Prism penceresini açar |
| `playblastDialog` | | Prism'in Playblast ayar penceresini açar |
| `playblastTarget` | `entity`, `task`, `extension`, `comment=""` | `{"path","version"}` döner |
| `playblastDone` | `path`, `entity`, `task` | Medyayı Prism'e kaydeder, `{"ok"}` döner |

**Prism → Unity komutları** (C# `UnityCommands`, ayrıca `PrismApi` içinde public):

| Komut | Parametreler | Ne yapar / ne döner |
|---|---|---|
| `getPid` | | `int` döner |
| `getAppVersion` | | `"6000.5.6f1"` gibi bir string döner |
| `getProjectInfo` | | `{"projectPath","productGuid"}` döner |
| `getSceneBinding` | | `SceneBinding` ya da `null` döner |
| `bindScene` | `entity`, `department`, `task` | `SceneBinding` döner |
| `saveSceneTo` | `path` | Önce çalışma sahnesini kaydeder, sonra `path`'e kopyalar. `{"workingPath"}` döner |
| `openSceneFrom` | `path`, `unsaved: "save"\|"discard"\|"abort"`, `sourceProductGuid`, `confirmForeign=false` | `{"workingPath"}` döner |
| `getFrameRange` / `setFrameRange` | `start`, `end` | Değerler oturum ayarı olarak tutulur. Playblast'in varsayılan aralığı budur |
| `getFPS` / `setFPS` | `fps` | Aynı şekilde oturum ayarı |
| `importProduct` | `entity`, `product`, `version="latest"`, `confirm=false` | `ImportResult` döner |
| `updateProduct` | `recordId`, `version="latest"`, `confirm=false` | `ImportResult` döner |
| `listImported` | | `ImportRecord[]` döner |
| `listCameras` | | `[{"name","path"}]` döner |
| `playblast` | `PlayblastRequest` | `PlayblastResult` döner |

---

## Milestone A — Temel: köprü, eklenti iskeleti, kurulum

### Task 1: Repo, ortam ve ortak protokol

**Files:**
- Create: `.gitignore`, `.gitattributes`, `tools/run_py_tests.ps1`, `tools/run_unity_tests.ps1`
- Create: `Unity/Scripts/unity_bridge/__init__.py`, `Unity/Scripts/unity_bridge/protocol.py`
- Create: `Unity/UnityPackage/com.prism.unity/package.json`, `Editor/Prism.Unity.Editor.asmdef`, `Editor/Bridge/Protocol.cs`
- Create: `Unity/UnityPackage/com.prism.unity/Tests/Editor/Prism.Unity.Editor.Tests.asmdef`, `Tests/Editor/ProtocolTests.cs`
- Create: `protocol/fixtures/request_ping.json`, `response_ok.json`, `response_error.json`
- Create: `tests/python/test_protocol.py`
- Create: `TestProject/` (Unity projesi)

**Interfaces:**
- Produces (Python): Aşağıdaki fonksiyonlar `protocol.py` içinde.
  - `encode(msg: dict) -> bytes`
  - `decode(line: bytes) -> dict`. Geçersizse `BridgeError("bad_request")` fırlatır.
  - `make_request(cmd: str, args: dict | None, token: str, interactive: bool) -> dict`
  - `ok(id: str, result) -> dict`
  - `err(id: str, code: str, message: str, details: dict | None = None) -> dict`
  - `ERROR_CODES: frozenset[str]`
  - `class BridgeError(Exception)`, alanları `code`, `message`, `details`
- Produces (C#): Aşağıdaki tipler `Protocol.cs` içinde.
  - `PrismRequest { int V; string Id; string Token; string Cmd; JObject Args; bool Interactive }`
  - `PrismResponse { int V; string Id; bool Ok; JToken Result; PrismError Error }`
  - `PrismError { string Code; string Message; JObject Details }`
  - `static class ErrorCodes` (Python'la aynı string sabitler)
  - `class PrismCommandException(string code, string message, JObject details = null) : Exception`
  - `static class LineCodec { byte[] Encode(object msg); PrismRequest DecodeRequest(string line); PrismResponse DecodeResponse(string line) }`

- [ ] **Step 1: Ortamı kur**
  - `git init` ile repoyu başlat.
  - `.gitignore` dosyasına Unity `Library/`, `Temp/`, `Logs/`, `UserSettings/` ve Python `__pycache__/` girişlerini ekle.
  - `.gitattributes` dosyasına `*.fbx`, `*.abc`, `*.png` için `filter=lfs diff=lfs merge=lfs -text` ekle.
  - `unity:unity-cli` skill'ini kullanarak Unity `6000.5.6f1`'i kur. `TestProject/` klasörünü URP şablonundan oluştur.
  - `TestProject/Packages/manifest.json` dosyasına şunları ekle: `"com.prism.unity": "file:../../Unity/UnityPackage/com.prism.unity"` ve `"testables": ["com.prism.unity"]`.
  - `package.json` dosyasında şunlar olmalı: `"name":"com.prism.unity"`, `"unity":"6000.5"`, `"dependencies":{"com.unity.nuget.newtonsoft-json":"3.2.1"}`.
  - Beklenen sonuç: `TestProject` batch modda hatasız açılır.
- [ ] **Step 2: Test çalıştırıcılarını yaz**
  - `tools/run_py_tests.ps1 [-Pattern test_*.py]` şunu çalıştırır: `& "C:\Program Files\Prism2\Python313\python.exe" -m unittest discover -s tests/python -p $Pattern -v`.
  - `tools/run_unity_tests.ps1 [-Filter X] [-Category Y]` şunu çalıştırır: `Unity.exe -batchmode -projectPath TestProject -runTests -testPlatform EditMode -testResults TestResults/editmode.xml -logFile TestResults/editmode.log`. Bitince XML'deki toplam/başarılı/başarısız sayısını yazdırır. Başarısız test varsa çıkış kodu 1 olur.
  - Not: `-runTests` ile birlikte `-quit` verilmez.
- [ ] **Step 3: Ortak protokol örneklerini ve iki dildeki başarısız testleri yaz**
  - Python testleri:
    - `test_roundtrip_fixtures`: her fixture için `decode(encode(x)) == x` olmalı.
    - `test_decode_rejects_non_json`: `decode(b"hello\n")` çağrısı `BridgeError` fırlatmalı, `code == "bad_request"` olmalı.
    - `test_decode_rejects_missing_cmd`
    - `test_err_has_known_code`: `err("1","nope","x")` çağrısı `ValueError` fırlatmalı.
  - C# testleri:
    - `DecodesSharedFixtures`: `protocol/fixtures` dosyaları okunur. Beklenen değerler `Cmd == "ping"`, `Ok == true`, `Error.Code == "needs_input"`.
    - `EncodeEndsWithSingleNewline`
    - `DecodeRejectsGarbage`: `PrismCommandException` fırlatmalı, `Code == "bad_request"` olmalı.
- [ ] **Step 4: Testleri çalıştır, başarısız olduklarını doğrula**
  - `tools/run_py_tests.ps1 -Pattern test_protocol.py` → FAIL (`ModuleNotFoundError`).
  - `tools/run_unity_tests.ps1 -Filter ProtocolTests` → derleme hatası ya da FAIL.
- [ ] **Step 5: `protocol.py` ve `Protocol.cs` dosyalarını uygula.** C# tarafında Newtonsoft `JsonConvert` kullan, alan adları camelCase olsun.
- [ ] **Step 6: Testleri tekrar çalıştır, geçtiklerini doğrula** (iki komut da PASS).
- [ ] **Step 7: Commit** — `git add -A` ve ardından `git commit -m "feat: repo scaffold and shared bridge protocol"`.

### Task 2: Unity komut sunucusu ve ana thread dağıtıcısı

**Files:**
- Create: `Editor/Bridge/CommandRegistry.cs`, `Editor/Bridge/CommandServer.cs`, `Editor/Bridge/MainThreadDispatcher.cs`, `Editor/Bridge/PrismSession.cs`
- Test: `Tests/Editor/CommandServerTests.cs`

**Interfaces:**
- Consumes: Task 1'deki `LineCodec`, `PrismCommandException` ve `ErrorCodes`.
- Produces:
  - `delegate JToken CommandHandler(JObject args, CommandContext ctx)`
  - `class CommandContext { bool Interactive }`
  - `static class CommandRegistry`:
    - `void Register(string cmd, CommandHandler h, bool mutatesProject)`
    - `bool TryGet(string cmd, out CommandHandler h, out bool mutatesProject)`
  - `class CommandServer`:
    - `CommandServer(string token)`, `int Start(int preferredPort = 0)` (seçtiği portu döner), `void Stop()`, `int Port`
    - Yalnızca `IPAddress.Loopback` üzerinde dinler.
  - `static class MainThreadDispatcher`:
    - `Task<T> Run<T>(Func<T> fn, TimeSpan timeout)`
    - `EditorApplication.update` ile pompalanır.
  - `static class PrismSession`:
    - `SessionInfo Current`, `SessionInfo EnsureStarted()`, `void Shutdown()`
    - `class SessionInfo { int UnityPort; int PrismPort; string Token; int UnityPid }`
    - `[InitializeOnLoad]` ile her domain reload'dan sonra `session.json` dosyasındaki aynı port ve token ile sunucuyu yeniden başlatır.

- [ ] **Step 1: Başarısız testleri yaz.** Testler `[UnityTest]` (IEnumerator) şeklinde. Her test gerçek bir TCP istemcisiyle bağlanır.
  - `PingCommandRespondsOk`: bir test komutu `ping` kaydedilir. Cevapta `Ok == true` olmalı.
  - `RejectsWrongToken`: `Error.Code == "bad_token"` olmalı.
  - `RejectsUnknownCommand`: `Error.Code == "unknown_command"` olmalı.
  - `HandlerRunsOnMainThread`: handler içinde `Thread.CurrentThread.ManagedThreadId` kaydedilir. Bu değer testin ana thread id'sine eşit olmalı.
  - `ListensOnLoopbackOnly`: makinenin loopback dışı bir IPv4 adresine bağlanma denemesi başarısız olmalı.
  - `MutatingCommandRejectedInPlayMode`: `EditorApplication.isPlayingOrWillChangePlaymode` bir test kancasıyla true yapılır. Cevapta `unity_busy` olmalı.
  - `HandlerExceptionBecomesError`: handler `PrismCommandException("needs_input", ...)` fırlatır. Cevapta `Error.Code == "needs_input"` olmalı ve sunucu çalışmaya devam etmeli.
  - `SessionFileRoundTrip`: `EnsureStarted()` çağrısından sonra `Library/PrismUnity/session.json` içindeki port, `CommandServer.Port` ile aynı olmalı.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.** `tools/run_unity_tests.ps1 -Filter CommandServerTests` → FAIL.
- [ ] **Step 3: Uygula.**
  - Sunucu her bağlantıyı bir arka plan thread'inde okur. Handler'ı `MainThreadDispatcher` ile ana thread'de çalıştırır.
  - Ana thread hiçbir zaman ağ okuması beklemez.
  - Varsayılan zaman aşımı 10 sn. İstekte `args._timeoutSec` varsa (en fazla 600) o kullanılır.
  - Play Mode kontrolü için `PrismSession.PlayModeOverride` test kancası eklenir.
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat(unity): loopback command server with main-thread dispatch`.

### Task 3: Prism tarafı köprü: istemci, dinleyici, pencere bastırma, tek örnek

**Files:**
- Create: `Unity/Scripts/unity_bridge/unity_client.py`, `command_server.py`, `headless.py`
- Test: `tests/python/test_unity_client.py`, `tests/python/test_command_server.py`, `tests/python/test_headless.py`

**Interfaces:**
- Consumes: Task 1'deki `protocol.py`.
- Produces:
  - `class UnityClient(port: int, token: str, timeout: float = 10.0)` ve `.call(cmd: str, args: dict | None = None, interactive: bool = False, timeout: float | None = None) -> Any`.
    - Hata cevabında aynı kodla `BridgeError` fırlatır.
    - Bağlantı kurulamazsa `BridgeError("timeout")` ya da `BridgeError("internal")` fırlatır.
  - `class CommandServer(port: int, token: str, handle: Callable[[dict], dict], run_on_main: Callable[[Callable[[], dict]], dict])`, metotları `.start() -> None` ve `.stop() -> None`. Yalnızca `127.0.0.1` üzerinde dinler.
  - `headless.py`:
    - `@contextmanager headless(core)`: Bağlam boyunca `core.prismArgs` listesine `"silent"` ekler. `core.popup` ve `core.popupQuestion` fonksiyonlarını, ilk çağrıda `BridgeError("needs_input", <pencere metni>)` fırlatan sarmalayıcılarla değiştirir. Çıkışta her şeyi geri yükler.
    - `def instance_key(unity_project_path: str) -> str`: Normalize edilmiş, küçük harfli mutlak yolun sha1 değerinin ilk 16 karakteri.

- [ ] **Step 1: Başarısız testleri yaz.**
  - `test_call_returns_result`: Python'da sahte bir Unity sunucusu (`socketserver` thread'i) `ok` cevabı verir. Sonuç döndürülen değere eşit olmalı.
  - `test_call_raises_bridge_error_with_code`: Sahte sunucu `needs_confirmation` cevabı verir. Fırlatılan hatada `e.code == "needs_confirmation"` olmalı.
  - `test_call_times_out`: Sahte sunucu hiç cevap vermez, `timeout=0.5`. `code == "timeout"` olmalı ve süre 2 sn'nin altında kalmalı.
  - `test_server_rejects_bad_token`
  - `test_server_rejects_unknown_command`: `handle`, `unknown_command` hatası döner.
  - `test_server_binds_loopback_only`
  - `test_headless_popup_raises_needs_input`: Sahte bir `core` nesnesi kullanılır (`prismArgs=[]`, `popup` ve `popupQuestion` var). Bağlam içinde `core.popup("Did you save it using Prism?")` çağrısı `BridgeError` fırlatmalı, `code == "needs_input"` olmalı ve mesaj pencere metnini içermeli. Bağlamdan çıkınca `"silent" not in core.prismArgs` olmalı ve `popup` orijinal fonksiyon olmalı.
  - `test_headless_restores_on_exception`
  - `test_instance_key_differs_per_project`: `instance_key("C:/A")` ile `instance_key("C:/B")` farklı olmalı. `instance_key("C:/A/")` ile `instance_key("c:\\a")` aynı olmalı.
  - `test_two_clients_two_servers_no_crosstalk` (Review Focus 2): İki sahte Unity sunucusu ve iki istemci kullanılır. Her istemci yalnızca kendi sunucusunun cevabını almalı.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.** `tools/run_py_tests.ps1` → FAIL.
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat(prism): bridge client, listener, headless context`.

### Task 4: Prism app eklentisi iskeleti, Prism süreci başlatıcı ve Unity menüsü

**Files:**
- Create: `Unity/Scripts/Prism_Unity_init.py`, `Prism_Unity_init_unloaded.py`, `Prism_Unity_Variables.py`, `Prism_Unity_Functions.py`, `Prism_Unity_externalAccess_Functions.py`, `Prism_Unity_Launcher.py`
- Create: `Unity/Scripts/unity_bridge/commands.py` (bu görevde yalnızca `ping`, `projectBrowser`, `settings`)
- Create: `Editor/Bridge/PrismClient.cs`, `Editor/Bridge/PrismProcess.cs`, `Editor/Project/ProjectBinding.cs`, `Editor/Project/PrismEntity.cs`, `Editor/Api/UnityCommands.cs`, `Editor/Api/PrismApi.cs`, `Editor/Menu/PrismMenu.cs`
- Create: `tools/deploy_dev.ps1`
- Test: `tests/python/test_plugin_functions.py`, `tests/python/test_commands_dispatch.py`, `Tests/Editor/PrismProcessTests.cs`, `Tests/Editor/E2E/BridgeE2ETests.cs`

**Interfaces:**
- Consumes: Task 2 (`CommandRegistry`, `PrismSession`) ve Task 3 (`UnityClient`, `CommandServer`, `headless`).
- Produces (Python):
  - `class PrismCommands(core, unity: UnityClient)` ve `.dispatch(request: dict) -> dict`.
    - `interactive == False` ise metodu `headless(core)` içinde çalıştırır.
    - Bilinmeyen komutta `unknown_command` döner.
    - Komut adları "Ortak Arayüzler" tablosundaki gibi, metot adları da birebir aynı.
  - `Prism_Unity_Variables`: `pluginName="Unity"`, `pluginType="App"`, `appShortName="Unity"`, `appType="3d"`, `hasQtParent=False`, `sceneFormats=[".unity"]`, `outputFormats=[".fbx",".obj",".abc"]`, `platforms=["Windows"]`.
  - `Prism_Unity_Functions`: Prism'in beklediği hook'ları uygular.
    - `getCurrentFileName`, `getSceneExtension`, `saveScene`, `openScene`, `getFrameRange`, `setFrameRange`, `getFPS`, `setFPS`, `getAppVersion`.
    - `getCurrentFileName`, `saveScene` ve `openScene` bu görevde `NotImplementedError` fırlatır, Task 10 ve 11'de doldurulur.
    - `self.unity: UnityClient` nesnesini ortam değişkenlerinden kurar.
  - `Prism_Unity_Launcher.py` komut satırı: `python Prism_Unity_Launcher.py <ilk komut>`. Gerisi ortam değişkenlerinden okunur. Akış:
    1. `instance_key` ile Windows mutex'i dener: `Global\PrismUnity_<key>`.
    2. Mutex zaten varsa çıkar.
    3. Yoksa `PrismCore.create(app="Unity", prismArgs=["loadProject","noProjectBrowser"])` ile Prism'i başlatır.
    4. Prism'in aktif projesi `PRISM_UNITY_PRISM_PROJECT` değilse `pcore.changeProject(configPath)` çağırır.
    5. `CommandServer` dinleyicisini `PRISM_UNITY_PRISM_PORT` üzerinde başlatır.
    6. 5 sn'de bir `PRISM_UNITY_PID` sürecini kontrol eder. Süreç kapandıysa `QApplication.quit()` çağırır.
- Produces (C#):
  - `class PrismClient` ve `static Task<JToken> SendAsync(string cmd, JObject args, bool interactive, TimeSpan? timeout = null)`.
    - Gerekirse önce `PrismProcess.EnsureRunning()` çağırır.
    - Prism hazır olana kadar 60 sn boyunca `ping` dener. Hazır olmazsa `PrismCommandException("prism_unavailable")` fırlatır.
  - `static class PrismProcess`:
    - `ProcessStartInfo BuildStartInfo(SessionInfo s, ProjectBinding b, string prismRoot, string pluginDir, string firstCmd)`
    - `bool IsRunning()`, `void EnsureRunning()`
  - `class ProjectBinding { string PrismProjectConfig; static ProjectBinding Load(); void Save() }`. Dosya: `ProjectSettings/PrismUnity/project.json`.
  - Makineye özel yollar EditorPrefs'te tutulur. `PrismUnity.PrismRoot` varsayılanı `C:\Program Files\Prism2`. `PrismUnity.PluginDir` değeri paketin `package.json` konumundan iki üst klasör (`Unity/`).
  - `class PrismEntity { string Type; string AssetPath; string Sequence; string Shot; JObject ToJson(); static PrismEntity FromJson(JObject) }`. JSON alan adları `type`, `asset_path`, `sequence`, `shot`.
  - `PrismMenu`: `Prism/` menüsü altında şu öğeler: `Project Browser`, `Save Version`, `Save Comment...`, `Import...`, `Check for New Versions...`, `Playblast...`, `Prism Settings...`. Her öğe ilgili Unity → Prism komutunu `interactive:true` ile gönderir.
  - `UnityCommands.RegisterAll()`: Bu görevde `getPid`, `getAppVersion`, `getProjectInfo`, `getFrameRange`, `setFrameRange`, `getFPS`, `setFPS` komutlarını kaydeder.

- [ ] **Step 1: Başarısız testleri yaz.**
  - Python:
    - `test_dispatch_unknown_command`
    - `test_dispatch_headless_wraps_noninteractive`: Sahte bir core ile `ping` komutu `interactive:false` olarak gönderilir. Çalışırken `"silent" in core.prismArgs` olmalı.
    - `test_getFPS_calls_unity`: Sahte `UnityClient` kullanılır. `plugin.getFPS(None)` çağrısı `unity.call("getFPS")` sonucunu dönmeli.
    - `test_variables`: `sceneFormats == [".unity"]` ve `pluginName == "Unity"` olmalı.
  - C#:
    - `StartInfoHasEnvAndArgs`: `BuildStartInfo` sonucunda `FileName` `...\Python313\python.exe` ile bitmeli. Argümanlar `Prism_Unity_Launcher.py` yolunu ve `firstCmd` değerini içermeli. Ortam değişkenleri `PRISM_UNITY_PORT`, `PRISM_UNITY_PRISM_PORT`, `PRISM_UNITY_TOKEN`, `PRISM_UNITY_PID`, `PRISM_UNITY_PROJECT`, `PRISM_UNITY_PRISM_PROJECT`'in hepsini içermeli. Yollarda boşluk olsa bile argümanlar tırnaklı olmalı.
    - `SendAsyncFailsFastWhenPrismMissing` (Review Focus 1): `PrismRoot` var olmayan bir klasöre ayarlanır. 2 sn içinde `prism_unavailable` hatası gelmeli ve editör bloklanmamalı (test `[UnityTest]`, kare sayısı ilerlemeli).
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula** (iki çalıştırıcıyla da).
- [ ] **Step 3: Python iskeletini ve launcher'ı uygula.** `PluginEmpty` dosyalarını kurulu Prism'den (`C:\Program Files\Prism2\Plugins\Apps\PluginEmpty`) kopyala ve sınıf adlarını `Unity` olarak değiştir. Launcher'da After Effects'in `Prism_AfterEffects_MenuTools.py` dosyasındaki yapıyı izle: `QMetaObject.invokeMethod(..., Qt.QueuedConnection)` ile ana thread'e aktarım, `setQuitOnLastWindowClosed(False)`.
- [ ] **Step 4: C# tarafını uygula.** `UnityCommands.RegisterAll` çağrısı `PrismSession`'ın `[InitializeOnLoad]` akışında yapılır.
- [ ] **Step 5: `tools/deploy_dev.ps1` dosyasını yaz.** Script `%USERPROFILE%\Documents\Prism2\PluginPaths.json` içindeki `plugins` listesine `<repo>\Unity` yolunu ekler. Aynı yol zaten varsa ikinci kez eklemez. Dosyanın yedeğini `PluginPaths.json.bak` adıyla alır.
- [ ] **Step 6: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 7: E2E testi yaz ve çalıştır.**
  - Test `[Category("E2E")]` olarak işaretlenir: `PingRealPrism`. Gerçek Prism süreci başlatılır, `PrismClient.SendAsync("ping")` çağrısının cevabında `prismVersion` ve `checkImportVersions` alanları olmalı. Test bitince Prism süreci kapatılır.
  - Ön koşullar: `tools/deploy_dev.ps1` çalıştırılmış olmalı, `ProjectBinding` test Prism projesini göstermeli (Task 5'ten önce elle ayarlanır).
  - Çalıştırma: `tools/run_unity_tests.ps1 -Category E2E -Filter PingRealPrism` → PASS.
- [ ] **Step 8: Elle doğrula.** TestProject'i aç, `Prism > Project Browser` seç. Prism'in Project Browser penceresi bağlı proje ile açılmalı. Unity'yi kapat, Prism süreci 10 sn içinde kapanmalı.
- [ ] **Step 9: Commit** — `feat: Prism Unity plugin skeleton, launcher and Prism menu`.

### Task 5: Prism ayarlarından Unity projesine kurulum ve test Prism projesi

**Files:**
- Create: `Unity/Scripts/unity_bridge/manifest.py`, `Unity/Scripts/Prism_Unity_Integration.py`
- Create: `tools/make_test_prism_project.py`, `fixtures/make_fbx.py`
- Create: `Unity/UnityPackage/com.prism.unity/Tests/Editor/Fixtures~/lotus_v1.fbx`, `lotus_v2.fbx`, `lotus_v3_renamed.fbx`
- Test: `tests/python/test_manifest.py`

**Interfaces:**
- Produces:
  - `manifest.py`:
    - `is_unity_project(path: str) -> bool`: `ProjectSettings/ProjectVersion.txt` ve `Packages/manifest.json` var mı diye bakar.
    - `add_package(project_path: str, package_dir: str) -> bool`: `"com.prism.unity": "file:<package_dir mutlak yolu, / ayraçlı>"` girişini ekler ya da günceller. Manifest'teki diğer girişlere ve sıralarına dokunmaz.
    - `remove_package(project_path: str) -> bool`
    - `write_project_binding(project_path: str, prism_project_config: str) -> None`: `ProjectSettings/PrismUnity/project.json` dosyasını yazar.
  - `Prism_Unity_Integration`: Kullanıcının seçtiği yol Unity proje köküdür. İçerdiği fonksiyonlar `addIntegration(installPath)`, `removeIntegration(installPath)`, `updateInstallerUI`, `installerExecute`. Yapı `PluginEmpty`'deki imzaları izler. `addIntegration` sırasıyla şunları çağırır: `add_package` ve ardından `write_project_binding` (o anki Prism projesiyle).
  - Test FBX'leri `fixtures/make_fbx.py` ile Blender 4.5'te `blender -b -P fixtures/make_fbx.py -- <çıktı klasörü>` komutuyla üretilir:
    - **v1:** `Lotus` kökü altında `Petals` ve `Stem` mesh'leri. Materyalleri `PetalMat` ve `StemMat`.
    - **v2:** Aynı adlar, `Petals` vertex'leri %10 büyütülmüş.
    - **v3_renamed:** `Stem` adı `StemMain` olarak değişmiş, `StemMat` silinmiş.
  - `make_test_prism_project.py` şu komutla çalışır: `Python313\python.exe tools/make_test_prism_project.py <hedef klasör>`. Prism'i UI olmadan başlatır (`PrismCore.create(app="Standalone", prismArgs=["noUI"])`). Sonra şunları yapar:
    1. `projects.createProject(name="PrismUnityTest", path=<hedef>)` ile projeyi oluşturur.
    2. `Props/Lotus`, `Props/Çay Bardağı` ve `Scenes/MeditationRoom` asset'lerini oluşturur.
    3. `products.ingestProductVersion([lotus_vN.fbx], {"type":"asset","asset_path":"Props/Lotus"}, "lotus_model")` ile v1, v2 ve v3_renamed sırasıyla `v0001`, `v0002`, `v0003` olarak yayımlanır.
    4. `Çay Bardağı` için de bir `cay_model v0001` yayımlanır (Review Focus 3).
  - Varsayılan hedef `%USERPROFILE%\PrismUnityTest Project`. Yolda boşluk bilerek bırakıldı.

- [ ] **Step 1: Başarısız testleri yaz** (`test_manifest.py`, geçici klasörde sahte bir Unity projesi kurulur).
  - `test_add_package_preserves_other_entries`: Manifest'te başka bağımlılıklar ve bir `scopedRegistries` alanı vardır. Ekleme sonrası hepsi aynı kalmalı ve yalnızca `com.prism.unity` eklenmiş olmalı.
  - `test_add_package_idempotent`
  - `test_remove_package`
  - `test_rejects_non_unity_folder`: `add_package` çağrısı `ValueError` fırlatmalı.
  - `test_paths_with_spaces_and_turkish_chars`: Proje yolu `.../Wellness Proje Ğüşİ/`. Manifest girişi `file:` ile başlamalı ve `/` ayraçlı olmalı.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: `manifest.py` ve `Prism_Unity_Integration.py` dosyalarını uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Fixture'ları ve test Prism projesini üret.** Blender komutunu, ardından `make_test_prism_project.py` scriptini çalıştır. Beklenen sonuç: Prism Project Browser'da `Props/Lotus` altında `lotus_model` ürünü `v0001`–`v0003` versiyonlarıyla görünür.
- [ ] **Step 6: Elle doğrula.** Prism Settings > DCC apps > Unity ekranından `TestProject` klasörünü seçip kur. `TestProject/Packages/manifest.json` dosyasında girişin oluştuğunu, `ProjectSettings/PrismUnity/project.json` dosyasının test Prism projesini gösterdiğini kontrol et.
- [ ] **Step 7: Commit** — `feat: Prism-side Unity integration installer and test fixtures`.

---

## Milestone B — Import ve güncelleme

### Task 6: İçe aktarım kaydı ve ürün import'u (Unity)

**Files:**
- Create: `Editor/Import/ImportRecord.cs`, `Editor/Import/ProductImporter.cs`
- Test: `Tests/Editor/ProductImporterTests.cs`

**Interfaces:**
- Consumes: Task 4'teki `PrismEntity`.
- Produces:
  - `class ImportRecord`, alanları: `string Id`, `PrismEntity Entity`, `string Product`, `string Version`, `string SourcePath`, `string Location`, `string AssetPath`, `string ImportedBy`, `string ImportedAt`.
    - `Id` biçimi `<entity slug>__<product>`. Slug, `asset_path` içindeki `/` yerine `__`, shot için `<seq>__<shot>`.
    - Kayıt `ProjectSettings/PrismUnity/imports/<Id>.json` dosyasına yazılır.
    - Statik metotlar: `static ImportRecord Load(string id)`, `static IReadOnlyList<ImportRecord> LoadAll()`, `void Save()`.
  - `class ResolvedVersion { string Version; string FilePath; string Location }`
  - `class ImportResult { ImportRecord Record; bool Updated; HierarchyChanges Changes }`. `HierarchyChanges` tipi Task 7'de tanımlanır, bu görevde her zaman `null`.
  - `static class ProductImporter` ve `ImportResult ImportResolved(PrismEntity entity, string product, ResolvedVersion v, bool confirm)`.
    - Hedef yol: `Assets/Prism/<entity yolu>/<product>/<product><ext>`.
    - Önce kaynağın varlığı kontrol edilir. Yoksa `source_unavailable` hatası fırlatılır ve hedefe dokunulmaz.
    - Kaynak önce aynı klasörde `<product><ext>.prismtmp` adıyla kopyalanır, kopya tamamlanınca atomik olarak `File.Replace` ya da `Move` ile yerine konur, sonra `AssetDatabase.ImportAsset` çağrılır.
    - `.abc` dosyası için `com.unity.formats.alembic` yüklü değilse `missing_package` hatası fırlatılır.
    - Desteklenen uzantılar `.fbx`, `.obj` ve `.abc`. Başka bir uzantıda `bad_args` hatası fırlatılır.

- [ ] **Step 1: Başarısız testleri yaz.** Fixture'lar `Fixtures~` klasöründen geçici bir "kaynak" klasöre kopyalanır.
  - `ImportCreatesAssetAndRecord`: `Assets/Prism/Props/Lotus/lotus_model/lotus_model.fbx` dosyası oluşmalı. `ImportRecord.Load("Props__Lotus__lotus_model").Version == "v0001"` olmalı.
  - `UpdateKeepsGuid`: v1'i import et ve GUID'i al, sonra v2'yi import et. GUID aynı kalmalı. Kayıtta `Version == "v0002"` ve `Updated == true` olmalı.
  - `UpdateKeepsMaterialRemap`: v1'i import et. `ModelImporter.AddRemap` ile `PetalMat` adını test projesinde oluşturulan `TestPetal.mat` materyaline eşle. v2'yi import et. Remap hâlâ `TestPetal.mat` olmalı.
  - `UpdateKeepsSceneInstance`: v1'i sahneye yerleştir, sonra v2'yi import et. Sahnedeki nesnenin `PrefabUtility.GetCorrespondingObjectFromSource` sonucu aynı asset GUID'ini göstermeli.
  - `MissingSourceLeavesAssetUntouched` (Review Focus 5): v1'i import et, dosyanın hash'ini al. Var olmayan `M:/yok/lotus.fbx` yolunu import etmeyi dene. `source_unavailable` hatası gelmeli ve hash aynı kalmalı.
  - `AbcWithoutAlembicPackage`: `missing_package` hatası gelmeli.
  - `TurkishAndSpacedNames` (Review Focus 3): Entity `Props/Çay Bardağı`, ürün `cay_model`. Asset doğru yolda oluşmalı, kayıt yazılıp tekrar okunabilmeli.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.** `tools/run_unity_tests.ps1 -Filter ProductImporterTests` → FAIL.
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat(unity): versioned product import with in-place GUID-preserving update`.

### Task 7: Hiyerarşi farkı ve onay kapısı

**Files:**
- Create: `Editor/Import/HierarchyDiff.cs`
- Modify: `Editor/Import/ProductImporter.cs` (güncellemeden önce fark kontrolü eklenir)
- Test: `Tests/Editor/HierarchyDiffTests.cs`

**Interfaces:**
- Produces:
  - `class HierarchyChanges { List<string> RemovedNodes; List<string> AddedNodes; List<string> RemovedMaterials; List<string> AddedMaterials; bool IsBreaking }`. `IsBreaking`, `RemovedNodes` ya da `RemovedMaterials` doluysa true olur.
  - `JObject HierarchyChanges.ToJson()`
  - `static class HierarchyDiff`:
    - `HierarchyChanges Compare(string existingAssetPath, string newSourceFile)`
    - Yeni dosya `Assets/Prism/_staging/<guid>/` klasörüne kopyalanıp import edilir. Node yolları (`Lotus/Stem`) ve materyal adları okunur. Bitince staging klasörü silinir.
  - `ProductImporter.ImportResolved` davranışı: Güncellemede `IsBreaking && !confirm` ise hiçbir şey yazmadan `PrismCommandException("needs_confirmation", "...", changes.ToJson())` fırlatır.

- [ ] **Step 1: Başarısız testleri yaz.**
  - `NoChangesBetweenV1AndV2`: `IsBreaking == false` olmalı ve tüm listeler boş olmalı.
  - `DetectsRenameAndRemovedMaterial`: v1 ile v3_renamed karşılaştırılır. `RemovedNodes` içinde `"Lotus/Stem"`, `AddedNodes` içinde `"Lotus/StemMain"`, `RemovedMaterials` içinde `"StemMat"` olmalı ve `IsBreaking == true` olmalı.
  - `BreakingUpdateNeedsConfirmation`: v1 import edilir, sonra `confirm:false` ile v3 import edilir. `needs_confirmation` hatası gelmeli, `details.removedNodes` içinde `"Lotus/Stem"` olmalı, kayıtta hâlâ `v0001` olmalı ve dosya hash'i değişmemiş olmalı.
  - `BreakingUpdateWithConfirmApplies`: `confirm:true` ile kayıtta `v0003` olmalı.
  - `StagingCleanedUp`: Her testten sonra `Assets/Prism/_staging` klasörü olmamalı.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat(unity): hierarchy diff and confirmation gate on breaking updates`.

### Task 8: Prism tarafı ürün sorguları, versiyon kontrolü ve import penceresi

**Files:**
- Modify: `Unity/Scripts/unity_bridge/commands.py`. Eklenecek komutlar: `listProducts`, `listVersions`, `resolveVersion`, `checkVersions`, `importDialog`, `checkVersionsDialog`.
- Test: `tests/python/test_commands_products.py`, `tests/python/integration/test_products_it.py`

**Interfaces:**
- Consumes:
  - Prism API'leri: `core.products.getProductsFromEntity(entity)`, `core.products.getVersionsFromProduct(entity, product)`, `core.products.getLatestVersionFromProduct(product, entity=entity, includeMaster=True)`, `core.products.getPreferredFileFromVersion(version)`.
  - Unity komutları: `importProduct`, `listImported`.
- Produces: "Ortak Arayüzler" tablosundaki dönüş biçimleri.
  - `resolveVersion(version="latest")` en son versiyonu döner. `"master"` ya da `"v0002"` verilirse o versiyonu döner.
  - Versiyon yoksa ya da dosya bulunamıyorsa `source_unavailable` hatası döner.
  - `importDialog`: Prism'in ürün tarayıcısını açar. Prism'de kendi `ProductBrowser` sınıfını kullan (kurulu Prism'de `Scripts/ProjectScripts` altında bul). Kullanıcı bir versiyon seçince `unity.call("importProduct", {...}, interactive=True)` çağrılır. Unity `needs_confirmation` dönerse fark listesi `core.popupQuestion` ile gösterilir, kullanıcı evet derse `confirm:true` ile tekrar çağrılır.
  - `checkVersionsDialog`: `listImported` → `checkVersions`. Güncel olmayan ürünleri bir Qt listesinde gösterir. "Update" seçilenler için `updateProduct` çağrılır.

- [ ] **Step 1: Başarısız unit testleri yaz** (sahte `core.products` kullanılır).
  - `test_resolve_latest_uses_include_master`: Sahte API'de çağrının `includeMaster=True` ile yapıldığı doğrulanır.
  - `test_resolve_specific_version`
  - `test_resolve_missing_version_source_unavailable`
  - `test_check_versions_marks_outdated`: Kayıtlarda `v0001`, latest `v0003`. Sonuç `[{"id":..., "current":"v0001", "latest":"v0003"}]` olmalı.
  - `test_check_versions_up_to_date_empty`
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Integration testini yaz ve çalıştır.**
  - `tests/python/integration/test_products_it.py` gerçek Prism ve test Prism projesiyle çalışır. `PRISM_UNITY_IT=1` ortam değişkeni yoksa `skipUnless` ile atlanır.
  - `listVersions(Props/Lotus, lotus_model)` sonucu üç versiyon içermeli ve `resolveVersion(latest).version == "v0003"` olmalı.
  - Çalıştırma: `$env:PRISM_UNITY_IT=1; tools/run_py_tests.ps1 -Pattern test_products_it.py` → PASS.
- [ ] **Step 6: Commit** — `feat(prism): product queries, version check and import dialogs`.

### Task 9: Uçtan uca import ve güncelleme (PrismApi, menü, açılış kontrolü)

**Files:**
- Modify: `Editor/Api/PrismApi.cs`, `Editor/Api/UnityCommands.cs`, `Editor/Menu/PrismMenu.cs`
- Create: `Editor/Import/StartupVersionCheck.cs`
- Test: `Tests/Editor/E2E/ImportE2ETests.cs`

**Interfaces:**
- Consumes: Task 6 ve 7 (`ProductImporter`, `ImportRecord`), Task 8'deki Prism komutları.
- Produces (`PrismApi`):
  - `Task<ImportResult> ImportProduct(PrismEntity entity, string product, string version = "latest", bool confirm = false)`: Önce Prism'e `resolveVersion` gönderir, sonra `ProductImporter.ImportResolved` çağırır.
  - `Task<ImportResult> UpdateProduct(string recordId, string version = "latest", bool confirm = false)`
  - `IReadOnlyList<ImportRecord> ListImported()`
  - `Task<JArray> CheckForUpdates()`
  - `Task<JArray> ListProducts(PrismEntity entity)`
  - `Task<JArray> ListVersions(PrismEntity entity, string product)`
  - `UnityCommands` tarafında `importProduct`, `updateProduct` ve `listImported` komutları kaydedilir.
  - `StartupVersionCheck`: `[InitializeOnLoad]` ile çalışır. Editör oturumu başına bir kez, ilk `EditorApplication.delayCall` anında devreye girer. Prism'in `check_import_versions` ayarı true ise ve en az bir import kaydı varsa `checkVersionsDialog` gönderir. Ayar değeri `ping` cevabındaki `checkImportVersions` alanından okunur.

- [ ] **Step 1: E2E testlerini yaz** (`[Category("E2E")]`, gerçek Prism ve test Prism projesiyle).
  - `ImportLatestThenUpdateAfterNewPublish`:
    1. `ImportProduct(Lotus, "lotus_model", "v0001")` çağrılır.
    2. `CheckForUpdates()` sonucunda `latest == "v0003"` olmalı.
    3. `UpdateProduct(id, "v0002")` sonucunda kayıtta `v0002` olmalı.
  - `HeadlessBreakingUpdateReturnsDiff`: `UpdateProduct(id, "v0003", confirm:false)` çağrısı `needs_confirmation` hatası vermeli ve hata detayı `details.removedNodes` içermeli. Bu sırada Prism tarafında hiçbir pencere açılmamalı: Prism'deki test kancası `PRISM_UNITY_FAIL_ON_DIALOG=1`, herhangi bir `QDialog.exec_` çağrısında komutu `internal` hatasıyla düşürür.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.** `tools/run_unity_tests.ps1 -Category E2E -Filter ImportE2ETests` → FAIL.
- [ ] **Step 3: Uygula.** `PRISM_UNITY_FAIL_ON_DIALOG` kancası `Prism_Unity_Launcher.py` içinde `QDialog.exec` ve `QMessageBox.exec` fonksiyonlarını sarmalar ve yalnızca test ortamında etkindir.
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Elle doğrula.** `Prism > Import...` menüsünden lotus v0001'i import et. Unity'yi yeniden aç: "yeni versiyon var" penceresi gelmeli. "Update" seç, materyal ataması korunmalı.
- [ ] **Step 6: Commit** — `feat: end-to-end product import, update and startup version check`.

---

## Milestone C — Unity sahnesi versiyonlama

### Task 10: Sahne bağlama ve Save Version

**Files:**
- Create: `Editor/Scenes/SceneBinding.cs`, `Editor/Scenes/SceneVersioning.cs`
- Modify: `Unity/Scripts/Prism_Unity_Functions.py` (`getCurrentFileName`, `saveScene`), `unity_bridge/commands.py` (`saveVersion`, `saveComment`), `Editor/Api/UnityCommands.cs`, `Editor/Api/PrismApi.cs`
- Test: `Tests/Editor/SceneVersioningTests.cs`, `tests/python/test_scene_save.py`, `Tests/Editor/E2E/SceneE2ETests.cs`

**Interfaces:**
- Produces (C#):
  - `class SceneBinding`, alanları: `string SceneGuid`, `string WorkingPath`, `PrismEntity Entity`, `string Department`, `string Task`, `string LastPrismPath`.
    - Kayıt `ProjectSettings/PrismUnity/scenes/<SceneGuid>.json` dosyasında tutulur.
    - Statik metotlar: `static SceneBinding ForActiveScene()`, `static SceneBinding FindByPrismPath(string prismScenefile)`. İkincisi, aynı Prism görev klasörüne bağlı bağlamayı bulur.
  - `static class SceneVersioning`:
    - `string SaveTo(string prismPath)`: Aktif sahneyi `EditorSceneManager.SaveScene` ile kendi yerine kaydeder. Sonra `.unity` dosyasını `prismPath`'e kopyalar ve `LastPrismPath` alanını günceller. Çalışma yolunu döner.
    - Aktif sahne hiç kaydedilmemişse (`path == ""`) önce `Assets/Scenes/<entity adı>/<task>.unity` yoluna kaydeder.
  - `PrismApi.SaveVersion(string comment, PrismEntity entity = null, string department = null, string task = null, bool createDepartment = false, bool interactive = false) -> Task<JObject>`: Prism'e `saveVersion` komutunu gönderir.
- Produces (Python):
  - `getCurrentFileName()`: Unity'den `getSceneBinding` ister. `LastPrismPath` varsa onu döner. Yoksa `core.generateScenePath(entity, department, task, extension=".unity")` sonucunu döner. Böylece `core.saveScene` bir sonraki versiyonu kendisi hesaplar.
  - `saveScene(origin, filepath, details)`: `unity.call("saveSceneTo", {"path": filepath})` çağırır. Versiyon bilgisine `details["unityProductGuid"]` alanı eklenir. Değer `getProjectInfo` cevabındaki `productGuid` alanından gelir, o da `PlayerSettings.productGUID` değeridir.
  - `PrismCommands.saveVersion(comment="", entity=None, department=None, task=None, createDepartment=False)`. Davranışı:
    1. Bağlama yoksa entity, departman ve görev gerekir. Eksikse `needs_input` hatası döner, detayda `{"missing": [...]}` olur. Etkileşimli modda Prism'in entity/görev seçim penceresi açılır.
    2. Departman varsayılanı `"Unity"`. Departman Prism projesinde yoksa ve `createDepartment` false ise `needs_confirmation` döner. Etkileşimli modda kullanıcıya sorulur. Departman `core.entities.createDepartment` ile oluşturulur.
    3. Bağlama `unity.call("bindScene")` ile kurulur.
    4. `core.saveScene(comment=comment)` çağrılır ve `{"path","version"}` döner.

- [ ] **Step 1: Başarısız testleri yaz.**
  - C#:
    - `SaveToCopiesSceneAndUpdatesBinding`: Geçici bir Prism yolu kullanılır. Yolda dosya oluşmalı, içeriği çalışma sahnesiyle aynı olmalı ve `LastPrismPath` güncellenmiş olmalı.
    - `UnsavedSceneGetsDefaultWorkingPath`
    - `BindingFileIsPerScene`
  - Python (sahte core ve sahte `UnityClient`):
    - `test_first_save_without_target_needs_input`: `details.missing == ["entity","department","task"]` olmalı.
    - `test_missing_department_needs_confirmation`
    - `test_create_department_true_creates_then_saves`
    - `test_get_current_file_name_uses_last_prism_path`
    - `test_save_scene_adds_unity_product_guid`
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.** `getSceneBinding`, `bindScene` ve `saveSceneTo` komutlarını `UnityCommands` içinde kaydet. `saveSceneTo` ve `bindScene` proje değiştiren komutlar olarak işaretlenir (`mutatesProject = true`).
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: E2E testini yaz ve çalıştır.**
  - `SaveVersionHeadlessTwice`: `SaveVersion("ilk", Scenes/MeditationRoom, "Unity", "layout", createDepartment:true)` çağrısının sonucu `version == "v0001"` olmalı. İkinci çağrı `SaveVersion("ikinci")` sonucu `"v0002"` olmalı. Prism projesinde iki `.unity` dosyası ve yorumlu versiyon bilgisi bulunmalı. Hiçbir pencere açılmamalı (`PRISM_UNITY_FAIL_ON_DIALOG=1`).
  - `SaveVersionTurkishEntity` (Review Focus 3): `Props/Çay Bardağı` entity'si ile kayıt başarılı olmalı.
- [ ] **Step 6: Commit** — `feat: Unity scene binding and Prism Save Version`.

### Task 11: Sahne versiyonu açma

**Files:**
- Modify: `Editor/Scenes/SceneVersioning.cs`, `Editor/Api/UnityCommands.cs`, `Unity/Scripts/Prism_Unity_Functions.py` (`openScene`)
- Test: `Tests/Editor/SceneOpenTests.cs`, `tests/python/test_scene_open.py`

**Interfaces:**
- Produces:
  - `SceneVersioning.OpenFrom(string prismPath, string unsaved, string sourceProductGuid, bool confirmForeign) -> string` (çalışma yolunu döner). Davranışı:
    1. Hedef yol `SceneBinding.FindByPrismPath` ile bulunur. Bağlama yoksa `Assets/Scenes/<entity adı>/<task>.unity` kullanılır.
    2. Aktif sahne kirliyse `unsaved` değerine bakılır. `"abort"` ise `needs_confirmation` hatası fırlatılır, detayda `{"reason":"unsaved_changes"}` olur. `"save"` ise sahne kaydedilir, `"discard"` ise değişiklikler atılır.
    3. `sourceProductGuid` boş değilse, `PlayerSettings.productGUID` değerinden farklıysa ve `confirmForeign` false ise `needs_confirmation` fırlatılır, detayda `{"reason":"foreign_project"}` olur.
    4. Dosya kopyalanır, `AssetDatabase.ImportAsset` ve ardından `EditorSceneManager.OpenScene` çağrılır. Bağlama oluşturulur ya da güncellenir.
  - `openScene(origin, filepath, force=False)` (Python):
    - Etkileşimli modda `unsaved` önce `"abort"` olarak gönderilir. `needs_confirmation` gelirse kullanıcıya Kaydet / At / Vazgeç diye sorulur ve seçimle tekrar çağrılır.
    - Etkileşimsiz modda hata olduğu gibi yukarı iletilir.
    - Kaydedilmiş `unityProductGuid` değeri `core.getScenefileData(filepath)` ile okunur ve Unity'ye `sourceProductGuid` parametresi olarak gönderilir. Değer yoksa (eski kayıtlar) boş string gönderilir.

- [ ] **Step 1: Başarısız testleri yaz.**
  - C#:
    - `OpenRestoresVersionIntoWorkingPath`: v1 içinde küp var, v2 içinde küre var. v1 açıldığında sahnede küp olmalı.
    - `DirtySceneAbortNeedsConfirmation`
    - `DirtySceneDiscardOpens`
    - `ForeignProjectNeedsConfirmation`: `sourceProductGuid` başka bir GUID verilir, `details.reason == "foreign_project"` olmalı.
    - `ForeignProjectConfirmedOpens`
    - `EmptySourceGuidOpensWithoutPrompt`
  - Python:
    - `test_open_interactive_asks_on_unsaved`: Sahte `popupQuestion` "Discard" döner. İkinci çağrıda `unsaved == "discard"` olmalı.
    - `test_open_headless_propagates_needs_confirmation`
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Elle doğrula.** Prism Project Browser'dan `MeditationRoom` sahnesinin v0001 versiyonunu aç: Unity'de o versiyon açılmalı.
- [ ] **Step 6: Commit** — `feat: open Prism scene versions into Unity working scenes`.

---

## Milestone D — Playblast

### Task 12: Kare yakalama ve turntable kurulumu (Unity)

**Files:**
- Create: `Editor/Playblast/FrameCapture.cs`, `Editor/Playblast/TurntableRig.cs`
- Test: `Tests/Editor/PlayblastCaptureTests.cs`

**Interfaces:**
- Produces:
  - `static class FrameCapture` ve `void CaptureFrame(Camera cam, int width, int height, string pngPath)`.
    - URP'de `RenderPipeline.SubmitRenderRequest(cam, new RenderPipeline.StandardRequest { destination = rt })` ile bir `RenderTexture`'a render eder. Ardından `ReadPixels` ve `EncodeToPNG` ile PNG yazar.
    - Unity Recorder kullanılmaz (benim kararım: edit modda deterministik çalışması ve ek paket gerektirmemesi için).
  - `sealed class TurntableRig : IDisposable`:
    - Kurucu: `TurntableRig(IReadOnlyList<GameObject> targets, int width, int height)`.
    - Kök nesne `HideFlags.HideAndDontSave` ile oluşturulur. İçinde bir kamera ve üç noktalı ışık (key, fill, rim) bulunur.
    - Hedef objelerin `Renderer.bounds` birleşimine göre kamera konumu ve uzaklığı hesaplanır.
    - `void SetAngle(float degrees)`: Kamera bounds merkezi etrafında döner. **Hedef objelerin transform'larına dokunulmaz.**
    - `Camera Camera`
    - `Dispose()` tüm geçici nesneleri siler.

- [ ] **Step 1: Başarısız testleri yaz.**
  - `CaptureWritesPngOfRequestedSize`: Çıktı dosyası `512x512` olmalı.
  - `TurntableDoesNotDirtySceneOrMoveTargets` (Review Focus 4'ün sahne tarafı): Her şey bittikten sonra şu koşullar sağlanmalı: `scene.isDirty == false`, hedeflerin `position`, `rotation` ve `scale` değerleri öncekiyle aynı, sahnede `HideFlags` taşıyan geçici nesne kalmamış.
  - `TurntableCleansUpOnException`: `SetAngle` içinde bir test kancasıyla istisna atılır. `Dispose` sonrası geçici nesne kalmamalı.
  - `FramesBoundsOfTargets`: Ortadaki kare tamamen arka plan renginde olmamalı. Bu, hedefin kamerada göründüğünü gösterir.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat(unity): frame capture and non-destructive turntable rig`.

### Task 13: Playblast'i Prism'e yazma (turntable ve serbest mod)

**Files:**
- Create: `Editor/Playblast/PlayblastRunner.cs`, `Unity/Scripts/unity_bridge/dialogs.py`
- Modify: `unity_bridge/commands.py` (`playblastTarget`, `playblastDone`, `playblastDialog`), `Editor/Api/UnityCommands.cs` (`listCameras`, `playblast`), `Editor/Api/PrismApi.cs`
- Test: `Tests/Editor/PlayblastRunnerTests.cs`, `tests/python/test_playblast_cmds.py`, `Tests/Editor/E2E/PlayblastE2ETests.cs`

**Interfaces:**
- Produces:
  - `class PlayblastRequest`. Alanları ve varsayılanları:
    - `string Mode` — `"turntable"` ya da `"free"`
    - `string[] TargetPaths` — turntable için. Boşsa Unity'de seçili objeler kullanılır.
    - `string CameraPath` — serbest mod için
    - `int Width = 1920`, `int Height = 1080`, `int Frames = 120`, `int Fps = 30`
    - `string Format` — `"png"` ya da `"mp4"`, varsayılan `"png"`
    - `string Comment`
    - `string Task` — turntable için varsayılan `"Turntable"`, serbest mod için `"Playblast"`
  - `class PlayblastResult { string OutputPath; string Version; int FrameCount }`
  - `PrismApi.Playblast(PlayblastRequest req) -> Task<PlayblastResult>`. Entity seçimi:
    - **Turntable:** İlk hedefin `Assets/Prism/...` altındaki kaynak asset'i bulunur, entity onun `ImportRecord` kaydından alınır. Hedef Prism'den gelmemişse `needs_input` döner, detayda `{"missing":["entity"]}` olur. İstekte `Entity` alanı varsa o kullanılır.
    - **Serbest:** Entity aktif sahnenin `SceneBinding` kaydından alınır. Bağlama yoksa `needs_input` döner.
  - Akış:
    1. Prism'e `playblastTarget(entity, task, extension=".png"|".mp4")` gönderilir. Cevap `{path, version}` olur. Dönen yol kare dizisi şablonudur (Prism'in `####` biçimi).
    2. Kareler bu şablona yazılır: turntable için `SetAngle(360 * i / Frames)`, serbest mod için `Time` ve Timeline/Animator `i / Fps` saniyesine örneklenir. Serbest mod sahnedeki `PlayableDirector` varsa `director.time` ayarlanıp `Evaluate()` ile, yoksa statik kamera olarak çalışır.
    3. `mp4` istenmişse PNG'ler geçici bir klasöre yazılır, `C:\Program Files\Prism2\Tools\FFmpeg` altındaki `ffmpeg.exe` ile `-c:v libx264 -pix_fmt yuv420p -r <fps>` parametreleriyle kodlanır ve geçici klasör silinir.
    4. Son olarak `playblastDone` gönderilir.
  - Zaman aşımı 600 sn.
  - `playblastDialog` (Prism tarafı Qt penceresi, `dialogs.py`): mod, kamera listesi (Unity'den `listCameras`), çözünürlük, kare sayısı, fps, format ve yorum alanları. Tamam'a basılınca `unity.call("playblast", req, interactive=True)` çağrılır.

- [ ] **Step 1: Başarısız testleri yaz.**
  - C#:
    - `TurntableEntityFromImportRecord`: İçe aktarılmış lotus seçiliyken çözümlenen entity `Props/Lotus` olmalı.
    - `TurntableNonPrismTargetNeedsInput`
    - `FreeModeWithoutBindingNeedsInput`
    - `WritesRequestedFrameCount`: Prism tarafı sahte bir `PrismClient` kancasıyla geçici bir yol döner. 12 kare istendiğinde 12 PNG oluşmalı.
  - Python:
    - `test_playblast_target_uses_generate_playblast_path`: Sahte `core.mediaProducts.generatePlayblastPath` fonksiyonunun `entity`, `task="Turntable"` ve `extension=".png"` ile çağrıldığı doğrulanır.
    - `test_playblast_done_registers_media`
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: E2E testini yaz ve çalıştır.**
  - `TurntableAppearsInPrismMedia`: lotus import edilir, `Playblast({Mode:"turntable", Frames:24})` çağrılır. Prism tarafında `core.mediaProducts` ile `Props/Lotus` için `Turntable` medyası `v0001` olarak listelenmeli. `Format:"mp4"` ile tekrar çağrılınca `v0002` altında bir `.mp4` dosyası oluşmalı. Hiçbir pencere açılmamalı.
- [ ] **Step 6: Elle doğrula.** `Prism > Playblast...` menüsünden turntable seç. Sonuç Prism'in medya tarayıcısında oynatılabilmeli.
- [ ] **Step 7: Commit** — `feat: turntable and free playblasts published to Prism`.

---

## Milestone E — Claude (Unity MCP) ve kabul

### Task 14: Unity MCP üzerinden Claude erişimi

**Files:**
- Create: `Editor/Mcp/PrismMcpTools.cs`, `Documentation~/CLAUDE_TOOLS.md`
- Test: `Tests/Editor/PrismMcpToolsTests.cs`

**Interfaces:**
- Consumes: `PrismApi` içindeki tüm public metotlar (Task 4, 9, 10, 11 ve 13).
- Produces:
  - `static class PrismMcpTools`. Her metot tek bir JSON string parametre alır ve JSON string döner. Hata durumunda `{"ok":false,"error":{code,message,details}}` döner.
  - Metotlar: `prism_list_products`, `prism_list_versions`, `prism_list_imported`, `prism_import`, `prism_update`, `prism_check_updates`, `prism_save_version`, `prism_open_scene_version`, `prism_playblast`, `prism_list_cameras`.
  - Hepsi `interactive:false` ile çalışır.

- [ ] **Step 1: Unity MCP'nin yeteneklerini doğrula (spike, kod yazılmaz).**
  - TestProject'i editörde aç ve Unity MCP relay'in bağlandığını doğrula.
  - Bu oturumda `ToolSearch` ile `unity` aramasını yap ve sunulan araçların listesini çıkar.
  - Kurulu Unity AI / MCP paketinin kaynağında özel araç kaydı için bir attribute ya da API olup olmadığına bak (ör. `McpTool`).
  - Sonucu `Documentation~/CLAUDE_TOOLS.md` dosyasının başına "Bağlantı yöntemi" başlığı altında yaz. İki yoldan biri seçilir:
    - **(A)** Özel araç kaydı mümkünse metotlar o API ile kaydedilir.
    - **(B)** Mümkün değilse Claude, relay'in editörde kod çalıştırma ya da menü çağırma aracıyla `Prism.Unity.Editor.PrismMcpTools.<metot>(json)` metodunu çağırır.
- [ ] **Step 2: Başarısız testleri yaz** (MCP'den bağımsız, metotlar doğrudan çağrılır).
  - `ImportReturnsJsonResult`: `prism_import` çağrısının sonucunda `ok == true` ve `result.record.version` bulunmalı.
  - `NeedsConfirmationIsReturnedNotThrown`: `prism_update` çağrısı v3 ile `confirm:false` olarak yapılır. Cevap `ok == false`, `error.code == "needs_confirmation"` olmalı ve `error.details.removedNodes` dolu olmalı.
  - `BadJsonReturnsBadArgs`
  - `AllToolsAreNonInteractive`: Bir test kancasıyla `PrismClient` çağrılarının tamamının `interactive:false` olduğu doğrulanır.
- [ ] **Step 3: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 4: `PrismMcpTools` sınıfını ve Step 1'de seçilen kayıt yolunu uygula. `CLAUDE_TOOLS.md` dosyasını tamamla.** Dosyada her araç için parametreler, örnek çağrı ve hata kodlarının anlamı yer alır. `needs_input` ve `needs_confirmation` hatalarında Claude'un ne yapacağı da yazılır: kullanıcıya sorup tekrar çağırmak.
- [ ] **Step 5: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 6: Claude ile canlı doğrula.**
  - Editör açıkken bu oturumdan Unity MCP üzerinden şu senaryoyu çalıştır: "Lotus'un son versiyonunu import et, sahneye yerleştir, URP/Lit tabanlı yeni bir materyal ata, turntable al, sahneyi `Scenes/MeditationRoom` olarak Prism'e kaydet."
  - Hiçbir pencere açılmadığını, Prism'de turntable medyasının ve sahne versiyonunun oluştuğunu kontrol et.
- [ ] **Step 7: Commit** — `feat: expose Prism operations to Claude via Unity MCP`.

### Task 15: Kabul senaryoları ve ekip için kurulum rehberi

**Files:**
- Create: `README.md` (Türkçe: kurulum, ekip Git LFS ayarı, menü kullanımı, Claude ile kullanım, sorun giderme)
- Create: `docs/acceptance/2026-11-11-v1-acceptance.md` (her senaryo için sonuç ve kanıt)

- [ ] **Step 1: Tüm testleri çalıştır.**
  - `tools/run_py_tests.ps1` → hepsi PASS.
  - `$env:PRISM_UNITY_IT=1; tools/run_py_tests.ps1 -Pattern "test_*_it.py"` → PASS.
  - `tools/run_unity_tests.ps1` ve `tools/run_unity_tests.ps1 -Category E2E` → hepsi PASS.
- [ ] **Step 2: Spec §10'daki 6 kabul senaryosunu elle çalıştır.** Her biri için kısa sonuç ve gerekirse ekran görüntüsü yolunu kabul belgesine yaz. Ek kontroller:
  - Senaryo 5 için Prism sürecini Görev Yöneticisi'nden öldür, sonra `Prism > Save Version` seç. Unity donmamalı, Prism yeniden başlamalı ya da anlaşılır bir hata gelmeli.
  - Senaryo 6 için `tests/python` içindeki yardımcıyla Unity'ye tanımsız bir komut gönder, `unknown_command` hatası gelmeli.
- [ ] **Step 3: İkinci Unity projesiyle eşzamanlılığı kontrol et** (Review Focus 2). `TestProject` klasörünün bir kopyasını aç, iki projede aynı anda `Prism > Project Browser` seç. İki ayrı Prism süreci açılmalı ve her biri kendi projesine bağlı olmalı.
- [ ] **Step 4: `README.md` dosyasını yaz.** Ekibin Unity projesi için önerilen `.gitattributes` satırları da (FBX ve ABC için LFS) README'ye eklenir.
- [ ] **Step 5: Commit** — `docs: v1 acceptance results and team setup guide`.
