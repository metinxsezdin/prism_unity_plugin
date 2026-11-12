# Asset paketleme kabul sonuçları — 2026-11-12

**Ortam:**
- Windows 11, Prism 2.1.2.1, Unity 6000.5.6f1 (URP), Addressables 2.9.1.
- Test Prism projesi: `%USERPROFILE%\PrismUnityTest Project`. lotus_model v0002 için 64x64 kırmızı ürün önizlemesi var.

**Otomatik test durumu (`tools/run_all_tests.ps1 -E2E`):**
- Python: tüm testler geçti.
- Unity EditMode: 164/164 (review düzeltmelerinden sonra).
- Gerçek Prism ile uçtan uca testler: 11/11.

## Kabul senaryoları

| # | Senaryo | Sonuç | Kanıt |
|---|---|---|---|
| 1 | Her import'ta prefab variant, tanım, küçük resim, Addressable kayıtları ve katalog girişi oluşuyor | ✅ | `PackageBuilderTests.ImportCreatesFullPackage`; E2E `ImportLatestBuildsPackageWithPrismPreview` |
| 2 | Küçük resim Prism'in önizlemesinden geliyor, önizleme yoksa render ediliyor | ✅ | E2E `ImportLatestBuildsPackageWithPrismPreview` (gerçek Prism önizlemesinin kırmızı pikseli); `ThumbnailRenderedWithoutPreview` |
| 3 | Güncelleme ekibin prefab eklemelerini ve tanım alanlarını koruyor | ✅ | `UpdateKeepsTeamPrefabAdditions`, `UpdateKeepsTeamDefinitionFieldsAndDisplayName` |
| 4 | Başka bir asset'in Addressable adresi ezilmiyor | ✅ | `AddressCollisionIsNotOverwritten` (uyarı döner, diğer kayıt yerinde kalır) |
| 5 | Addressables ayarı olmayan projede ilk paket ayarları penceresiz oluşturuyor | ✅ | `FirstPackagingCreatesAddressablesSettingsWithoutDialog` |
| 6 | Türkçe karakterli isimler | ✅ | `TurkishNamesWork` (`Props/Çay Bardağı/cay_model`) |
| 7 | Prism'den silinen ürün işaretleniyor, hiçbir şey silinmiyor | ✅ | E2E `ProductRemovedFromPrismIsMarkedMissing`; `MissingNeverDeletesAnything`, `ReimportClearsMissing` |
| 8 | Paketleme öncesi import edilmiş ürünler için eksik paketler oluşturuluyor | ✅ | `GenerateMissingCreatesPackagesForV1Imports`, `GenerateMissingIsIdempotent` |
| 9 | Tanımlar ekibin sınıfına çevriliyor, GUID ve referanslar korunuyor | ✅ | `ConvertKeepsGuidAndPrismFields`, `ConvertedDefinitionStillInCatalog` |
| 10 | Claude araçları paket bilgisini döndürüyor, çevirme onay istiyor | ✅ | `PrismMcpToolsTests.ImportResultIncludesPackage`, `ConvertWithoutConfirmNeedsConfirmation`, `GeneratePackagesReturnsCount` |
| 11 | Paketleme kapalıyken v1 davranışı | ✅ | `PackagingDisabledKeepsV1Behaviour` |
| 12 | Eklenti olmayan makinede proje açılıyor (gömülü paketler) | ✅ | Aşağıdaki kurulum denemesi; `PluginLocatorTests`, `test_manifest.py` |

## Kurulum denemesi (penceresiz)

Prism'in **DCC apps → Unity** sayfası `addIntegration` çağırır, o da `manifest.install_embedded` çağırır. Pencere açılamadığı için aynı fonksiyon doğrudan çalıştırıldı:

1. Unity 6000.5.6f1 ile boş bir proje oluşturuldu (`-createProject`).
2. `install_embedded(<proje>, Unity/)` çalıştırıldı.
3. Sonuç:
   - `Packages/com.prism.unity` ve `Packages/com.prism.assets` klasörleri oluştu.
   - `manifest.json`'da `com.prism.*` ya da `file:` girişi yok.
4. Proje batchmode'da açıldı:
   - 0 derleme hatası.
   - `com.unity.addressables@2.9.1` çözüldü.
   - `Prism.Assets`, `Prism.Unity.Editor` ve `Prism.Unity.Editor.Packaging` derlendi.
   - `Prism.Unity.Editor.Mcp` derlenmedi. Bu beklenen bir durum, çünkü AI Assistant paketi kurulu değil.
5. Not: Bu denemede `Prism.Unity.Editor.Tests` da kopyalanıyordu. Review sonrası `Tests/` artık kopyalanmıyor (`test_install_embedded_leaves_out_tests`).

## Senin elle kontrol etmen gerekenler

Bunlar Prism ya da Unity penceresi gerektiriyor, otomatik testlerle denenemedi:

- [ ] **Prism Settings → DCC apps → Unity** ile yeni bir Unity projesine kurulum. `Packages/com.prism.unity`, `Packages/com.prism.assets` ve `ProjectSettings/PrismUnity/project.json` oluşmalı, `manifest.json`'da `file:` girişi olmamalı.
- [ ] **Project Settings → Prism** sayfası açılıyor. Paketleme aç/kapa, tanım sınıfı, adres ve grup biçimi kaydediliyor. Sınıf değiştirince mevcut tanımları çevirme önerisi geliyor.
- [ ] **Prism → Check for New Versions...** penceresinde Prism'den silinmiş bir ürün "Prism'de yok" notuyla görünüyor ve tanımı `prismMissing` oluyor.
- [ ] **Prism → Generate Missing Asset Packages** ve **Prism → Convert Definitions to Selected Class** menüleri çalışıyor, sonuç penceresi doğru sayıyı gösteriyor.
- [ ] **Canlı Claude oturumu:** `prism_import` cevabında `package` alanı var, `prism_convert_definitions` önce `needs_confirmation` dönüyor. Bu oturumda Unity MCP bağlantısı kapalıydı. Aynı çağrılar `PrismMcpToolsTests` ile doğrulandı.
- [ ] **Addressables build:** Window → Asset Management → Addressables → Groups → Build. `PrismAssetCatalog` ve `Props/Lotus/lotus_model` Play Mode'da yükleniyor.

## Açık konular

- Tanım sınıfı çevrildikten sonra, açık bir sahnede tanıma bağlı eski referanslar sahne yeniden yüklenene kadar boş görünebilir. Diskteki referanslar (GUID) doğru kalıyor.
- Review'dan ertelenen küçük konular branch raporunda listelendi.
