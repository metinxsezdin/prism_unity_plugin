# Prism ↔ Unity Entegrasyonu

Prism Pipeline 2 için Unity eklentisi. Maya ve Blender'dan Prism'e yayımlanan modeller Unity'ye versiyonlu gelir. Unity sahneleri Prism'de versiyonlanır, turntable ve kamera kayıtları Prism'in medya tarayıcısına yazılır. Bu işlerin hepsi hem Unity'deki **Prism** menüsünden hem de Claude'dan (Unity MCP üzerinden) yapılabilir.

- Tasarım: [docs/superpowers/specs/2026-11-11-prism-unity-entegrasyonu-design.md](docs/superpowers/specs/2026-11-11-prism-unity-entegrasyonu-design.md)
- Claude araç rehberi: [Unity/UnityPackage/com.prism.unity/Documentation~/CLAUDE_TOOLS.md](Unity/UnityPackage/com.prism.unity/Documentation~/CLAUDE_TOOLS.md)

## Gereksinimler

- Windows
- Prism Pipeline 2.1.x, `C:\Program Files\Prism2` altında kurulu (Maya ve Blender eklentileriyle birlikte)
- Unity `6000.5.6f1`, URP
- Claude ile kullanım için Unity projesinde **Unity AI Assistant** paketi (`com.unity.ai.assistant`) ve Claude'da `unity-mcp` bağlantısı

## Kurulum

### 1. Eklentiyi Prism'e tanıt (her makinede bir kez)

`Unity` klasörü Prism'in "Unity" eklentisidir. Bu repoyu klonladıktan sonra şu komutu çalıştır:

```powershell
tools\deploy_dev.ps1
```

Komut, `%USERPROFILE%\Documents\Prism2\PluginPaths.json` dosyasına bu klasörü ekler. İlk çalıştırmada orijinal dosyanın yedeğini `.bak` uzantısıyla alır. Kaldırmak için `tools\deploy_dev.ps1 -Remove` çalıştır.

Ekip genelinde dağıtmak için `Unity` klasörünü ortak bir yere koyup Prism ayarlarındaki eklentiler bölümünden aynı klasörü eklemek de yeterli.

### 2. Unity projesine kur (her proje için bir kez)

1. Prism'i aç ve ilgili Prism projesine geç.
2. **Prism Settings → DCC apps → Unity** bölümünden Unity proje klasörünü seç: içinde `Assets`, `Packages` ve `ProjectSettings` bulunan klasör.
3. Prism iki şey yapar:
   - `Packages/manifest.json` dosyasına `com.prism.unity` paketini ekler.
   - Unity projesini o anki Prism projesine bağlar. Bağlantı `ProjectSettings/PrismUnity/project.json` dosyasında tutulur.
4. Unity'yi aç. Üst menüde **Prism** görünür.

Unity projesi hangi Prism projesine bağlıysa onu kullanır. Maya'da en son hangi projeyi açtığın önemli değildir, eklenti senin Prism'deki "aktif proje" ayarını da değiştirmez.

Prism başka bir klasöre kuruluysa Unity'de şu kodla yeri değiştir: `EditorPrefs.SetString("PrismUnity.PrismRoot", @"D:\Prism2")`

### 3. Git ve Git LFS ayarı (Unity projesinin reposu)

Import edilen modeller ve kayıtlar repoya girer, böylece herkes aynı versiyonları görür. Unity projesinin `.gitattributes` dosyasına şunları ekle:

```
*.fbx filter=lfs diff=lfs merge=lfs -text
*.abc filter=lfs diff=lfs merge=lfs -text
*.obj filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
```

Repoya girmesi gerekenler:
- `Assets/Prism/**` (`.meta` dosyalarıyla birlikte)
- `ProjectSettings/PrismUnity/**`: içe aktarım kayıtları (`imports/`, ürün başına bir dosya), sahne bağlantıları (`scenes/`, sahne başına bir dosya) ve proje bağlantısı (`project.json`)

`Library/` ise girmemeli, standart Unity `.gitignore` bunu zaten dışarıda bırakır.

## Kullanım (Prism menüsü)

| Menü | Ne yapar |
|---|---|
| **Project Browser** | Prism'in Project Browser'ını açar. Oradan bir sahne versiyonu açarsan Unity'de açılır. |
| **Save Version** | Açık sahneyi Prism'e yeni versiyon olarak kaydeder. İlk kayıtta hangi Prism asset'i ve görevine ait olduğunu sorar, departman varsayılan olarak `Unity`'dir. |
| **Save Comment...** | Aynısı, önce yorum sorar. |
| **Import...** | Prism'in ürün tarayıcısı açılır. Seçtiğin versiyon `Assets/Prism/<entity>/<ürün>/` altına gelir. |
| **Check for New Versions...** | Unity'deki Prism modellerinden yenisi çıkanları listeler ve seçtiklerini günceller. |
| **Playblast...** | Seçili objelerin turntable'ını ya da bir sahne kamerasının kaydını PNG veya MP4 olarak Prism'e yazar. |
| **Prism Settings...** | Prism ayarlarını açar. |

