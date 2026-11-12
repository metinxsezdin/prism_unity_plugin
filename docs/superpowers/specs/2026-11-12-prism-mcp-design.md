# Prism MCP — Tasarım

Tarih: 2026-11-12
Durum: Taslak (onay bekliyor)

## 1. Amaç ve neden

Ekip, bir wellness uygulamasının 3D ekibi. Modeller Maya ve Blender'da yapılıyor, Prism Pipeline 2'de versiyonlanıyor, Unity'ye geliyor. Prism ↔ Unity entegrasyonu ([2026-11-11-prism-unity-entegrasyonu-design.md](2026-11-11-prism-unity-entegrasyonu-design.md)) Claude'a Unity MCP üzerinden `prism_*` araçları veriyor; ama bu araçlar yalnızca Unity açıkken ve Unity'nin gözünden çalışıyor (import, güncelleme, sahne kaydı, playblast).

Ekip Prism'de elle yaptığı işleri Claude'a söyleyip geçmek istiyor:

- projede ne var, kim ne publish etti, hangi versiyon master, hangi asset'in modeli yok,
- Maya/Blender ekibine iş açmak (asset, shot, department, task),
- versiyonları toparlamak (master, yorumlar, yeniden adlandırma, omit, silme).

Bu proje, **Unity'den tamamen bağımsız** bir **Prism MCP sunucusu** ekler. Claude Code'a kayıtlı bir stdio MCP sunucusu olarak çalışır, Prism'in Python çekirdeğini pencere açmadan (`noUI`) yükler ve Prism projesinde doğrudan çalışır.

## 2. Hedefler

1. Claude, Unity kapalıyken de Prism projesini sorgulayabilir ve raporlayabilir.
2. Claude, Prism'de asset, kategori, sequence, shot, department ve task açabilir; açıklama, metadata, önizleme resmi ve shot frame aralığı yazabilir.
3. Claude, versiyonları yönetebilir: master yapma/silme, yorum düzenleme, shot/sequence/episode yeniden adlandırma, omit/geri alma, shot silme.
4. Claude, aktif Prism projesini değiştirebilir (bkz. §5).
5. Ekipteki herkes, repoyu çektikten sonra tek bir çift tıklamayla kurabilir (bkz. §8).

## 3. Hedef dışı

- **Publish etmek.** Model ve sahne export'u sanatçının Maya/Blender'ındaki Prism eklentisiyle yapılır. Sunucu yeni ürün versiyonu üretmez.
- **Maya, Blender veya Unity'yi açmak/sürmek.**
- **Asset yeniden adlandırma.** Prism'in API'sinde asset rename yok (yalnızca episode/sequence/shot). Bu sürümde yok.
- **Proje oluşturmak** ve Prism proje ayarlarını değiştirmek.
- **Yetki/rol sistemi.** Prism'de yok; sunucu da eklemez (bkz. §6).
- **Claude Desktop ve diğer istemciler.** Kurulum yalnızca Claude Code'a kaydeder (CLI ve VS Code eklentisi aynı kaydı kullanır). Protokol standart olduğu için başka istemciler elle eklenebilir; desteklenmez. *(Tasarımcının kararı.)*

## 4. Kesin kurallar (anti-hedefler)

Bunlardan biri bozulursa iş çalışsa bile başarısız sayılır:

