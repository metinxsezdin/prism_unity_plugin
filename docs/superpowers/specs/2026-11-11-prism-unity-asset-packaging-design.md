# Prism ↔ Unity: Asset Paketleme (Prefab, Tanım Dosyası, Addressables) — Tasarım

Tarih: 2026-11-11
Durum: Taslak
Önceki tasarım: `docs/superpowers/specs/2026-11-11-prism-unity-entegrasyonu-design.md` (v1, tamamlandı)

## 1. Amaç

v1'de Prism'den gelen bir model Unity'de yalnızca bir FBX, OBJ ya da ABC dosyası olarak duruyor. Uygulamayı yazan kişinin bu modeli kullanabilmesi için her obje için elle prefab yapması, Addressable olarak işaretlemesi ve objeyi kodda tanımlayan bir veri dosyası oluşturması gerekiyor.

Bu iş, Prism'den gelen her objeyi Unity'de **kullanıma hazır bir paket** olarak kurar. Paket şunlardan oluşur:
- bir prefab
- objeyi tanımlayan bir ScriptableObject
- bir Addressable adresi
- bir küçük resim

Bütün paketler tek bir katalogda listelenir.

Objelere koddan nasıl ulaşılacağı obje tipine göre değişebilir. Ekip bunu henüz bilmiyor, karar şu: her obje için **iki yol birlikte** kurulur.
- **Tanım dosyası üzerinden:** Kod tanım dosyasına ya da kataloğa referans verir.
- **Addressable adresiyle:** Kod objeyi adresiyle yükler.

## 2. Ekip kararları

- Her obje için prefab, tanım dosyası ve Addressable birlikte kurulur.
- Küçük resim Prism'in önizlemesinden alınır.
- Bölüm 4'teki katalog, sonradan oluşturma, silinen ürün uyarısı, ayarlar sayfası ve Claude bilgileri kapsama dahil.

## 3. Hedefler

### 3.1 Paket
Bir ürün import edildiğinde `Assets/Prism/<entity yolu>/<ürün>/` klasöründe şunlar bulunur:

| Dosya | Ne | Kim değiştirir |
|---|---|---|
| `<ürün>.fbx` (veya `.obj`, `.abc`) | Model. v1'deki gibi, güncellemede yenilenir. | Eklenti |
| `<ürün>.prefab` | Modelden türetilmiş **prefab variant**. Ekip buna component, collider, materyal ve script ekler. | Ekip (eklenti yalnızca ilk kez oluşturur) |
| `<ürün>.asset` | **Tanım dosyası** (`PrismAssetDefinition` ya da ekibin ondan türettiği bir sınıf). | Prism alanlarını eklenti, ekip alanlarını ekip değiştirir |
| `<ürün>_thumb.png` | Küçük resim. | Eklenti |

Yeni versiyon geldiğinde:
- Model yenilenir.
- Prefab variant'a dokunulmaz. Modeldeki değişiklik variant'a kendiliğinden geçer, ekibin eklemeleri korunur.
- Tanım dosyasında yalnızca eklentinin alanları güncellenir.
- Küçük resim yenilenir.

İsim değişikliğinde onay isteme kuralı v1'deki gibi kalır. Variant'taki override'lar da adla bağlı olduğu için bu kural burada daha da önemli.

### 3.2 Tanım dosyası (`PrismAssetDefinition`)
Oyun koduna açık bir ScriptableObject sınıfı. Sınıf, yeni bir **runtime asmdef** olan `Prism.Assets` içinde durur, böylece oyun kodu ona referans verebilir.

Eklentinin yönettiği alanlar:

| Alan | Tip | Anlam |
|---|---|---|
| `displayName` | string | Varsayılan olarak entity adı, ör. "Lotus". Ekip değiştirirse eklenti bir daha üzerine yazmaz. |
| `entityType`, `entityPath` | string | Prism'deki yeri, ör. `asset`, `Props/Lotus` |
| `product` | string | Ürün adı, ör. `lotus_model` |
| `version`, `contentVersion` | string | Unity'deki versiyon. `master` ise içerdiği numaralı versiyon da tutulur. |
| `addressableKey` | string | Prefab'ın sabit adresi |
| `prefab` | `AssetReferenceGameObject` | Prefab'a Addressable referansı |
| `thumbnail` | `AssetReferenceTexture2D` | Küçük resme Addressable referansı |
| `prismMissing` | bool | Ürün Prism'de artık yoksa true (bkz. 3.6) |

