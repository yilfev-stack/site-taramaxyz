# Web Sitesi Tarama ve İçerik Toplama Aracı

Herhangi bir web sitesini tarayarak görselleri, videoları ve metinleri toplayan araç.

## Özellikler

- ✅ Herhangi bir web sitesi URL'si girme
- ✅ Görselleri listeleme ve indirme
- ✅ Videoları listeleme
- ✅ Metinleri toplama ve kopyalama
- ✅ Kırık link tespiti
- ✅ ZIP olarak toplu indirme

## Bilinen Kısıtlamalar

⚠️ **JavaScript ile render edilen siteler** (React, Vue, Angular vb.) için:
- Bu araç HTML kaynak kodunu tarar
- JS ile yüklenen içerikler görünmeyebilir
- Playwright/Puppeteer entegrasyonu gerekir (gelişmiş versiyon)

## Local PC'de Çalıştırma (Docker ile)

### Gereksinimler
- Docker
- Docker Compose

### Kurulum

```bash
# Projeyi indirin
git clone <repo-url>
cd <proje-klasoru>

# Docker ile başlatın
docker-compose up -d

# Tarayıcıda açın
http://localhost:3006
```

### Portlar
- Frontend: `3006`
- Backend API: `8001`
- MongoDB: `27017`

## Kullanım

1. Web sitesi URL'sini girin (orn: `www.example.com`)
2. Max sayfa sayısını ayarlayın
3. "Taramayı Başlat" butonuna tıklayın
4. Görseller, videolar, metinler sekmelerinden içerikleri görün
5. İstediğiniz öğeleri seçip indirin

## API Endpoints

- `POST /api/crawl/start` - Taramayı başlat
- `GET /api/crawl/status` - Tarama durumu
- `GET /api/report/images` - Görseller
- `GET /api/report/videos` - Videolar
- `GET /api/report/texts` - Metinler
- `POST /api/download/start` - İndirme başlat

## Teknik Detaylar

- **Backend:** Python FastAPI
- **Frontend:** React
- **Veritabanı:** MongoDB
- **Tarayıcı:** aiohttp + BeautifulSoup
