# Prism ↔ Unity Asset Paketleme — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prism'den Unity'ye gelen her ürün için şunları otomatik kurmak:
- prefab variant
- tanım dosyası (ScriptableObject)
- Addressable kaydı
- Prism önizlemesinden küçük resim
- ortak katalog

Ayrıca paketleri Unity projesine gömerek v1'deki makineye özel paket yolu sorununu kapatmak.

**Architecture:**
- **Paketler:**
  - Yeni runtime paketi `com.prism.assets`: tanım ve katalog sınıfları, oyuna girer, Addressables'a bağımlı.
  - Editor paketi `com.prism.unity`'ye yeni bir `Prism.Unity.Editor.Packaging` assembly'si eklenir. Bu assembly yalnızca `com.prism.assets` varken derlenir.
- **Import'a bağlanma:** Paketleme, v1'deki import'a bir olay (`ProductImporter.Imported`) üzerinden bağlanır. v1 kodu paketlemeyi bilmez.
- **Kurulum:** Prism entegrasyonu iki paketi Unity projesinin `Packages/` klasörüne kopyalar (gömülü paket).
- **Eklenti klasörü:** Unity, Prism eklenti klasörünü Prism'in eklenti listesinden bulur.

**Tech Stack:** v1'deki ile aynı (Prism 2.1.2.1 Python, Unity 6000.5.6f1 + URP, C#, unittest, Unity Test Framework), artı Addressables `2.9.1`.

**Spec:** `docs/superpowers/specs/2026-11-11-prism-unity-asset-packaging-design.md` (v1: `docs/superpowers/specs/2026-11-11-prism-unity-entegrasyonu-design.md`)

## Global Constraints

- v1'in bütün kuralları geçerli:
  - Yalnızca loopback ve token.
  - Tanımlı komut listesi dışında hiçbir şey çalışmaz.
  - `interactive:false` çağrılarda pencere açılmaz.
  - Bekleyen taraf geri çağrılmaz. Prism, Unity'yi çağırırken gerekli veriyi (ör. `previewPath`) önceden çözüp gönderir.
  - Unity API'leri yalnızca ana thread'de kullanılır.
- **Dosya yerleri:**
  - Paket klasörü `Assets/Prism/<entity yolu>/<ürün>/`. İçindekiler: model `<ürün><ext>`, prefab `<ürün>.prefab`, tanım `<ürün>.asset`, küçük resim `<ürün>_thumb.png`.
  - Katalog `Assets/Prism/PrismAssetCatalog.asset`.
- **Addressables:**
  - Adres biçimi varsayılanı `{entity}/{product}`, ör. `Props/Lotus/lotus_model`.
  - Küçük resim adresi `<adres>#thumb`, tanım adresi `<adres>#definition`, katalog adresi `PrismAssetCatalog`.
  - Grup adı biçimi varsayılanı `Prism {category}`. `{category}` entity yolunun ilk klasörüdür.
  - Etiketler `prism`, `{category}` ve ürün adı.
- **Asla üzerine yazılmayanlar:**
  - Ekibin prefab variant'ı. Eklenti yalnızca yoksa oluşturur.
  - Tanım dosyasında ekibin alanları.
  - `displayName`. Yalnızca boşsa yazılır.
  - Başka bir asset'e ait Addressable adresi.
- **Hiçbir şey otomatik silinmez.** Prism'de olmayan ürün `prismMissing = true` olur.
- **Paket adları:**
  - Runtime paketi `com.prism.assets`, asmdef `Prism.Assets`, namespace `Prism.Assets`.
  - Editor paketleme assembly'si `Prism.Unity.Editor.Packaging`.
- **Ayarlar:** `ProjectSettings/PrismUnity/settings.json`. Proje bağlantısı `project.json`'da kalır. Prism yolu EditorPrefs `PrismUnity.PrismRoot`'ta kalır.

## Review Focus