Ekibin kendi alanları için şu yol izlenir:
- Ekip `PrismAssetDefinition`'dan bir sınıf türetir, ör. `WellnessItemDefinition : PrismAssetDefinition`, ve kategori, kilit açma koşulu gibi alanları oraya ekler.
- Ayarlar sayfasında hangi sınıfın kullanılacağı seçilir. Eklenti yeni tanım dosyalarını bu sınıfla oluşturur ve yalnızca yukarıdaki alanlara yazar.

### 3.3 Addressables
- **Adres:** Prefab Addressable olarak işaretlenir. Adres sabittir, versiyon içermez. Varsayılan biçim `<entity yolu>/<ürün>`, ör. `Props/Lotus/lotus_model`.
- **Grup:** Entity yolunun ilk klasörüne göre, ör. `Prism Props`, `Prism Scenes`. Grup yoksa varsayılan ayarlarla oluşturulur.
- **Etiketler:** `prism`, entity'nin ilk klasörü (ör. `Props`) ve ürün adı.
- **Diğer Addressable'lar:** Küçük resim ve tanım dosyası da Addressable olur, aynı grupta, adresin sonuna `#thumb` ve `#definition` eklenerek.
- **Adres çakışması:** Aynı adrese başka bir asset kayıtlıysa eklenti üzerine yazmaz, uyarır.
- **Paket gereksinimi:** `com.unity.addressables` projede yüklü olmalı. Yüklü değilse eklenti bunu söyler ve yalnızca prefab variant'ı kurar. Tanım dosyası, katalog ve Addressable kaydı yapılmaz.

### 3.4 Katalog (`PrismAssetCatalog`)
- Bütün tanım dosyalarını listeleyen tek bir ScriptableObject: `Assets/Prism/PrismAssetCatalog.asset`.
- Kendisi de Addressable'dır, adresi `PrismAssetCatalog`.
- Eklenti her import, güncelleme ve sonradan oluşturma işleminde listeyi günceller. Listeyi entity yolu ve ürün adına göre sıralı tutar.
- Kod "bütün ortamlar" gibi listeleri buradan okur. Basit sorgu yardımcıları olur: entity yoluna göre, ilk klasöre göre ve tanım tipine göre filtreleme.

### 3.5 Önceden import edilmiş objeler
- **Prism → Generate Missing Asset Packages** menüsü (ve aynı işi yapan bir Claude aracı), v1 ile import edilmiş ama paketi olmayan her ürün için prefab, tanım dosyası, küçük resim ve Addressable kaydını oluşturur.
- Komut güvenle tekrar çalıştırılabilir: var olan prefab ve tanım dosyalarına dokunmaz, yalnızca eksikleri tamamlar.

### 3.6 Silinen ya da adı değişen ürünler
- Prism'de bir ürün artık yoksa Unity'deki paket **silinmez**, çünkü oyun kodu ona bağlı olabilir.
- Bunu tespit etmek için Prism tarafındaki versiyon kontrolü, ürünü "proje erişilebilir ama bu ürün yok" ve "proje erişilemiyor" diye iki ayrı durumda raporlar. "Ürün yok" durumunda tanım dosyasında `prismMissing = true` olur ve "Check for New Versions" penceresi bunu ayrı bir uyarıyla gösterir.
- Ürün geri gelirse ya da yeniden import edilirse `prismMissing` false olur.

### 3.7 Ayarlar sayfası (**Project Settings → Prism**)
Mevcut ve yeni ayarlar tek bir yerde toplanır:
- **Makineye özel (EditorPrefs):** Prism kurulum klasörü.
- **Bağlı Prism projesi (yeri değişmiyor: `ProjectSettings/PrismUnity/project.json`):**
  - Görüntülenir.
  - Aynı Prism projesi başka bir sürücüye ya da klasöre taşındıysa yeni `pipeline.json` gösterilebilir. Eklenti, yeni yoldaki projenin adının eskisiyle aynı olduğunu kontrol eder, değilse reddeder. Bir sonraki çağrıda Prism süreci yeniden başlatılır.
  - Farklı bir projeye geçmek bu sayfadan yapılmaz (bkz. 4).
