# Prism ↔ Unity Entegrasyonu — Tasarım

Tarih: 2026-11-11
Durum: Taslak (onay bekliyor)

## 1. Amaç ve neden

Ekip, bir wellness uygulamasının 3D ekibi. Modeller Maya ve Blender'da üretiliyor, Prism Pipeline 2'de versiyonlanıyor, son durak Unity. Shader ve materyal işleri Unity'de, Claude'un yardımıyla (Unity MCP üzerinden) yapılacak.

Bugün Prism'in Unity eklentisi yok. Bu yüzden Prism'deki versiyonlu export'lar Unity'ye elle taşınıyor, hangi versiyonun Unity'de olduğu takip edilemiyor, Unity tarafındaki sahne ve önizleme çıktıları Prism'in dışında kalıyor.

Bu proje Prism'e bir **Unity app eklentisi** ekler. Böylece:

- Prism'deki asset'ler Unity'ye versiyon bilgisiyle gelir ve güncellenir,
- Unity sahneleri Prism'de versiyonlanır,
- Unity'den alınan playblast'ler Prism'in medya tarayıcısında görünür,
- bunların hepsi hem Unity menüsünden hem de Claude'dan (Unity MCP) yapılabilir.

## 2. Ana iş akışı

1. Maya veya Blender'da model yapılır. Prism'in mevcut eklentileri üzerinden **FBX** olarak versiyonlu export edilir (bu kısım zaten var, değişmiyor).
2. Unity'de Prism menüsünden ya da Claude'dan asset ve versiyon seçilir, `Assets/` içine import edilir.
3. Unity'de shader ve materyal kurulur. Prism'de yeni versiyon çıkınca Unity bunu bildirir. Güncelleme, kurulan materyal ve shader bağlantılarını bozmaz.
4. Unity sahnesi Prism'e versiyonlu kaydedilir.
5. Modelin turntable'ı (veya herhangi bir kameradan kayıt) playblast olarak Prism'e yazılır.

## 3. Hedefler (v1)