### Güncellemede ne olur?

- **Aynı dosya yenilenir.** Model her zaman aynı yolda durur, güncellemede o dosya yenilenir. Unity'deki materyal atamaların, prefab bağlantıların ve sahnedeki yerleşim korunur.
- **İsim değişikliğinde onay istenir.** Yeni versiyonda bir obje ya da materyal slotu yeniden adlandırılmış veya silinmişse, örneğin `Stem` → `StemMain`, güncelleme hemen uygulanmaz. Fark listesi gösterilir ve onay istenir.
- **Modelciler için kural:** Bu yüzden Maya'da ve Blender'da export'lar arasında obje ve materyal adlarını sabit tutun.
- **Açılışta kontrol:** Unity açılırken, Prism'de "check import versions" ayarı açıksa yeni versiyonu çıkan modeller için bir pencere gelir.

### Sahne versiyonları

- **Çalışma sahnesi:** Her zaman `Assets/` içinde durur. Her "Save Version" bu sahnenin bir kopyasını Prism'e versiyonlu olarak yazar.
- **Eski versiyonlar:** Eski bir versiyonu Prism'den açtığında kaydedilmemiş değişiklikler için Kaydet / At / Vazgeç diye sorulur.
- **Sınır:** Sahne dosyası modelleri, materyalleri ve shader'ları kopyalamaz, yalnızca onlara referans verir. Eski bir sahne versiyonu, kullandığı dosyalar projede durduğu sürece doğru açılır.

## Claude ile kullanım

1. Unity projesine **Unity AI Assistant** paketini (`com.unity.ai.assistant`) ekle. Prism araçları kendiliğinden Unity MCP'ye kaydolur: `prism_import`, `prism_update`, `prism_save_version`, `prism_playblast` ve diğerleri.
2. Claude'da `unity-mcp` bağlantısı açıkken, örneğin "Prism'deki lotus'un son versiyonunu al, sahneye koy, pembe bir URP Lit materyal ver, turntable al" diyebilirsin.
3. **Pencere açılmaz.** Claude'un başlattığı işlemler hiçbir pencere açmaz. Bir bilgi eksikse ya da işlem iş kaybettirebilecekse, örneğin isim değişen bir güncelleme veya yeni bir departman oluşturmak gibi, Claude bunu sana sorar ve ancak onay verirsen devam eder.
4. **Araçlar görünmezse:** **Prism → Debug → Re-register Claude (MCP) Tools** menüsünü kullan.

## Sorun giderme

- **"Prism was not found"**
  - Prism'in kurulu olduğu klasörü kontrol et (`PrismUnity.PrismRoot`, bkz. Kurulum 2).
- **"Unity is in Play Mode"**
  - Sahne veya asset değiştiren işlemler Play Mode'da çalışmaz.
- **"The Prism file is not reachable"**
  - Prism projesinin bulunduğu sürücünün (ör. `M:`) bağlı olduğunu kontrol et.
  - Bu durumda Unity'deki mevcut dosyaya dokunulmaz.
- **"The Prism project of this Unity project is not reachable"**
  - Unity projesinin bağlı olduğu Prism projesine ulaşılamıyor. Bağlantı `ProjectSettings/PrismUnity/project.json` dosyasında.
  - Sürücünün bağlı olduğunu kontrol et. Prism bu durumda pencere açmadan durur.
- **"Unity is not answering (it may be compiling scripts)"**
  - Unity script derlerken Prism'den gelen çağrılar kısa süre bekler, sonra bu mesajı verir. Derleme bitince tekrar dene.
- **Bir modelin formatı değişti (ör. FBX → OBJ)**
  - Güncelleme onay ister. Onaylarsan Unity yeni bir asset oluşturur. Sahnelerdeki ve materyallerdeki eski bağlantılar eski asset'te kalır.
- **Prism penceresi gelmiyor**
  - Prism Unity'den ilk kullanımda arka planda başlar. İlk çağrı bir dakikaya kadar sürebilir.
  - Prism çökerse bir sonraki işlemde kendiliğinden yeniden başlar.

## Geliştirme

```powershell
tools\run_py_tests.ps1                      # Prism tarafı birim testleri
tools\run_unity_tests.ps1                   # Unity EditMode testleri (TestProject)
tools\run_unity_tests.ps1 -Category E2E     # gerçek Prism + test Prism projesiyle
tools\run_all_tests.ps1 -E2E                # hepsi
```

Uçtan uca testler için:
- **Test Prism projesi:** `python tools/make_test_prism_project.py` ile oluşturulur. Varsayılan konumu `%USERPROFILE%\PrismUnityTest Project`.
- **Test FBX'leri:** Blender ile `blender -b -P fixtures/make_fbx.py -- <klasör>` komutuyla üretilir.