1. **Hiçbir pencere açılmaz.** Prism'in `popup`, `popupQuestion`, hata penceresi (`writeErrorLog`), kullanıcı adı ve proje seçme pencereleri dahil. Prism bir şey sormak isterse bu Claude'a hata olarak döner.
2. **Onaysız değişiklik yok.** Var olan veriyi değiştiren veya silen hiçbir işlem, kullanıcı onaylamadan yapılmaz (bkz. §6).
3. **Sonsuz döngü yok.** Prism'in bazı fonksiyonları dosya kilitliyken "Retry/Cancel" sorusunu döngüde sorar (`deleteShot`, `deleteMasterVersion`). `noUI` modunda `popupQuestion` `default` (yani `None`) döndürdüğü için `deleteShot` sonsuza kadar döner. Sunucu bu fonksiyonları ya bu sorunun hata olarak döndüğü bir koruma içinde çağırır ya da kendi uygulamasını kullanır.
4. **Geri dönüşsüz silme yok.** Shot silme klasörleri kalıcı silmez, çöp klasörüne taşır (bkz. §7.3).
5. **Kullanıcının Prism seçimi izinsiz değişmez.** Varsayılan proje değişikliği yalnızca sunucunun oturumunu etkiler (bkz. §5).
6. **stdout yalnızca MCP'ye ait.** Prism açılışta ve çalışırken stdout'a log basabilir. Sunucu, MCP protokolü dışındaki her çıktıyı stderr'e yönlendirir; aksi halde istemci bağlantıyı bozuk sayar.
7. **Unity'ye bağımlılık yok.** Sunucu Unity kurulu olmayan bir makinede de çalışır. Unity köprüsünün Python kodundan (`Unity/Scripts/unity_bridge/`) yalnızca Unity'ye ihtiyaç duymayan parçalar (ör. `headless()`, `BridgeError`) kullanılabilir.

## 5. Aktif proje

- Sunucu açıldığında aktif proje, kullanıcının Prism'deki seçili projesidir (`globals/current project`).
- `set_project` aracı projeyi **yalnızca sunucunun oturumunda** değiştirir: Prism'in `changeProject(configPath)` fonksiyonu `noUI` modunda ayara yazmaz. Kullanıcının kendi açtığı Prism'i ve Unity'nin açtığı Prism'i etkilemez.
- `set_project` ile `persist: true` verilirse Prism'in seçili projesi de değişir (`writeToConfig=True`). Bu, §6'daki onay kuralına tabidir: önce `needs_confirmation` döner (eski ve yeni proje adıyla).
- Proje, son açılan projeler listesinden ada göre ya da `pipeline.json` yoluyla seçilir. Ad birden fazla projeyle eşleşirse `needs_input` döner ve adaylar listelenir.
- Her araç cevabı hangi projede çalıştığını (`project: {name, path}`) içerir, böylece Claude yanlış projede iş yaptığını fark edebilir.

## 6. Onay kuralı

Prism'de yetki sistemi yok. Her ekip üyesi her işlemi yapabilir; ama var olan veriyi **değiştiren veya silen** her işlem iki adımlıdır:

1. Araç `confirm` olmadan çağrılır. Hiçbir şey değişmez. Cevap `needs_confirmation` hatasıdır; `details` içinde:
   - `summary`: insanın okuyacağı tek cümle ("Lotus/lotus_model master'ı v0002'den v0003'e geçecek"),
   - `changes`: neyin değişeceği (eski/yeni değer, etkilenen dosya veya klasör sayısı, silinecek/taşınacak yollar),
   - `confirmToken`: bu önizlemenin ait olduğu durumu temsil eden kısa bir değer.
