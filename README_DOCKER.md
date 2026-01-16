# Web Sitesi Tarama ve İndirme Aracı - Docker Kurulumu

## Gereksinimler
- Docker
- Docker Compose

## Kurulum

```bash
# Projeyi indirin ve klasöre girin
cd site-tarama-main

# Docker ile başlatın
docker-compose up -d --build

# Tarayıcıda açın
http://localhost:3006
```

## Portlar
- **3006** - Frontend (Web Arayüzü)
- **8001** - Backend API
- **27017** - MongoDB

## Özellikler

### 🔍 Web Sitesi Tarama
- Herhangi bir site URL'si girin
- JavaScript render'lı siteleri tarar (Playwright)
- Görselleri, videoları, metinleri toplar

### 📥 İndirme
- Görselleri ZIP olarak indir
- YouTube videoları indir
- VK.com videoları indir
- TikTok, Twitter, Instagram, Facebook...
- 1000+ site desteği (yt-dlp)

### 📹 Video İndirme Kullanımı
1. "▶ YouTube" sekmesine git
2. Video URL yapıştır (YouTube, VK, TikTok vs.)
3. "Kontrol Et" tıkla
4. "Video İndir" veya "MP3 İndir" seç

## Sorun Giderme

### Build hatası alırsam?
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Logları görmek için?
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Durdurmak için?
```bash
docker-compose down
```

## Yasal Uyarı
⚠️ Video indirme özelliği sadece kişisel kullanım içindir.
Ticari kullanım ve dağıtım telif hakkı ihlalidir.