1. **Prism menüsü (Unity):** Project Browser, Save Version, Save Comment, Import, Check for New Versions, Playblast, Prism Settings.
2. **Import ve güncelleme:**
   - Prism ürünlerinin (product) versiyonlarını görmek ve import etmek. Desteklenen formatlar `.fbx`, `.obj`, `.abc`. `.abc` için Unity Alembic paketi gerekir. Paket yoksa kullanıcıya bunu söyler.
   - Import edilen her asset'in hangi Prism ürününden ve versiyonundan geldiği kaydedilir.
   - Daha yeni versiyon varsa bunu bildirir: proje açılışında (Prism'in `check_import_versions` ayarına uyarak) ve menüden elle tetiklenerek.
   - Tek tıkla güncelleme yapılır. Güncelleme yerinde olur: dosya aynı yolda yenilenir, Unity GUID'i (`.meta`) korunur. Böylece prefab, sahne ve materyal referansları bozulmaz.
3. **Unity sahnesi versiyonlama:**
   - Save Version ve Save Comment, çalışılan `.unity` sahnesini Prism'in sahne dosyası düzenine (entity / departman / görev / versiyon) versiyonlu kopya olarak yazar. Kopyanın yanında Prism'in normal versiyon bilgisi (kullanıcı, yorum, tarih) tutulur.
   - Çalışılan sahne her zaman `Assets/` içinde kalır.
   - Project Browser'dan bir versiyon açılınca o kopya `Assets/` içindeki çalışma yerine geri getirilip açılır. Kaydedilmemiş değişiklik varsa kullanıcıya sorulur.
   - Bilinen sınır: sahne dosyası modelleri, materyalleri ve shader'ları kopyalamaz, referans verir. Eski bir sahne versiyonu, bu dosyalar projede durduğu sürece doğru açılır. Bu kabul edildi. Paketleme ileride yapılacak (bkz. §9).
4. **Playblast:**
   - **Turntable modu (varsayılan):** Seçili obje(ler) için geçici kamera ve ışık kurar, 360° döndürerek kaydeder, sonra geçici kurulumu temizler. Sahne kirlenmez.
   - **Serbest mod:** Seçilen sahne kamerasından, verilen frame aralığı veya süre boyunca olduğu gibi kaydeder (animasyon, UI akışı vb.).
   - Ayarlar: çözünürlük, frame sayısı/süre, FPS, çıktı biçimi (görüntü dizisi; isteğe bağlı mp4).
   - Çıktı Prism'in playblast/medya konumuna versiyonlu yazılır ve Prism medya tarayıcısında görünür.
5. **Claude erişimi (Unity MCP):** Yukarıdaki her işlem Claude tarafından Unity MCP üzerinden çağrılabilir. Örnek: "Prism'deki lotus modelinin son versiyonunu al, sahneye koy, yeni shader'la materyal kur, turntable'ını al".
6. **Kurulum:** Unity eklentisi, Maya ve Blender eklentileri gibi Prism ayarlarındaki entegrasyon ekranından kurulur. Prism, seçilen Unity projesine eklentiyi bir paket olarak ekler; kaldırma da aynı ekrandan yapılır.

## 4. Hedef dışı (v1'de yok)

- Render ve Deadline gönderimi.
- Unity'den Prism'e model/obje export etme.
- Sahneyle birlikte kullandığı asset'leri paketleme.
- macOS ve Linux.
- Unity içinde Prism arayüzlerinin yeniden yazılması. Prism'in kendi Qt pencereleri (Project Browser, Save Comment vb.) kullanılır.

## 5. Kaçınılacaklar (çalışsa bile başarısızlık sayılır)

- Asset güncellemenin Unity'de kurulmuş materyal ve shader atamalarını, prefab referanslarını ya da sahnedeki yerleşimi kırması.
- Prism ile Unity arasındaki bağlantının uzaktan rastgele kod çalıştırmaya izin vermesi. After Effects eklentisi gelen her script'i çalıştırıyor. Bu eklentide yalnızca **tanımlı komutlar** kabul edilir, bağlantı yalnızca `127.0.0.1` üzerinden olur.
- Prism açılmadığında veya çöktüğünde Unity editörünün donması ya da kilitlenmesi. Tüm iletişim zaman aşımlı ve ana thread'i bloklamadan yapılır.
- Claude'un yapabildiği ile menünün yapabildiğinin ayrışması. İkisi aynı kod yolunu kullanır.
- Claude'un başlattığı bir işin ortasında bir pencere açılıp işin onu beklemesi (bkz. §8).

## 6. Kısıtlar ve ortam

- **Prism:** Prism 2, `C:\Program Files\Prism2` altında kurulu (gömülü `Python313`, `Tools\FFmpeg` dahil). App eklentileri Prism Hub ile `C:\ProgramData\Prism2\plugins` altına kuruluyor. Mevcut Maya eklentisi v2.1.2.4, Blender eklentisi v2.1.2. Referans kaynak: GitHub `PrismPipeline/Prism` 2.1.4.3. Eklenti kurulu sürümle çalışmalı, gerekirse referans kaynakla karşılaştırılmalı.
- **Unity:** Hedef sürüm **`6000.5.6f1`** (ekip kararı). Render pipeline **URP** *(benim kararım)*. Bu sürüm makinede henüz kurulu değil, Unity Hub ile kurulması gerekiyor. Makinede şu an `6000.0.83f1` ve `6000.6.0f1` var. Eklentinin bu sürümlerde de derlenmesi iyi olur ama zorunlu değil.
- **Unity'de Python ve Qt yok.** Bu yüzden Prism'in Unreal'daki gibi editörün içinde çalışması mümkün değil. Model, After Effects ve Photoshop eklentileriyle aynı: Prism ayrı bir süreç olarak çalışır.
- **DCC'ler:** Maya 2023, Blender 4.x/5.x. Bunların Prism eklentileri bu projede değişmez.
- **Platform:** Windows.
- **Unity MCP:** Unity'nin resmi MCP köprüsü (`~/.unity/relay/relay_win.exe`), açık bir Unity editörüne bağlanır. Hangi araçları sunduğu, editör açık olmadan görülemedi (bkz. §8).
- **Proje durumu:** Wellness uygulamasının Unity projesi ve Prism projesi henüz yok. Geliştirme için bir test Unity projesi ve bir test Prism projesi kurulacak.
- **Lisans:** Prism LGPL. Eklenti Prism'in eklenti arayüzünü kullanır, Prism koduna dokunmaz.

## 7. Mimari

İki parça, iki yönlü yerel bağlantı:

```
┌──────────────────────── Unity Editor ────────────────────────┐
│  UPM paketi (C#, yalnızca Editor)                            │
│   ├─ Prism menüsü ──┐                                        │
│   ├─ MCP araçları ──┼──► PrismUnity API (tek ortak katman)   │
│   └─ Komut sunucusu ┘     import / sahne / playblast / sorgu │
│        ▲ 127.0.0.1, JSON komutlar                            │
└────────┼─────────────────────────────────────────────────────┘
         │                          ▲ "aç / kaydet / browser" istekleri
         ▼                          │
┌──────────────── Prism süreci (Python313 + Qt) ───────────────┐
│  Prism "Unity" app eklentisi (PluginEmpty şablonundan)       │
│   ├─ Prism_Unity_Functions: sendCmd ile Unity'ye komut       │
│   ├─ MenuTools girişi: tek örnek, komut dinleyici            │
│   └─ Integration: Unity projesine paketi kur/kaldır          │
│  Prism çekirdeği: Products, PathManager, MediaProducts...    │
└──────────────────────────────────────────────────────────────┘
```

**7.1 Prism tarafı: `Unity` app eklentisi (Python)**
- `PluginEmpty` şablonundan türetilir. Şablondaki dosya düzeni kullanılır: `_init`, `_Variables`, `_Functions`, `_Integration`, `_externalAccess_Functions`.
- `_Variables`: `pluginName = "Unity"`, `sceneFormats = [".unity"]`, `outputFormats` Unity'nin import edebildikleri, platform Windows.
- `_Functions`: Prism'in app eklentisinden beklediği fonksiyonlar (`getCurrentFileName`, `saveScene`, `openScene`, `getFrameRange`, `getFPS`, import ve playblast hook'ları vb.) Unity'ye komut gönderilerek uygulanır.
- After Effects'teki `Prism_AfterEffects_MenuTools.py` modeli izlenir. Unity bir komut istediğinde Prism'in Python'u başlatılır. Prism zaten açıksa komut çalışan örneğe iletilir (tek örnek). Unity kapanınca Prism kendini kapatır (PID takibi).
- `_Integration`: Prism ayarlarındaki entegrasyon ekranında bir Unity projesi klasörü seçilir. Paket bu projeye eklenir (`Packages/manifest.json` üzerinden yerel paket referansı), kaldırma da aynı şekilde yapılır.