2. Kullanıcı Claude'a "evet" der; Claude aynı aracı aynı argümanlarla ve `confirm: "<confirmToken>"` ile tekrar çağırır.
   - Token, işlemin dayandığı durumdan (ilgili dosyaların değişiklik zamanları, mevcut master versiyonu vb.) türetilir. Önizlemeden sonra durum değiştiyse (başka biri master'ı değiştirdiyse) token tutmaz ve yeni bir `needs_confirmation` döner.
   - Token tahmin edilemez olmak zorunda değil; amacı Claude'un önizleme görmeden onaylamasını ve eski bir önizlemeyle onaylamasını önlemek.
3. Her aracın açıklamasında şu yazar: "Never confirm on your own. Show the user `details.summary` and `details.changes` and ask; call again with `confirm` only after the user says yes."

**Onaya tabi olanlar:** master yapma, master silme, yorum değiştirme (boş yorumu doldurmak dahil değil), açıklama/metadata/önizlemenin üzerine yazma, var olan frame aralığını değiştirme, yeniden adlandırma, omit ve omit geri alma, shot silme, `persist: true` ile proje değiştirme.

**Onaysız olanlar:** her türlü sorgu; yeni bir şey açmak; boş bir alanı ilk kez doldurmak.

**Zaten var olan bir şeyi açmak** (aynı adlı asset, task vb.) hata değildir: hiçbir şey değişmez, cevap `created: false` ve mevcut öğeyi döndürür.

## 7. Araçlar

Sunucunun MCP adı `prism`. Claude Code'da araçlar `mcp__prism__<ad>` olarak görünür; bu yüzden adlarda `prism_` öneki yoktur. Unity MCP'deki `prism_*` araçlarıyla aynı entity biçimini kullanır:

- Asset: `{"type":"asset","asset_path":"Props/Lotus"}`
- Shot: `{"type":"shot","sequence":"sq01","shot":"sh010"}` (episode kullanan projelerde `episode` da)

Ürün ve versiyon listeleri, Unity tarafındaki `prism_list_products` / `prism_list_versions` ile aynı alanları döndürür; yeni alanlar (`isMaster` vb.) eklenebilir.

Hata kodları Unity entegrasyonundakilerle aynıdır (`needs_input`, `needs_confirmation`, `source_unavailable`, `prism_unavailable`, `bad_args`, `timeout`, `internal`); Unity'ye özgü olanlar (`unity_busy`, `missing_package`) kullanılmaz.

### 7.1 Oturum ve proje

| Araç | Ne yapar |
|---|---|
| `status` | Prism sürümü, Prism kullanıcısı (ad, kısaltma), aktif proje, sunucu sürümü. Prism kullanıcı adı yoksa `needs_input`. |
| `list_projects` | Son açılan projeler: ad, `pipeline.json` yolu, erişilebilir mi (ağ sürücüsü çevrimdışı olabilir). |
| `set_project` | `name` veya `configPath`, opsiyonel `persist`. Bkz. §5. |

### 7.2 Sorgular (hiçbir şey yazmaz)

| Araç | Ne yapar |
|---|---|
| `list_entities` | Asset'ler (kategori yoluyla) veya sequence/shot'lar. Filtre: `type`, `path` ön eki / ad içerir, `includeOmitted`. |
| `get_entity` | Bir entity'nin açıklaması, metadata'sı, önizleme resminin yolu, (shot ise) frame aralığı, department'ları ve task'ları. |
| `list_scenefiles` | Bir entity'nin (opsiyonel department/task) sahne dosyaları: versiyon, yorum, kullanıcı, tarih, uygulama (uzantıdan), yol. |
| `list_products` | Bir entity'nin ürünleri. |
| `list_versions` | Bir ürünün versiyonları: versiyon, yorum, kullanıcı, tarih, dosya, konum, `isMaster`. |
| `list_media` | Bir entity'nin playblast ve render'ları ve versiyonları. |
| `get_dependencies` | Bir sahne dosyasının kullandığı ürünler (Prism'in kaydettiği kadarıyla). |
| `report` | Hazır raporlar, `kind` ile: |
|  | `recent_activity` — verilen tarihten (`since`, varsayılan 7 gün) beri kaydedilen sahne versiyonları, ürün versiyonları ve medya, kullanıcıya göre. |
|  | `missing_products` — belirli bir ürünü (ad kalıbıyla, ör. `*_model`) ya da herhangi bir ürünü olmayan asset'ler; opsiyonel kategori filtresi. |
|  | `master_behind` — master'ı en son versiyonda olmayan, ya da master'ı hiç olmayan ürünler. |
|  | `empty_tasks` — sahne dosyası olmayan task'lar (açılmış ama başlanmamış işler). |

Büyük projelerde sorgular tüm projeyi tarayabilir. Her liste aracı `limit` (varsayılan 200) alır ve kesildiyse `truncated: true` döner.

### 7.3 Proje düzeni (yeni şey açar)

| Araç | Ne yapar |
|---|---|
| `create_entity` | Asset (ara klasörler/kategoriler dahil) veya sequence/shot açar. Opsiyonel: `description`, shot için `frameRange`, `taskPreset`. |
| `create_department` | Bir entity'de department açar; Prism'in o department için varsayılan task'larını da açar (`getDefaultTasksForDepartment`), `defaultTasks: false` verilmedikçe. |
| `create_task` | Bir department'ta task açar; department yoksa `needs_confirmation` değil `needs_input` döner (`missing: ["department"]`) — Claude department'ı da açmayı önerir. |
| `apply_task_preset` | Prism'in task preset'ini bir entity'ye uygular (`createTasksFromPreset`). Opsiyonel `dryRun` hangi department/task'ların açılacağını listeler. |
| `list_task_presets` | Projede tanımlı task preset'leri. |
| `set_description`, `set_metadata`, `set_preview` | Boş alanı doldurur; doluysa §6'daki onaya tabidir. `set_preview` yerel bir resim dosyası yolu alır. |
| `set_shot_range` | Shot frame aralığı; aralık zaten varsa onaya tabidir. |

### 7.4 Versiyon yönetimi (hepsi onaya tabi)

| Araç | Ne yapar |
|---|---|
| `set_master` | Bir ürün versiyonunu master yapar (`updateMasterVersion`). Medya için de (`mediaProducts.updateMasterVersion`). |
| `delete_master` | Ürünün master versiyonunu siler. Master, bir versiyonun kopyasıdır; versiyonun kendisi kalır. |
| `set_comment` | Ürün versiyonu, medya versiyonu veya sahne dosyası yorumunu değiştirir. |
| `rename` | Episode, sequence veya shot'ı yeniden adlandırır (`renameEpisode/Sequence/Shot`). Asset yok (§3). Prism dosyaları tek tek yeniden adlandırır; paylaşılan sürücüde açık bir dosya işi yarıda bırakabilir. Bu yüzden sunucu başlamadan önce etkilenecek bütün klasör ve dosyaların kilitli olup olmadığına bakar; biri kilitliyse hiçbir şeye dokunmadan hangi dosyanın kilitli olduğunu söyleyen bir hata döner. Kontrolden sonra yine de yarıda kalırsa, hata neyin yeniden adlandırıldığını ve neyin kaldığını listeler. Tam geri alma (her şeyi eski haline döndürme) bu sürümde yok. *(Tasarımcının kararı.)* |
| `omit` / `unomit` | Entity'yi Prism'de gizler / geri getirir (`omitEntity`). Dosyalara dokunmaz. |
| `delete_shot` | Shot'ın klasörlerini (global ve varsa local) projenin içindeki çöp klasörüne taşır: `<proje>/00_Pipeline/Trash/<YYYYMMDD-HHMMSS>_<sequence>-<shot>/`. Kalıcı silmez. Taşıma bir dosya kilidi yüzünden yarıda kalırsa taşınanları geri koyar ve kilitli dosyayı söyleyen bir hata döner. *(Çöp klasörünün yeri tasarımcının kararı.)* |

**Shot'a bağlı olanlar (`rename` ve `delete_shot`):** Onay önizlemesinin `changes` alanı, yeniden adlandırılacak veya silinecek shot'ın ürünlerini kullanan sahne dosyalarını listeler (`dependents`: entity, sahne dosyası, versiyon, kullanıcı). Liste, projedeki sahne dosyalarının Prism'e kaydettiği bağımlılık bilgisinden çıkarılır (`get_dependencies` ile aynı kaynak). İşlem engellenmez: kullanıcı listeyi görür ve yine de onaylayabilir. `summary`, bağlantıların kopacağını açıkça söyler ("3 sahne bu shot'ın ürünlerini kullanıyor; onlarda bağlantı kopacak"). Unity projelerindeki import kayıtları Prism'de olmadığı için listelenemez; `changes` bunu bir not olarak her zaman söyler ("Unity'deki import'lar bu listede yok; Unity'de 'Check for updates' bunları Prism'den kaldırılmış olarak gösterecek"). Unity kayıtlarını düzeltmek kapsam dışıdır (§4.7).

Geri alma: shot'ı çöpten geri koymak bu sürümde ayrı bir araç değildir; `changes` ve hata mesajları çöp yolunu söyler, kullanıcı klasörü geri taşıyabilir.

## 8. Kurulum

Repo kökünde iki dosya: `Install.bat` ve `Uninstall.bat`. İkisi de `powershell -ExecutionPolicy Bypass -File tools\install.ps1 [-Remove]` çalıştırır, böylece PowerShell betik politikasına takılmaz.

`Install.bat`:

1. **Prism'i bulur.** `-PrismRoot` argümanı → `PRISM_ROOT` ortam değişkeni → `C:\Program Files\Prism2`. Bulamazsa konsolda yolu bir kez sorar. (Bir insanın çalıştırdığı bir konsol; Claude çalıştırırsa `-PrismRoot` ile verir ve hiçbir şey sorulmaz.)
2. **Unity eklentisini Prism'e kaydeder.** Bugünkü `tools\deploy_dev.ps1` ile aynı iş (`PluginPaths.json`, yedek dahil). `deploy_dev.ps1` geliştiriciler için kalır ve aynı kodu kullanır.
3. **Prism MCP'yi Claude Code'a ekler**, kullanıcı düzeyinde: `claude mcp add --scope user prism -e PRISM_ROOT=<yol> -- "<PrismRoot>\Python313\python.exe" "<repo>\PrismMcp\server.py"`. Önceden bir `prism` kaydı varsa önce kaldırır (tekrar çalıştırma güvenli). `claude` komutu yoksa bu adımı atlar ve Claude Code'un kurulmasını söyler.
4. **Kontrol eder.** `python server.py --check` çalıştırır: Prism'i pencere açmadan yükler, kullanıcı adını ve son projeleri okur. Sonunda tek satır özet ("Kurulum tamam: kullanıcı X, 3 proje") ya da neyin eksik olduğunu yazar (ör. "Prism kullanıcı adı yok: Prism'i bir kez açıp adını gir").
5. Pencere kapanmadan önce "bir tuşa bas" bekler (çift tıklanınca sonuç okunabilsin); `-NoPause` ile beklemez.

`Uninstall.bat` 2. ve 3. adımları geri alır.

Git'ten güncelleme çekildikten sonra kurulumu tekrar çalıştırmak gerekmez (sunucu repodan çalışır); yalnızca Claude Code oturumunu yeniden başlatmak yeterlidir. README bunu söyler.

## 9. Çalışma şekli

- **Yer:** repoda `PrismMcp/`. Giriş noktası `PrismMcp/server.py`.
- **Prism sürümü:** Ekipte herkes aynı Prism sürümünü kullanır: **2.1.2.1**. Sunucu yalnızca bu sürüme göre yazılır ve test edilir; uyumluluk katmanı yoktur. `Install.bat` ve `server.py --check` Prism sürümünü okur; farklıysa kurulumu durdurmaz ama açık bir uyarı verir ("Bu makinede Prism X var, ekip sürümü 2.1.2.1"). `status` aracı da sürüm farklıysa uyarı alanı döndürür. Ekip sürümü tek bir sabitte durur, Prism yükseltildiğinde orası ve testler güncellenir. *(Uyarı davranışı tasarımcının kararı.)*
- **Python:** Prism'in kendi Python'u (`<PrismRoot>\Python313\python.exe`). Dışarıdan paket kurulmaz; MCP protokolü (JSON-RPC 2.0, satır satır stdio; `initialize`, `notifications/initialized`, `tools/list`, `tools/call`, `ping`) standart kütüphaneyle yazılır.
- **Prism çekirdeği:** ilk araç çağrısında tembel yüklenir (açılış birkaç saniye sürebilir; `initialize` ve `tools/list` beklemez). Prism bir Qt uygulaması ister: `QApplication` oluşturulur, `QT_QPA_PLATFORM=offscreen` ile ekran kullanılmaz. `PrismCore.create(app="Standalone", prismArgs=["noUI", "silent"])`.
- **Pencere koruması:** her araç çağrısı, Unity köprüsündeki `headless(core)` ile aynı davranışta bir koruma içinde çalışır: `popupQuestion` → `needs_input`, `popup` → `internal`, hata penceresi → hata, kullanıcı/proje seçme pencereleri → `needs_input`.
- **Eşzamanlılık:** her Claude oturumu kendi sunucu sürecini açar. Aynı anda birden fazla süreç (başka kullanıcılar, Unity'nin açtığı Prism, kullanıcının kendi Prism'i) aynı projede çalışabilir; Prism zaten dosya tabanlıdır. Sunucu açmadan önce var olup olmadığına bakar (§6) ve onaylı işlemlerde token ile eski önizlemeyi reddeder; bunun ötesinde kilit tutmaz.
- **Kayıt:** sunucu, yaptığı her değiştirici işlemi (kullanıcı, zaman, araç, argümanlar, sonuç) kullanıcının makinesinde bir log dosyasına yazar: `%USERPROFILE%\Documents\Prism2\PrismMcp.log`. *(Tasarımcının kararı.)*

## 10. Test

- **Birim testleri** (sahte Prism çekirdeği): onay kuralı ve token, `created: false`, proje değiştirme (`persist` olan/olmayan), entity biçimi dönüşümü, rapor mantığı, stdout'un temiz kalması, `deleteShot` korumasının sonsuz döngüye girmemesi.
- **Entegrasyon testleri** (gerçek Prism, `tools/make_test_prism_project.py` ile kurulan test projesi; proje gerekiyorsa genişletilir): her aracın gerçek Prism'e karşı bir mutlu yol testi; değiştirici araçlarda önce `needs_confirmation`, sonra onayla uygulanması; shot silmenin çöpe taşıması; kullanıcının `current project` ayarının testlerden sonra değişmemiş olması.
- **Protokol testi:** sunucuyu Prism'in Python'uyla alt süreç olarak başlatır, `initialize` → `tools/list` → `tools/call status` akışını stdio üzerinden yapar ve stdout'ta JSON-RPC dışında bir satır olmadığını doğrular.
- **Kurulum testi:** `tools\install.ps1`'i geçici bir `USERPROFILE` ve sahte bir `claude` komutuyla çalıştırır; iki kez çalıştırmanın aynı sonucu verdiğini ve `-Remove`'un her şeyi geri aldığını doğrular.
- Testler mevcut `tools\run_py_tests.ps1` ile çalışır.

## 11. Belgeler

- README'ye "Prism MCP" bölümü: ne işe yarar, `Install.bat`, kullanım örnekleri ("Lotus'a Modeling departmanı aç", "bu hafta kim ne publish etti").
- `PrismMcp/TOOLS.md`: Unity tarafındaki `CLAUDE_TOOLS.md` gibi, her araç, argümanları, dönüşü ve onay kuralı.

## 12. Uygulayıcıya bırakılanlar

- Modül yapısı, araç argümanlarının JSON şemalarının ayrıntısı.
- `confirmToken`'ın nasıl türetildiği (§6'daki amaçları sağladığı sürece).
- `headless()` ve `BridgeError`'ı Unity köprüsünden import etmek mi, `PrismMcp/` içine taşıyıp iki tarafın da oradan kullanması mı (§4.7'ye uyduğu sürece).
- Rapor sorgularının nasıl hızlandırılacağı.