1. **Ekibin eklemeleri:** Ekibin prefab variant'a eklediği component'ler ve tanım dosyasındaki kendi alanları; güncelleme, "eksikleri oluştur" ve sınıf çevirme işlemlerinden sonra aynen kalmalı. Testler: Task 5 ve Task 7.
2. **Adres çakışması:** Projede aynı adrese kayıtlı Prism dışı bir asset varsa adres değiştirilmemeli, uyarı dönmeli. Test: Task 5.
3. **Prism'siz makine:** Eklentisi kurulu olmayan bir makinede (`com.prism.unity` ve `com.prism.assets` gömülü, Prism yok) proje derlenmeli, Prism menüsü `prism_unavailable` vermeli. Test: Task 1.
4. **İlk paketleme:** Addressables ayarlarının henüz oluşturulmadığı bir projede ilk paketleme pencere açmadan ayarları ve grubu oluşturmalı. Test: Task 5.
5. **Türkçe karakter ve boşluklar:** Adreslerde, grup adlarında ve dosya adlarında Türkçe karakter ve boşluk (`Props/Çay Bardağı`) sorunsuz çalışmalı. Test: Task 5.

---

## Dosya Yapısı (yeni ve değişen)

```
Unity/UnityPackage/
  com.prism.assets/                          YENİ runtime paketi
    package.json                             depends: com.unity.addressables 2.9.1
    Runtime/Prism.Assets.asmdef
    Runtime/PrismAssetDefinition.cs
    Runtime/PrismAssetCatalog.cs
  com.prism.unity/
    Editor/Project/PluginLocator.cs          YENİ: eklenti klasörünü bulma
    Editor/Project/PackagingSettings.cs      YENİ: settings.json
    Editor/Project/PrismSettingsProvider.cs  YENİ: Project Settings → Prism
    Editor/Import/ProductImporter.cs         DEĞİŞİR: Imported olayı, previewPath
    Editor.Packaging/                        YENİ asmdef (com.prism.assets varken)
      Prism.Unity.Editor.Packaging.asmdef
      PackageBuilder.cs                      prefab variant, tanım, küçük resim
      AddressablesRegistrar.cs               grup, adres, etiket, çakışma kontrolü
      CatalogUpdater.cs
      PackagingCommands.cs                   menü, Unity komutları, Claude araçları
    Tests/Editor/...                         yeni testler
Unity/Scripts/unity_bridge/manifest.py       DEĞİŞİR: gömülü kurulum
Unity/Scripts/unity_bridge/commands.py       DEĞİŞİR: previewPath, missing
Unity/Scripts/Prism_Unity_Integration.py     DEĞİŞİR: install_embedded
TestProject/Packages/manifest.json           com.prism.assets (göreli file:)
tools/make_test_prism_project.py             lotus v0002 için ürün önizlemesi
```

## Ortak Arayüzler

**Unity → Prism, değişen cevaplar:**
- `resolveVersion` cevabına `"previewPath"` eklenir. Değer ürün önizlemesi, o yoksa entity önizlemesi, o da yoksa `""`.
- `checkVersions` cevabına, proje erişilebilir ama ürünün hiç versiyonu yoksa `{"id", "missing": true, "entity", "product"}` biçiminde girişler eklenir. Proje ya da sürücü erişilemiyorsa ürün v1'deki gibi atlanır.

**Prism → Unity, yeni komut:**
- `setPrismMissing {ids: [..], missing: bool}`. Proje değiştiren bir komut olarak işaretlenir.

**C#, runtime (`Prism.Assets`):**

```csharp
public class PrismAssetDefinition : ScriptableObject {
  public string displayName, entityType, entityPath, product, version, contentVersion, addressableKey;
  public AssetReferenceGameObject prefab; public AssetReferenceTexture2D thumbnail; public bool prismMissing;
}
public class PrismAssetCatalog : ScriptableObject {
  public List<PrismAssetDefinition> definitions;
  public IEnumerable<PrismAssetDefinition> ByCategory(string category);    // entityPath'in ilk klasörü
  public PrismAssetDefinition Find(string entityPath, string product);
  public IEnumerable<T> OfType<T>() where T : PrismAssetDefinition;
}
```

**C#, editor:**
- `ProductImporter.Imported` olayı: `static event Action<ImportRecord, ResolvedVersion>`. Başarılı her import ve güncellemeden sonra çağrılır.
- `ResolvedVersion.PreviewPath`: JSON alanı `previewPath`.
- Paketleme sonucu `PackageInfo { string PrefabPath, DefinitionPath, AddressableKey, ThumbnailPath; string Warning }`, JSON'da camelCase.
- `PrismMcpTools.PackageInfoProvider`: `static Func<string recordId, JObject>`. Paketleme assembly'si bunu doldurur, import, güncelleme ve listeleme cevaplarına `package` alanı buradan gelir.

---

### Task 1: Eklenti klasörünü bulma ve gömülü paket kurulumu (v1 düzeltmesi)

