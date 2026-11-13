# Trello ↔ Discord ↔ Prism senkronu

Prototip ekibinin Trello panolarını, Discord sunucusunu ve Prism projesini birbirine bağlayan tek bir betik.
Sunucu gerekmez: Windows Görev Zamanlayıcı onu 2 dakikada bir, pencere açmadan çalıştırır.

## Ne yapar

| Olay | Sonuç |
|---|---|
| Trello'da kart açma, taşıma, yorum, atama, kontrol listesi, ek | Panonun Discord kanalına mesaj (#3d-trello, #pipeline-trello). Aynı karttaki işaretlemeler tek mesajda toplanır. |
| Discord #kart-aç'a `Lotus Prop` | Şablondan Trello kartı açılır, etiket takılır, link cevap olarak yazılır |
| Discord #kart-aç'a `bağla <trello kullanıcı adı>` | Discord kişisi Trello hesabıyla eşleşir |
| 3D panosunda adı kurala uyan ve tek tür etiketi olan kart | Prism'de `Kategori/Ad` asset'i açılır, kartın açıklamasındaki "Prism asset:" satırı `Props/Lotus ✅` olur. Ad kurala uymuyorsa ya da iki tür etiketi varsa karta bir kez uyarı yorumu düşer. Etiket yoksa beklenir. |
| Prism'de açılmış bir kartın adı değişirse | Karta bir kez uyarı: Prism asset adlarını değiştiremez |
| Prism'de model publish | #wip'e mesaj |
| Prism'de playblast | #review forumunda asset'in başlığına video (başlık yoksa açılır), Trello kartı Review'a geçer |
| Hafta içi her sabah 09:30'dan sonra | #genel'e günlük özet |

**Bildirimler:** Bütün mesajlar sessiz (@silent) gider. Sadece işin sahibi etiketlenir:

- kart ona atanınca;
- kartına başkası yorum yazınca;
- kartını başkası taşıyınca;
- asset'ine başkası playblast atınca.

Etiketlenebilmesi için kişinin `bağla` ile eşleşmiş olması gerekir.

## Kurulum

1. Bu klasördeki `trello_discord.py` ve `prism_create.py` dosyalarını `%USERPROFILE%\.trello_discord\` içine kopyala.
2. `config.example.json` dosyasını aynı yere `config.json` adıyla kopyala ve doldur:
   - `trelloKey` / `trelloToken`: trello.com/power-ups/admin → API anahtarı ve Token
   - `boards`: Trello pano kısa linki → o panonun Discord kanal webhook'u
   - `summary.webhook`: günlük özetin gideceği kanalın webhook'u
   - `prism.project`: prototip Prism projesinin yolu (örn. `P:/Prototip`). Boş bırakılırsa Prism'le ilgili her şey kapalı kalır.
   - `prism.mcp`: bu reponun `PrismMcp` klasörü. Asset'ler Prism MCP'nin kendi araçlarıyla (`prism_create.py` üzerinden, pencere açmadan) oluşturulur.
   - `prism.categories`: Trello tür etiketi → Prism kategorisi. `prism.taskPreset`: yeni asset'e uygulanacak Prism task preset'i (boşsa yok).
   - `prism_create.py` dosyasını da `trello_discord.py`'nin yanına kopyala.
   - `cards.botToken`: Discord bot token'ı. Botta **Message Content Intent** açık olmalı.
3. Dosyayı sadece kendi kullanıcın okuyabilsin: `icacls config.json /inheritance:r /grant:r "%USERNAME%:F"`
4. Deneme: `python trello_discord.py --dry-run` (hiçbir şey göndermez, ne göndereceğini yazar)
5. Zamanlanmış görevi kur (PowerShell):

```powershell
$a = New-ScheduledTaskAction -Execute "C:\Program Files\Prism2\Python313\pythonw.exe" -Argument "-I `"$env:USERPROFILE\.trello_discord\trello_discord.py`"" -WorkingDirectory "$env:USERPROFILE\.trello_discord"
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2)
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "Trello Discord Sync" -Action $a -Trigger $t -Settings $s
```

İlk çalıştırma hiçbir şey göndermez, sadece kaldığı yeri `state.json` dosyasına yazar. Eski geçmiş Discord'a dökülmez.

**Başka makineye taşırken** `state.json` dosyasını da kopyala. Eski makinedeki görevi sil, yoksa mesajlar iki kere gelir.

## Komutlar

```
python trello_discord.py            yeni hareketleri gönder (görevin yaptığı)
python trello_discord.py --dry-run  ne gönderileceğini yaz, hiçbir şey değiştirme
python trello_discord.py --summary  günlük özeti şimdi gönder
python trello_discord.py --hello    her kanala "bağlandı" mesajı at
```

## Sorun olursa

- Hatalar `%USERPROFILE%\.trello_discord\trello_discord.log` dosyasına yazılır. Dosya yoksa hata yok demektir.
- Görevin son sonucu: `Get-ScheduledTask "Trello Discord Sync" | Get-ScheduledTaskInfo` (LastTaskResult 0 = sorun yok).
- Bir iş hata verirse (örneğin Trello cevap vermiyorsa) diğerleri çalışmaya devam eder, kaçan hareketler bir sonraki çalışmada gelir.
- Discord bot token'ı değişirse yenisini `cards.botToken` alanına yaz. Değişmezse sadece #kart-aç ve elle açılmış review başlıklarının bulunması durur.

Bu klasördeki kopya kaynak koddur. Çalışan kopya `%USERPROFILE%\.trello_discord\` içindedir. Değişiklik yapınca ikisini eşitle.
