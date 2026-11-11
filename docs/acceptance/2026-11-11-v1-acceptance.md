# v1 Kabul Sonuçları — 2026-11-11

**Ortam:**
- Windows 11, Prism 2.1.2.1, Unity 6000.5.6f1 (URP), Unity AI Assistant 2.19.0-pre.2.
- Test Prism projesi: `%USERPROFILE%\PrismUnityTest Project`.

**Otomatik test durumu (`tools/run_all_tests.ps1 -E2E`):**
- Python: tüm testler geçti.
- Unity EditMode: 104/104.
- Gerçek Prism ile uçtan uca testler: 9/9.

## Spec §10 kabul senaryoları

| # | Senaryo | Sonuç | Kanıt |
|---|---|---|---|
| 1 | Import → materyal atama → yeni versiyonla güncelleme; materyal ve yerleşim korunuyor | ✅ | `ProductImporterTests.UpdateKeepsGuid`, `UpdateKeepsMaterialRemap`, `UpdateKeepsSceneInstance`; E2E `ImportLatestThenUpdateAfterNewPublish` |
| 2 | Sahne Save Version → Prism'de görünüyor; eski versiyon doğru açılıyor | ✅ | E2E `SaveVersionHeadlessTwice` (iki versiyon, yorum ve proje kimliği versiyon bilgisinde); `SceneOpenTests.OpenRestoresVersionIntoWorkingPath` |
| 3 | Turntable playblast Prism medyasında; sahne değişmemiş | ✅ | E2E `TurntableAppearsInPrismMedia` (24 PNG + MP4, versioninfo); `PlayblastCaptureTests.TurntableDoesNotDirtySceneOrMoveTargets`; karelere göz ile bakıldı |
| 4 | 1–3 Claude üzerinden, hiçbir pencere açılmadan | ✅ | Canlı Claude oturumu (aşağıda); E2E testleri `PRISM_UNITY_FAIL_ON_DIALOG=1` ile, yani pencere açılsaydı test başarısız olurdu |
| 5 | Prism kapalı veya çökmüşken Unity donmuyor, anlaşılır hata ya da yeniden başlatma | ✅ | E2E `PrismRestartsAfterCrash`; `PrismProcessTests.SendAsyncFailsFastWhenPrismMissing` (< 2 sn, editör kare ilerletmeye devam ediyor) |
| 6 | Tanımsız komut reddediliyor | ✅ | `CommandServerTests.RejectsUnknownCommand` (Unity), `test_server_rejects_unknown_command` ve `test_dispatch_unknown_command` (Prism) |

## Canlı Claude oturumu (Unity MCP, editör arka planda)

1. `prism_list_versions` → lotus_model v0001–v0003, yorumlarıyla.
2. `prism_check_updates` → `Props__Lotus__lotus_model` v0002 → v0003.
3. `prism_update` (onaysız) → `needs_confirmation`. Fark listesi: `Stem` silindi, `StemMain` eklendi, `StemMat` kaldırıldı. Hiçbir şey değişmedi.
4. `prism_import` v0002 → lotus yerleştirildi, `PetalMat` yeni URP/Lit pembe materyale eşlendi.
5. `prism_playblast` (PNG ve MP4) → Turntable v0001/v0002. Pembe materyal karede görünüyor.
6. `prism_save_version` → önce `needs_confirmation` (departman oluşturma). Onaydan sonra `MeditationRoom_layout_v0001.unity` kaydedildi. Lotus sahnede, yorum ve proje kimliği versiyon bilgisinde.
7. Kullanıcının Prism "aktif proje" ayarı değişmedi (`M:\ulker_ambalaj`).

## Senin elle kontrol etmen gerekenler

Bunlar Prism'in kendi pencerelerine bakmayı gerektiriyor:

- [ ] **Prism Settings → DCC apps → Unity** ile yeni bir Unity projesine kurulum. `manifest.json` girişi ve `ProjectSettings/PrismUnity/project.json` oluşmalı.
- [ ] **Prism → Project Browser** Prism'i doğru projeyle açıyor. Unity kapanınca Prism 10 sn içinde kapanıyor.
- [ ] **Prism → Import...** ürün tarayıcısından bir versiyon seçince Unity'ye geliyor. İsim değişen bir versiyonda fark listesi soruluyor.
- [ ] Unity'yi yeniden açınca "yeni versiyon var" penceresi geliyor. **Update** seçince materyal ataması korunuyor.
- [ ] **Prism → Save Version / Save Comment...** ilk kayıtta asset ve görev soruyor.
- [ ] Prism Project Browser'dan bir sahne versiyonu açılınca kaydedilmemiş değişiklikler için Kaydet / At / Vazgeç soruluyor.
- [ ] **Prism → Playblast...** penceresi çalışıyor, sonuç Prism medya tarayıcısında oynatılabiliyor.
- [ ] **İki Unity projesi aynı anda:** `TestProject`'in bir kopyasını aç, iki projede de **Prism → Project Browser** seç. İki ayrı Prism süreci açılmalı, her biri kendi projesine bağlı olmalı. Proje başına tek örnek ve ayrı portlar birim testleriyle doğrulandı, ama gerçek iki editörle henüz denenmedi.