**Files:**
- Create: `Editor/Project/PluginLocator.cs`, `Tests/Editor/PluginLocatorTests.cs`
- Modify: `Editor/Project/PrismSettings.cs` (`PluginDir` artık `PluginLocator.Find()`), `Unity/Scripts/unity_bridge/manifest.py`, `Unity/Scripts/Prism_Unity_Integration.py`, `tests/python/test_manifest.py`

**Interfaces:**
- Produces (C#): `static class PluginLocator`:
  - `string Find()`. Sıra:
    1. EditorPrefs `PrismUnity.PluginDir`
    2. `%USERPROFILE%\Documents\Prism2\PluginPaths.json` içinde `Scripts\Prism_Unity_Launcher.py` dosyasını içeren ilk yol
    3. `C:\ProgramData\Prism2\plugins\Unity`
    4. Repo düzeni (paketten iki üst klasör, yalnızca `TestProject` için)
  - Bulamazsa `null` döner. `PrismProcess.CheckInstalled`, `prism_unavailable` hatasıyla "Prism Unity eklentisi bulunamadı" der.
  - `string Find(string pluginPathsJson, string programDataDir, string prefsOverride, string packagePath)`: test edilebilir sürüm.
- Produces (Python, `manifest.py`):
  - `install_embedded(project_path, plugin_dir) -> list[str]`. `UnityPackage/com.prism.unity` ve `UnityPackage/com.prism.assets` klasörlerini `<proje>/Packages/` altına kopyalar. Var olan kopyayı önce siler. `manifest.json`'daki `com.prism.unity` / `com.prism.assets` `file:` girişlerini kaldırır. Kopyalanan paket adlarını döner.
  - `remove_embedded(project_path) -> bool`
  - `add_package` ve `remove_package` yalnızca `TestProject` geliştirme yolu için kalır.
- `Prism_Unity_Integration.addIntegration` artık `install_embedded` ve `write_project_binding` çağırır.

- [ ] **Step 1: Başarısız testleri yaz.**
  - Python:
    - `test_install_embedded_copies_both_packages`: `Packages/com.prism.unity/package.json` ve `Packages/com.prism.assets/package.json` oluşmalı.
    - `test_install_embedded_removes_machine_specific_file_entry`: Önce `add_package` ile mutlak `file:` girişi yazılır. Kurulumdan sonra girişin yok olması, diğer bağımlılıkların korunması gerekir.
    - `test_install_embedded_replaces_old_copy`: Eski kopyada fazladan bir dosya bırakılır. Kurulumdan sonra o dosya olmamalı.
    - `test_install_embedded_turkish_path`
  - C#:
    - `PrefsOverrideWins`
    - `FindsLauncherFromPluginPaths`: Geçici bir `PluginPaths.json` ve sahte bir launcher dosyası kullanılır.
    - `FallsBackToProgramData`
    - `ReturnsNullWhenNothingFound`
    - `SendAsyncWithoutPluginIsPrismUnavailable`: Paket yolu "gömülü"ymüş gibi ayarlanır ve klasörler boştur. 2 sn içinde `prism_unavailable` dönmeli (Review Focus 3).
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.** `tools/run_py_tests.ps1` → FAIL; `tools/run_unity_tests.ps1 -Filter PluginLocatorTests` → derleme hatası.
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula** (iki çalıştırıcıyla da), ardından `tools/run_all_tests.ps1 -E2E` → hepsi PASS. `TestProject` bu adımda henüz `com.prism.assets` içermez, Task 2'de eklenecek.
- [ ] **Step 5: Commit** — `fix: embed Prism packages in the Unity project; locate the Prism plugin folder`.

### Task 2: `com.prism.assets` runtime paketi

**Files:**
- Create: `Unity/UnityPackage/com.prism.assets/package.json`, `Runtime/Prism.Assets.asmdef`, `Runtime/PrismAssetDefinition.cs`, `Runtime/PrismAssetCatalog.cs`
- Modify: `TestProject/Packages/manifest.json`. Eklenecek giriş: `"com.prism.assets": "file:../../Unity/UnityPackage/com.prism.assets"`. `testables` listesine ekleme yapılmaz, testler editor test assembly'sinde.
- Modify: `Tests/Editor/Prism.Unity.Editor.Tests.asmdef`. Referanslara `Prism.Assets`, `Unity.Addressables` ve `Unity.ResourceManager` eklenir.
- Test: `Tests/Editor/PrismAssetCatalogTests.cs`

**Interfaces:** "Ortak Arayüzler"deki runtime sınıflar. `package.json` içeriği: `"name":"com.prism.assets"`, `"version":"0.1.0"`, `"unity":"6000.5"`, `"dependencies":{"com.unity.addressables":"2.9.1"}`. asmdef bütün platformlarda derlenir, yalnızca `Unity.Addressables` ve `Unity.ResourceManager` referanslarını içerir, editor koduna bağımlılığı yoktur.

- [ ] **Step 1: Başarısız testleri yaz.**
  - `ByCategoryUsesFirstFolder`: `Props/Lotus` ve `Props/Çay Bardağı` → `Props` altında 2 sonuç. `Scenes/MeditationRoom` → `Scenes` altında 1 sonuç.
  - `FindByEntityAndProduct`
  - `OfTypeReturnsSubclassesOnly`: `TestItemDefinition : PrismAssetDefinition` (testte tanımlı).
  - `RuntimeAssemblyHasNoEditorReference`: `typeof(PrismAssetDefinition).Assembly.GetReferencedAssemblies()` içinde `UnityEditor` olmamalı.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.** Addressables paketi manifest bağımlılığıyla gelir. İlk Unity açılışı paketi içe aktarır.
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.** Ardından tam suite'i çalıştır.
- [ ] **Step 5: Commit** — `feat: com.prism.assets runtime package (definition, catalog)`.

### Task 3: Ayarlar (settings.json) ve Project Settings → Prism sayfası

**Files:**
- Create: `Editor/Project/PackagingSettings.cs`, `Editor/Project/PrismSettingsProvider.cs`, `Tests/Editor/PackagingSettingsTests.cs`
- Modify: `Editor/Project/ProjectBinding.cs`. Eklenecek fonksiyon: `static string ValidateRelocation(string newConfig, string currentConfig)`. Yeni ve eski `pipeline.json` içindeki `globals.project_name` aynı değilse hata metni döner.

**Interfaces:**
- `class PackagingSettings`:
  - Alanlar:
    - `bool Enabled = true`
    - `string DefinitionType = "Prism.Assets.PrismAssetDefinition, Prism.Assets"`
    - `string AddressFormat = "{entity}/{product}"`
    - `string GroupFormat = "Prism {category}"`
  - Metotlar: `static PackagingSettings Load()`, `void Save()`, `string FormatAddress(PrismEntity e, string product)`, `string FormatGroup(PrismEntity e)`.
- `PrismSettingsProvider`: `[SettingsProvider]` ile `Project/Prism` sayfası. Sayfada şunlar bulunur:
  - Prism kurulum klasörü (EditorPrefs)
  - Bulunan eklenti klasörü (salt okunur)
  - Bağlı Prism projesi ve "Proje taşındı…" düğmesi
  - Paketleme ayarları
  - `PrismAssetDefinition`'dan türetilmiş sınıfları listeleyen açılır liste (`TypeCache.GetTypesDerivedFrom<PrismAssetDefinition>()`)

- [ ] **Step 1: Başarısız testleri yaz.**
  - `DefaultsWhenFileMissing`
  - `SaveLoadRoundTrip`
  - `FormatAddressAndGroup`: `Props/Çay Bardağı` + `cay_model` → `Props/Çay Bardağı/cay_model` ve `Prism Props`.
  - `ShotEntityFormats`: shot için `{entity}` = `sq01/sh010`, `{category}` = `sq01`.
  - `RelocationSameProjectAccepted`
  - `RelocationOtherProjectRejected`
  - `RelocationStopsRunningPrism`: Kabul edilen bir taşıma `project.json`'u yazmalı ve `PrismProcess.StopOwnedProcess()` çağırmalı. Böylece bir sonraki çağrı Prism'i yeni yolla başlatır. Testte `PrismProcess` için bir gözlem kancası kullanılır.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat(unity): packaging settings and Project Settings → Prism page`.

### Task 4: Prism tarafı: önizleme yolu ve "ürün yok" durumu

**Files:**
- Modify: `Unity/Scripts/unity_bridge/commands.py` (`_describe_version`, `checkVersions`), `Unity/Scripts/unity_bridge/dialogs.py` (versiyon kontrol penceresinde "Prism'de yok" bölümü, Unity'ye `setPrismMissing` çağrısı)
- Modify: `tools/make_test_prism_project.py`. lotus_model v0002 için bir ürün önizlemesi yazılır: `products.setProductPreview(<version path>, QPixmap 64x64 kırmızı)`.
- Test: `tests/python/test_commands_products.py`, `tests/python/test_dialog_flow.py`

**Interfaces:** "Ortak Arayüzler"deki `previewPath` ve `missing`. Ürünün "yok" sayılma koşulu şunların hepsi: `core.getEntityPath(entity)` mevcut, `getProductsFromEntity(entity)` içinde ürün adı yok, ve proje kökü erişilebilir.

- [ ] **Step 1: Başarısız testleri yaz.**
  - `test_resolve_includes_product_preview`: Sahte `getProductPreviewPath` var olan bir dosya döner.
  - `test_resolve_falls_back_to_entity_preview`
  - `test_resolve_without_preview_is_empty_string`
  - `test_check_versions_reports_missing_product`
  - `test_check_versions_skips_unreachable_project`: entity yolu yok → listede olmamalı.
  - `test_check_dialog_marks_missing_in_unity`: `run_mark_missing(cmds, entries)` Unity'ye `setPrismMissing` gönderir.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.** Ardından test Prism projesini güncelle: `make_test_prism_project.py`'yi yeniden çalıştır. Betik var olan versiyonları atlar, eksik önizlemeyi ekler.
- [ ] **Step 5: Commit** — `feat(prism): preview path in resolved versions; report products missing from Prism`.

### Task 5: Paketleme çekirdeği (prefab variant, tanım, küçük resim, Addressables, katalog)

**Files:**
- Create: `Editor.Packaging/Prism.Unity.Editor.Packaging.asmdef`. Referanslar: `Prism.Unity.Editor`, `Prism.Assets`, `Unity.Addressables`, `Unity.Addressables.Editor`, `Unity.ResourceManager`. `versionDefines` ile `com.prism.assets` varsa `PRISM_ASSETS`, `defineConstraints: ["PRISM_ASSETS"]`.
- Create: `Editor.Packaging/PackageBuilder.cs`, `AddressablesRegistrar.cs`, `CatalogUpdater.cs`
- Modify: `Editor/Import/ProductImporter.cs`. `Imported` olayı eklenir, `ResolvedVersion.PreviewPath` eklenir. Prism'den başlayan import'larda `resolved.previewPath` zaten gelir.
- Test: `Tests/Editor/Packaging/PackageBuilderTests.cs`. Test asmdef'ine `Prism.Unity.Editor.Packaging` ve `Unity.Addressables.Editor` referansları eklenir.

**Interfaces:**
- `static class PackageBuilder` ve `PackageInfo Ensure(ImportRecord record, string previewPath)`. Sırasıyla:
  1. Prefab yoksa oluşturur: modeli örnekler, `PrefabUtility.SaveAsPrefabAsset` ile kaydeder. Bu, modelin variant'ıdır.
  2. Tanım dosyası yoksa `PackagingSettings.DefinitionType` tipinde oluşturur.
  3. Prism alanlarını yazar. `displayName` yalnızca boşsa `entity.Name` olur. `prismMissing = false` yapılır.
  4. Küçük resmi yazar: `previewPath` varsa kopyalanır. Yoksa `TurntableRig` + `FrameCapture` ile 256×256 tek kare render edilir. `TextureImporter` ayarları: mipmap kapalı, maksimum boyut 256.
  5. `AddressablesRegistrar`'ı çağırır.
  6. `CatalogUpdater`'ı çağırır.
- `ProductImporter.Imported`'a `[InitializeOnLoad]` ile abone olunur. `PackagingSettings.Enabled` false ise hiçbir şey yapılmaz.
- `static class AddressablesRegistrar` ve `string Register(string assetGuid, string address, string group, string[] labels)`. Bir uyarı metni ya da null döner. Davranışı:
  - Ayarlar yoksa `AddressableAssetSettingsDefaultObject.GetSettings(true)` ile oluşturulur, pencere açılmaz.
  - Grup yoksa `CreateGroup(group, false, false, true, null, typeof(BundledAssetGroupSchema), typeof(ContentUpdateGroupSchema))` ile oluşturulur.
  - Aynı adreste başka bir GUID varsa kayıt yapılmaz ve uyarı döner.
  - Asset başka bir gruptaysa grubu değiştirilmez, yalnızca etiketler eklenir.
- `static class CatalogUpdater`:
  - `void Add(PrismAssetDefinition d)`: Liste entity yolu ve ürüne göre sıralı tutulur.
  - `PrismAssetCatalog GetOrCreate()`: Katalog `PrismAssetCatalog` adresiyle kaydedilir.

- [ ] **Step 1: Başarısız testleri yaz.** Testler `ImportFixture` ve `ProductImporter.ImportResolved` kullanır, olay paketlemeyi tetikler.
  - `ImportCreatesFullPackage`: Prefab, tanım ve küçük resim dosyaları oluşmalı. Prefab, modelin variant'ı olmalı (`PrefabUtility.GetPrefabAssetType == Variant`). Tanımda `version == "v0001"` olmalı, `addressableKey == "Props/Lotus/lotus_model"` olmalı. Addressables'ta `Props/Lotus/lotus_model` adresli bir kayıt `Prism Props` grubunda, etiketleri `prism`, `Props` ve `lotus_model` olmalı. Katalogda 1 tanım olmalı.
  - `FirstPackagingCreatesAddressablesSettingsWithoutDialog` (Review Focus 4): Test başında Addressables ayarları geçici olarak kaldırılır.
  - `UpdateKeepsTeamPrefabAdditions` (Review Focus 1): Prefab variant'a bir `BoxCollider` eklenir. v2 import edilince collider hâlâ orada olmalı, tanımda `version == "v0002"` olmalı.
  - `UpdateKeepsTeamDefinitionFieldsAndDisplayName`: `TestItemDefinition` tipinde `unlockLevel = 5` ve `displayName = "Nilüfer"` ayarlanır. Güncellemeden sonra ikisi de aynı kalmalı.
  - `AddressCollisionIsNotOverwritten` (Review Focus 2): Başka bir asset `Props/Lotus/lotus_model` adresine kaydedilir. Import sonucu `PackageInfo.Warning` dolu olmalı, diğer asset'in adresi aynı kalmalı.
  - `ThumbnailFromPrismPreview`: `previewPath` olarak 64×64 kırmızı bir PNG verilir. Küçük resmin piksel rengi kırmızı olmalı.
  - `ThumbnailRenderedWithoutPreview`: Küçük resim 256×256 olmalı.
  - `TurkishNamesWork` (Review Focus 5): `Props/Çay Bardağı` için adres `Props/Çay Bardağı/cay_model` olmalı, grup `Prism Props` olmalı.
  - `PackagingDisabledKeepsV1Behaviour`: `Enabled = false` iken yalnızca model import edilmeli.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.** Ardından tam suite'i çalıştır. v1 testleri paketleme açıkken de geçmeli.
- [ ] **Step 5: Commit** — `feat(unity): package every imported product (prefab variant, definition, thumbnail, Addressables, catalog)`.

### Task 6: "Prism'de yok" işareti

**Files:**
- Modify: `Editor.Packaging/PackagingCommands.cs` (`setPrismMissing` komutu), `Editor/Api/PrismApi.Import.cs`. `CheckForUpdates` sonucundaki `missing` girişleri için yerelde de işaret konur. Packaging assembly'si bunu bir olayla (`PrismApi.MissingReported`) dinler.
- Test: `Tests/Editor/Packaging/MissingFlagTests.cs`

- [ ] **Step 1: Başarısız testleri yaz.**
  - `SetPrismMissingMarksDefinition`
  - `ReimportClearsMissing`
  - `MissingNeverDeletesAnything`: Prefab, tanım ve Addressable kaydı yerinde kalmalı.
  - `CheckForUpdatesMarksMissing`: `PrismClient.Override` ile `checkVersions` bir `missing` girişi döner.
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat: mark packages whose product disappeared from Prism`.

### Task 7: Eksik paketleri oluşturma ve tanım sınıfını çevirme

**Files:**
- Modify: `Editor.Packaging/PackagingCommands.cs`
- Test: `Tests/Editor/Packaging/GenerateAndConvertTests.cs`

**Interfaces:**
- `static int PackagingCommands.GenerateMissing()`: Bütün import kayıtları için `PackageBuilder.Ensure(record, previewPath: null)` çağrılır. Oluşturulan paket sayısı döner. Menü: **Prism → Generate Missing Asset Packages**.
  - Önizleme Prism'den gerekiyorsa çağrı `PrismApi` üzerinden yapılır. Bu yüzden asıl metot async'tir: `Task<int> GenerateMissingAsync()`. Bu metot her kayıt için `resolveVersion` çağırır ve `previewPath`'i alır. Prism'e ulaşılamazsa render'a düşer.
- `static (int count, string[] paths) PackagingCommands.PreviewConversion(Type target)` ve `static int ConvertDefinitions(Type target)`:
  - Tanım dosyasının `m_Script` referansı hedef sınıfın `MonoScript`'iyle değiştirilir, aynı adlı alanlar korunur.
  - Menü: **Prism → Convert Definitions to Selected Class**. Önce sayı gösterilip onay istenir.
  - Ayarlar sayfasında sınıf değiştirildiğinde de aynı öneri gelir.

- [ ] **Step 1: Başarısız testleri yaz.**
  - `GenerateMissingCreatesPackagesForV1Imports`: Paketleme kapalıyken iki ürün import edilir, sonra paketleme açılır. Komut 2 dönmeli, iki paket de tam olmalı.
  - `GenerateMissingIsIdempotent`: İkinci çağrı 0 dönmeli, prefab'a eklenen collider korunmalı.
  - `ConvertKeepsGuidAndPrismFields`: Dönüştürmeden önce ve sonra GUID aynı olmalı, `addressableKey` aynı olmalı, tip `TestItemDefinition` olmalı.
  - `ConvertedDefinitionStillInCatalog`
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat: generate missing asset packages; convert definitions to a team class`.

### Task 8: Claude araçları, rehber ve README

**Files:**
- Modify: `Editor/Mcp/PrismMcpTools.cs`. `prism_import`, `prism_update` ve `prism_list_imported` cevaplarına `package` eklenir (`PackageInfoProvider` üzerinden). Yeni araçlar: `prism_generate_packages` ve `prism_convert_definitions` (argüman: `className`, `confirm`).
- Modify: `Documentation~/CLAUDE_TOOLS.md`. Paketler, katalog ve Addressable ile yükleme örneği eklenir.
- Modify: `README.md`. "Asset packages" bölümü eklenir, kurulum adımlarına gömülü paketler ve Addressables yazılır.
- Test: `Tests/Editor/PrismMcpToolsTests.cs`. Mevcut liste testine iki yeni araç eklenir. Yeni testler:
  - `ImportResultIncludesPackage`
  - `ConvertWithoutConfirmNeedsConfirmation`: `confirm` olmadan çağrılınca `needs_confirmation` dönmeli, detayda `count` olmalı.
  - `GuideDocumentsEveryTool`: Mevcut test, yeni araçları da kapsar.

- [ ] **Step 1: Başarısız testleri yaz.**
- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula.**
- [ ] **Step 3: Uygula.**
- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula.**
- [ ] **Step 5: Commit** — `feat: package info and packaging tools for Claude; docs`.

### Task 9: Uçtan uca doğrulama

**Files:**
- Create: `Tests/Editor/E2E/PackagingE2ETests.cs`
- Modify: `docs/acceptance/` altına yeni bir sonuç belgesi.

- [ ] **Step 1: E2E testlerini yaz** (`[Category("E2E")]`, gerçek Prism, `PRISM_UNITY_FAIL_ON_DIALOG=1`).
  - `ImportLatestBuildsPackageWithPrismPreview`: lotus_model v0002 import edilir. Küçük resim, Prism ürün önizlemesinin kırmızı pikselini taşımalı. Adres kaydı mevcut olmalı.
  - `ProductRemovedFromPrismIsMarkedMissing`: Test Prism projesinde geçici bir ürün klasörü oluşturulup import edilir, sonra klasör silinir. `CheckForUpdates` çağrılınca tanımda `prismMissing == true` olmalı. Test sonunda temizlik yapılır.
- [ ] **Step 2: Çalıştır.** `tools/run_all_tests.ps1 -E2E` → hepsi PASS.
- [ ] **Step 3: Kurulumu elle doğrula.** Prism Settings → DCC apps → Unity ile yeni boş bir projeye kurulum yapılır. `Packages/com.prism.unity` ve `Packages/com.prism.assets` klasörleri oluşmalı, `manifest.json`'da `file:` girişi olmamalı, proje hatasız açılmalı ve Addressables yüklenmiş olmalı. Sonucu kabul belgesine yaz. Prism penceresi gerektiren adımları, v1'deki gibi kullanıcının kontrol listesine ekle.
- [ ] **Step 4: Commit** — `test: packaging end-to-end and acceptance notes`.
