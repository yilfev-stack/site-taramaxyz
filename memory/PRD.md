# Web Sitesi Tarama ve İndirme Aracı - PRD

## Orijinal Problem Tanımı
Kullanıcı, `www.demart.com.tr` sitesi için kapsamlı bir denetim aracı istedi. Proje kapsamı genişleyerek:
1. Genel amaçlı web tarayıcı ve içerik indirici
2. YouTube, VK.com, TikTok vb. sitelerden video indirme
3. Docker ile yerel PC'de çalışabilir uygulama
4. Doğrudan resim/video indirme özelliği
5. İndirme ilerleme çubuğu ve kuyruk sistemi (Maks 5 eşzamanlı)
6. Yarım kalan indirmeleri devam ettirme

## Hedef Kullanıcılar
- Web içerik analistleri
- Dijital pazarlamacılar
- Kişisel kullanım için medya indirmek isteyenler

## Temel Gereksinimler
### Tamamlanan (19 Ocak 2025)
- [x] Web sitesi tarama (Playwright ile JS destekli)
- [x] Görsel, video, metin toplama
- [x] YouTube/VK.com/TikTok video indirme (yt-dlp)
- [x] Doğrudan URL'den resim/video indirme
- [x] Docker ile yerel kurulum
- [x] İndirme ilerleme çubuğu (Progress Bar) - HER İKİ SEKMEDE
- [x] Kuyruk sistemi (Maks 5 eşzamanlı indirme)
- [x] Yarım kalan indirmeler listesi
- [x] Devam ettirme butonu
- [x] Sayfa yenilenince aktif indirmeler korunması
- [x] VK video URL çıkarma düzeltildi (CDN yerine video sayfası URL'si)
- [x] Videolar sekmesi yeni kart görünümü (thumbnail + butonlar)
- [x] Docker'a Deno eklendi (yt-dlp için daha iyi YouTube desteği)

### Bekleyen (Backlog)
- [ ] AI-destekli görsel analizi (sadece platform versiyonunda)
- [ ] Çoklu dil desteği (İngilizce/Türkçe)
- [ ] İndirme geçmişi ve kayıt tutma
- [ ] Toplu URL indirme (liste ile)

## Teknik Mimari
```
/app/
├── backend/
│   ├── server.py              # FastAPI API endpoints + Download Queue Manager
│   ├── advanced_crawler.py    # Playwright crawler + yt-dlp downloader
│   ├── download_state.json    # İndirme durumu kalıcı depolama
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/App.js             # React UI (Progress bar, Queue status)
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── README_DOCKER.md
```

## Önemli API Endpoints
- `POST /api/crawl/start` - Site tarama başlat
- `GET /api/crawl/status` - Tarama durumu
- `POST /api/download/video` - Video indir (sıra sistemi ile)
- `GET /api/download/queue-status` - İndirme kuyruğu durumu (progress + incomplete)
- `POST /api/download/resume/{id}` - Yarım kalan indirmeyi devam ettir
- `DELETE /api/download/incomplete/{id}` - Yarım kalan indirmeyi sil
- `POST /api/download/direct-image` - Doğrudan resim indir

## Son Güncelleme: 19 Ocak 2025
- İndirme ilerleme çubuğu eklendi
- Maks 5 eşzamanlı indirme sınırı eklendi
- Kuyruk sistemi: Fazla indirmeler sıraya alınır
- Yarım kalan indirmeler listesi ve devam ettirme butonu
- Sayfa yenilenince aktif indirmeler korunuyor (download_state.json)
- YouTube ayarları eski haline döndürüldü (kullanıcı talebi)