- **Proje ayarları (`ProjectSettings/PrismUnity/settings.json`):**
  - **Paketleme:** Açık / kapalı. Varsayılan açık. Kapalıysa v1 davranışı geçerlidir, yalnızca model import edilir.
  - **Tanım sınıfı:** `PrismAssetDefinition` ya da ondan türetilmiş bir sınıf.
  - **Addressable adres biçimi:** Varsayılan `{entity}/{product}`.
  - **Grup adı biçimi:** Varsayılan `Prism {category}`.

### 3.8 Claude
- **Import ve güncelleme cevabı:** `prism_import` ve `prism_update` cevabına bir `package` alanı eklenir: `{prefabPath, definitionPath, addressableKey, thumbnailPath}`.
- **`prism_list_imported`:** Her kayıtta aynı `package` bilgisini döner.
- **Yeni araç `prism_generate_packages`:** Eksik paketleri oluşturur (3.5).
- **Rehber:** `CLAUDE_TOOLS.md`'ye paketlerin nasıl kullanılacağı eklenir. Örneğin bir objeyi Addressable adresiyle yükleyen ya da katalogdan okuyan kod nasıl yazılır.

### 3.9 Küçük resim
Kaynak sırası:
1. O versiyonun Prism ürün önizlemesi (`products.getProductPreviewPath`)
2. Yoksa entity'nin Prism önizlemesi (`entities.getEntityPreviewPath`)
3. İkisi de yoksa Unity'de modelin tek karelik turntable render'ı (v1'deki `TurntableRig` ve `FrameCapture` ile, 256×256)

Prism önizlemesinin yolu, Prism'in versiyon çözümlemesi (`resolveVersion`) cevabına `previewPath` olarak eklenir. Böylece hem Claude'un hem de Prism'den başlatılan import'lar aynı yolu izler. Unity resmi `<ürün>_thumb.png` olarak kopyalar ve küçük, mipmap'siz bir doku olarak içe aktarır.

### 3.10 Paketlerin projeyle birlikte taşınması (gömülü paketler)
Oyunun build'i ve oyun kodu artık `Prism.Assets` sınıflarına bağlı olacak. Tanım ve katalog dosyaları da Git'e girecek. Bu yüzden eklentinin kurulu olmadığı makinelerde de proje derlenmeli ve açılmalı: uygulamayı yazan kişi, CI ve build makineleri.

v1'de Prism entegrasyonu `com.prism.unity` paketini `Packages/manifest.json` dosyasına makineye özel mutlak bir `file:` yoluyla ekliyordu. Bu yol her makinede farklı olabilir ve Git'te paylaşılan manifest'i bozar. Bu iş bunu da düzeltir:
- **İki gömülü paket:** Prism entegrasyonu paketleri Unity projesinin içine, gömülü paket olarak kopyalar:
  - `Packages/com.prism.unity/`: editor tarafı, v1'deki paket
  - `Packages/com.prism.assets/`: yeni runtime paketi. İçinde `Prism.Assets` asmdef'i, `PrismAssetDefinition`, `PrismAssetCatalog` ve sorgu yardımcıları bulunur.
- **Git'te:** İkisi de projeyle birlikte Git'e girer. `manifest.json` dosyasında makineye özel yol kalmaz.
- **Güncelleme:** Prism ayarlarındaki Unity bölümünden "yeniden kur" seçilir. Paketlerin versiyonu `package.json`'da durur, eklenti eski bir kopyayı görürse uyarır.
- **Prism'siz makineler:** Prism kurulu olmayan bir makinede editor paketi derlenir ama Prism özellikleri çalışmaz. Prism menüsü bunu anlaşılır bir hatayla bildirir (v1'deki `prism_unavailable`). `com.prism.assets` yalnızca Unity'ye bağlıdır.
- **Repodaki `TestProject`:** Geliştirme için repo içi göreli yolu kullanmaya devam eder.

### 3.11 Tanım sınıfı sonradan değiştirilirse
- Ayarlardan farklı bir tanım sınıfı seçildiğinde eklenti, var olan tanım dosyalarını yeni sınıfa çevirmeyi önerir: **Convert Definitions to Selected Class**. Claude için de aynı işi yapan bir araç olur.
- Çevirme, dosyanın script referansını değiştirir. Aynı adlı bütün alanlar (Prism alanları dahil) korunur, GUID değişmez. Böylece oyun kodundaki ve katalogdaki referanslar kırılmaz.
- Önce kaç dosyanın çevrileceği gösterilir ve onay istenir.

## 4. Hedef dışı