**7.2 Unity tarafı: UPM paketi (C#, yalnızca Editor assembly)**
- **PrismUnity API:** Tüm işlemlerin tek kapısı. Menü, Prism'den gelen komutlar ve MCP araçları hep bunu çağırır.
- **Komut sunucusu:** Yalnızca `127.0.0.1` üzerinde dinler. Kabul ettiği komutlar sabit ve tanımlıdır (örnek: `getCurrentFile`, `saveScene`, `openScene`, `getFrameRange`, `setFrameRange`, `getFPS`, `importProduct`, `updateProduct`, `listImported`, `playblast`, `getPid`). Unity API'leri ana thread'de çalışmak zorunda olduğu için gelen istekler ana thread'e kuyrukla aktarılır.
- **Prism menüsü:** Menü öğeleri Prism sürecine istek gönderir. Prism'in kendi pencerelerini (Project Browser, Save Comment, Settings) Prism açar.
- **İçe aktarım kaydı:** Hangi Unity asset'inin hangi Prism ürünü ve versiyonundan geldiği proje içinde tutulur. Kayıt sürüm kontrolüne girebilmeli, ekip aynı bilgiyi görmeli.
- **Playblast:** Turntable ve serbest mod. Görüntü dizisi Unity'de üretilir, mp4 gerekirse Prism'in `Tools\FFmpeg` aracıyla kodlanır.
- **MCP araçları:** bkz. §8.

**7.3 Import yeri ve güncelleme kuralı** *(benim kararım)*
- Her ürün sabit bir yola gelir: `Assets/Prism/<entity>/<ürün>/`. Yolda versiyon numarası yer almaz.
- Güncelleme aynı dosyanın üstüne yazar. `.meta` ve GUID korunur, bu yüzden referanslar ve materyal atamaları yerinde kalır.
- Versiyon bilgisi dosya yolunda değil, içe aktarım kaydında tutulur.

**7.4 Prism varlık modeli ile eşleme** *(benim kararım)*
- **Sahneler:** Prism'in `saveScene` fonksiyonu, mevcut dosya Prism projesinin içinde değilse kaydetmeyi reddeder. Çalışılan sahne ise `Assets/` içinde duruyor. Bu yüzden eklenti, her çalışma sahnesinin hangi Prism entity / departman / görevine bağlı olduğunu kaydeder. Bu eşleme içe aktarım kaydıyla aynı yerde tutulur. Bir `.unity` dosyası tek bir Prism görevine bağlanır.
- **İlk kayıt:** Prism'e hiç kaydedilmemiş bir sahnede Save Version, kullanıcıya (ya da Claude'a parametre olarak) entity, departman ve görevi sorar. Sonraki kayıtlar bu eşlemeyi kullanır.
- **Entity tipi:** Wellness uygulamasında shot yapısı beklenmediği için Unity sahneleri varsayılan olarak Prism **asset** entity'si altında tutulur (örnek: `Scenes/MeditationRoom`). Shot entity'leri de desteklenir.
- **Departman:** Prism projesinde varsayılan olarak `Unity` adında bir departman kullanılır. Projede yoksa eklenti oluşturulmasını önerir.
- **Project Browser'dan açılan sahne**, eşlemesinden bulunan çalışma yoluna gelir. Eşleme yoksa `Assets/Scenes/<entity>/<görev>.unity` yoluna gelir.
- **Playblast yeri:** Turntable, döndürülen modelin kendi Prism asset'i altına yazılır (örnek: lotus turntable'ı lotus asset'inde görünür). Serbest mod, sahnenin bağlı olduğu entity altına yazılır.