- Prism'de bir ürünün adı değişirse paketi yeni ürüne yeniden bağlama ("re-link"). Bu sürümde yeniden adlandırma, eski paketin `prismMissing` olması ve yeni adla ayrı bir paket oluşması demektir. Yeniden bağlama sonraya kaldı.
- Ayarlar sayfasından **farklı** bir Prism projesine geçmek. Sayfa yalnızca aynı projenin yeni konumunu göstermeye izin verir (bkz. 3.7).

- Her obje için ayrı bir asmdef. Objelere ait scriptleri ekip kendi asmdef'lerinde yazar, eklenti asmdef üretmez (yalnızca `Prism.Assets` vardır).
- Addressables build, profil, uzak içerik ve CDN ayarları. Bunlar ekibin Addressables kurulumuna aittir.
- Obje tiplerine göre farklı kurallar (dekor, ödül, etkileşimli obje gibi). Tipler netleşince ekip türetilmiş tanım sınıfları ya da etiketlerle ayırabilir.
- Oyun kodu üretmek, örneğin her obje için yükleyici script yazmak.

## 5. Kaçınılacaklar

- Ekibin prefab'a ya da tanım dosyasındaki kendi alanlarına yaptığı herhangi bir değişikliğin güncellemede kaybolması.
- Var olan bir Addressable adresinin, grubunun ya da başka bir asset'in sessizce değiştirilmesi.
- Prism'de silinen bir ürün yüzünden Unity'de bir şeyin otomatik silinmesi.
- v1 davranışının bozulması. Paketleme kapalıyken her şey v1'deki gibi çalışmalı.
- Claude'un başlattığı işlemlerde pencere açılması (v1 kuralı).

## 6. Kısıtlar

- v1'in bütün kısıtları geçerli: Windows, Unity 6000.5 + URP, Prism 2.1.x, loopback köprü, kilitlenme kuralı (bekleyen taraf geri çağrılmaz), pencere açmama.
- Addressables paketi: Unity 6000.5 ile uyumlu sürüm. Hangi sürüm olacağına builder karar verir.
- `Prism.Assets` runtime assembly'si oyuna girer. Küçük olmalı, yalnızca tanım ve katalog sınıflarını ve basit sorgu yardımcılarını içermeli. Editor koduna bağımlı olmamalı.
- Addressables'a bağlı kod, Addressables yokken de derlenmelidir. Bunun için v1'deki MCP adaptörü gibi `versionDefines` yöntemi kullanılır.

## 7. Builder'a bırakılanlar

- Addressables sürümü ve API ayrıntıları (`AddressableAssetSettings`, grup şablonu).
- Katalog sorgu yardımcılarının tam imzaları.
- Küçük resim doku ayarları.
- `settings.json` biçimi ve ayarlar sayfasının görünümü.

## 8. Benim verdiğim kararlar (ekip onayı bekliyor)

- Prefab, modelden türetilmiş bir **prefab variant**. Ekip eklemelerini variant'a yapar.
- Tanım dosyası Addressable referanslarıyla tutulur (`AssetReference…`). Böylece katalog yüklenince bütün prefab'lar belleğe girmez.
- Ekip kendi alanları için `PrismAssetDefinition`'dan türetilmiş bir sınıf kullanır, sınıf ayarlardan seçilir.
- Adres `{entity}/{product}`. Gruplar entity'nin ilk klasörüne göre. Etiketler `prism`, ilk klasör ve ürün adı.
- Addressables yoksa yalnızca prefab variant kurulur.
- Katalog `Assets/Prism/PrismAssetCatalog.asset`, adresi `PrismAssetCatalog`.
- Ürün Prism'den silinirse paket silinmez, `prismMissing` işaretlenir.
- Küçük resim kaynak sırası: ürün önizlemesi → entity önizlemesi → Unity render'ı.
- Ayarlar `ProjectSettings/PrismUnity/settings.json` dosyasında, Prism yolu EditorPrefs'te kalır. Proje bağlantısı `project.json`'da kalır.
- Hem `com.prism.unity` hem de yeni `com.prism.assets` Unity projesine **gömülü paket** olarak kopyalanır ve Git'e girer (3.10). Bu, v1'deki makineye özel `file:` yolu sorununu da kapatır.
- Ürün adı değişikliğinde yeniden bağlama bu sürümde yok (4).
- Ayarlar sayfasında proje yalnızca aynı projenin yeni konumuna değiştirilebilir (3.7).
- Tanım sınıfı değişince var olan tanım dosyaları onayla çevrilir, GUID'ler korunur (3.11).