**7.5 "Yeni versiyon" tanımı** *(benim kararım)*
- Prism'in Maya ve Blender eklentilerindeki davranış birebir izlenir: `master` dahil en son versiyon. Böylece ekip her programda aynı "en son" anlamını görür.
- İçe aktarım kaydında hangi versiyonun (veya master'ın) alındığı ve hangi konumdan (local/global) geldiği tutulur.

**7.6 Unity projesi ↔ Prism projesi bağlantısı** *(benim kararım)*
- Her Unity projesi bağlı olduğu Prism projesini kendi içinde saklar. Eklenti Prism'i bu projeyle başlatır. Kullanıcının Maya'da en son hangi projeyi açtığı önemli değildir.
- Bir Prism projesi birden fazla Unity projesini besleyebilir. Başka bir Unity projesinden kaydedilmiş bir sahne versiyonu açılırken kullanıcı uyarılır.

**7.7 Güncellemede isim ve yapı değişiklikleri** *(benim kararım)*
- GUID korunsa bile Unity materyal eşlemelerini ve prefab override'larını node ve slot **adıyla** tutar. Yeni versiyonda mesh, materyal slotu veya hiyerarşi node'u yeniden adlandırılmış ya da silinmişse bağlantılar kırılabilir.
- Güncelleme öncesi eklenti eski ve yeni dosyayı karşılaştırır. Ad değişikliği veya silme varsa bir fark listesi gösterir ve onay ister. Claude'a da aynı fark listesi sonuç olarak döner, Claude onaysız güncellemez.
- Varsayılan materyal atama yöntemi FBX import ayarlarındaki materyal eşlemesidir (`.meta` içinde). Ekipte Maya ve Blender için "export'lar arasında node ve materyal adları değişmez" kuralı önerilir.

## 8. Claude ve Unity MCP

- Hedef: menüdeki her işlemin Claude'dan da çağrılabilmesi.
- Unity MCP köprüsünün özel araç tanımlamaya izin verip vermediği henüz doğrulanmadı. Builder ilk iş olarak test projesinde editörü açıp bunu kontrol eder.
  - **Özel araç tanımlanabiliyorsa:** Paket, PrismUnity API'sini Prism araçları olarak kaydeder (`prism_list_products`, `prism_import`, `prism_update`, `prism_save_version`, `prism_playblast` vb.).
  - **Tanımlanamıyorsa:** Claude, köprünün genel araçlarıyla (menü çağırma veya editörde kod çalıştırma) aynı PrismUnity API'sini çağırır. API bu yüzden kısa, belgelenmiş, parametreleri basit olacak şekilde tasarlanır.
- **Claude'un başlattığı işlerde hiç pencere açılmaz (ekip kararı).** Her işlemin iki çağrılma şekli vardır:
  - **Etkileşimli (menüden):** Prism'in ve Unity'nin normal pencereleri açılır.
  - **Etkileşimsiz (Claude'dan):** Gereken her bilgi parametreyle gelir. Örnekler: yorum, entity, departman, görev, kaydedilmemiş değişiklik olduğunda kaydet / at / vazgeç seçimi, güncelleme fark listesinin onayı. Eksik bilgi ya da onay gerektiren bir durum pencere açmaz, açıklayıcı bir hata olarak Claude'a döner. Claude bunu kullanıcıya sorup yeniden çağırır.
  - Bu kural Prism tarafını da kapsar. Etkileşimsiz modda Prism'in `popup`, kaydetme uyarıları ve versiyon seçici gibi pencereleri bastırılır. Bunların yerine Prism çekirdeğinin fonksiyonları doğrudan, parametrelerle çağrılır. Bastırılamayan bir pencere varsa bu bir hata sayılır ve işlem güvenli şekilde iptal edilir.
- Uzun süren işler (playblast, toplu güncelleme) Claude'a anlaşılır bir sonuç döndürür: başarı veya hata, üretilen dosya yolları, versiyon numaraları.
- Paket içine, Claude'un bu araçları nasıl kullanacağını anlatan kısa bir rehber dosya konur.

## 9. Sonradan yapılacaklar (v1 sonrası)

Kabaca öncelik sırasıyla:

1. **Sahneyle birlikte asset paketleme:** Sahne versiyonu kaydedilirken kullandığı model, materyal, shader ve dokuları da yanında saklama. Eski versiyonlar bu sayede birebir geri gelir.
2. **Materyal ve shader'ları Prism'de versiyonlama:** Unity'de yazılan shader'lar (Shader Graph, `.shader`, `.mat`) Prism ürünü olarak yayınlanır. Ekip ve diğer Unity projeleri bunları paylaşabilir.
3. **Unity'den Prism'e export:** Unity FBX Exporter ile sahne veya prefab'ı Prism ürünü olarak dışa aktarma.
4. **Unity içinde asset tarayıcı:** Prism ürünlerini thumbnail'larla Unity penceresinde göstermek, sürükle-bırak import. v1'de Prism'in kendi penceresi kullanılıyor.
5. **Otomatik güncelleme izleme:** Prism'de yeni versiyon yayınlanınca Unity'de anında bildirim. İstenirse ayarla otomatik güncelleme.
6. **Mobil uygunluk kontrolleri:** Import sırasında poligon sayısı, doku boyutu, materyal sayısı gibi wellness uygulamasının hedef cihazlarına göre uyarılar. Prism'in kendi export kontrolleriyle birleştirilebilir.
7. **Doku pipeline'ı:** Substance veya diğer kaynaklardan gelen doku setlerini Prism ürünü olarak alıp Unity materyallerine otomatik bağlama.
8. **USD ve glTF desteği:** Gerekirse ek import formatları.
9. **Render ve Deadline:** Unity Recorder veya Deadline ile yüksek kaliteli render çıktıları.
10. **Prism Hub dağıtımı:** Eklentiyi diğer Prism eklentileri gibi Hub üzerinden kurulabilir ve güncellenebilir yapmak.
11. **macOS desteği.**
12. **"Kayıtlı versiyonları geri yükle":** Import edilen modeller sürüm kontrolüne konmazsa, her makinenin içe aktarım kaydına bakıp doğru versiyonları Prism'den kendisi çekmesi.
13. **Toplu işlemler (Claude için):** "Bu sahnedeki tüm Prism asset'lerini güncelle ve hepsinin turntable'ını al" gibi tek komutla çoklu iş.

## 10. Test yaklaşımı

- Test Prism projesi: içinde birkaç asset, Maya'dan ve Blender'dan FBX export'ları, her biri en az iki versiyonlu.
- Test Unity projesi: Unity `6000.5.6f1`, URP, paket Prism entegrasyon ekranından kurulmuş.
- Kabul senaryoları:
  1. Import, materyal atama, yeni versiyonla güncelleme: materyal ve sahnedeki yerleşim korunuyor.
  2. Sahne Save Version: Prism'de versiyon görünüyor. Eski versiyon açılınca doğru sahne geliyor.
  3. Turntable playblast: Prism medya tarayıcısında görünüyor, sahne değişmemiş.
  4. 1–3 arası senaryolar Claude üzerinden de yapılabiliyor ve hiçbirinde pencere açılmıyor. Eksik parametre verildiğinde pencere yerine açıklayıcı hata dönüyor.
  5. Prism kapalıyken veya çökmüşken Unity donmuyor, anlaşılır bir hata veriyor.
  6. Bağlantıya tanımsız bir komut gönderilince reddediliyor.

## 11. Builder'a bırakılanlar

- Komut protokolünün tam biçimi, port seçimi (birden fazla Unity editörü aynı anda açıkken çakışma önleme dahil) ve zaman aşımı değerleri.
- İçe aktarım kaydının dosya biçimi ve yeri (sürüm kontrolüne uygun olması şartıyla).
- Playblast yakalamanın Unity Recorder ile mi yoksa özel kodla mı yapılacağı.
- Prism'in hangi hook'larının v1'de gerçekten gerektiği. `PluginEmpty`'deki kullanılmayanlar boş bırakılabilir.
- Paketin `Packages/` altına nasıl bağlanacağı (yerel yol referansı veya kopya).

## 12. Benim verdiğim kararlar (ekip onayı bekliyor)

- Render pipeline URP.
- Varsayılan format FBX. OBJ ve ABC ek olarak desteklenir.
- Import yolu `Assets/Prism/<entity>/<ürün>/`, versiyon dosya yolunda değil, içe aktarım kaydında.
- Prism ile Unity arasında yalnızca tanımlı komutlar, rastgele kod çalıştırma yok.
- v1'de Prism'in kendi pencereleri kullanılır, Unity içinde yeni arayüz yok.
- Git ile paylaşımda büyük dosyalar için **Git LFS** kullanılır. `Assets/Prism/**` altındaki import edilmiş modeller, `.meta` dosyaları ve içe aktarım kaydı commit'lenir. Böylece herkes aynı dosyaları görür ve v1'de "geri yükle" özelliğine gerek kalmaz (bkz. §9.12). Aynı ürünün iki kişi tarafından aynı anda güncellenmesi durumunda normal Git çakışması olarak çözülür. İçe aktarım kaydı, çakışmayı kolaylaştırmak için ürün başına ayrı küçük dosyalar halinde tutulur.
- Unity sahneleri varsayılan olarak Prism **asset** entity'si altında, `Unity` departmanında tutulur (bkz. §7.4).
- Turntable, modelin kendi asset'i altına yazılır. Serbest mod playblast, sahnenin entity'si altına yazılır.
- "Yeni versiyon", Prism'in Maya ve Blender eklentilerindeki gibi master dahil en son versiyondur.
- Her Unity projesi kendi Prism projesini sabitler.
- Güncellemede ad değişikliği veya silme varsa fark listesi gösterilir ve onay istenir.

## 13. Ekip kararları

- v1 kapsamına Unity sahnesi versiyonlama ve playblast dahil.
- Playblast: öncelik turntable, ama herhangi bir kameradan serbest kayıt da olmalı.
- DCC'ler: Maya ve Blender.
- Unity sürümü: `6000.5.6f1`.
- Claude'a verilen işlerde hiçbir pencere açılmaz.
- Unity projesi ekipte Git ile paylaşılır (ekip "sanırım" dedi; kesinleşmesi bekleniyor).
