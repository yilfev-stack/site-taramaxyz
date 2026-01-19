from fastapi import FastAPI, APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import asyncio
import json
import csv
import io
import aiohttp
import aiofiles
import zipfile
import shutil
from collections import deque
import threading

# Gelişmiş crawler
from advanced_crawler import AdvancedCrawler, YouTubeDownloaderWithProgress, report_to_dict

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'website_scanner')]

# Downloads
DOWNLOADS_DIR = ROOT_DIR / 'downloads'
DOWNLOADS_DIR.mkdir(exist_ok=True)

# App
app = FastAPI(title="Gelişmiş Web Tarama ve İndirme Aracı")
api_router = APIRouter(prefix="/api")

# Global state
crawler_instance: Optional[AdvancedCrawler] = None
current_report: Optional[dict] = None
crawl_progress: Dict[str, Any] = {
    'status': 'idle', 'crawled': 0, 'discovered': 0,
    'images': 0, 'videos': 0, 'issues': 0, 'message': ''
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===== İndirme Sıra Yönetimi (Maks eşzamanlı) =====
# İndirme durumunu dosyaya kaydet
DOWNLOAD_STATE_FILE = ROOT_DIR / 'download_state.json'

class DownloadQueueManager:
    """Video indirme sıra yöneticisi - Maks eşzamanlı indirme, kalıcı durum"""
    
    def __init__(self, max_concurrent: int = 20):
        self.max_concurrent = max_concurrent
        self.active_downloads: Dict[str, Dict] = {}  # download_id -> info
        self.queue: deque = deque()  # Bekleyen indirmeler
        self.lock = asyncio.Lock()
        self.progress_data: Dict[str, Dict] = {}  # download_id -> progress
        self.incomplete_downloads: Dict[str, Dict] = {}  # Yarım kalan indirmeler
        self._load_state()
    
    def _load_state(self):
        """Kayıtlı durumu yükle"""
        try:
            if DOWNLOAD_STATE_FILE.exists():
                with open(DOWNLOAD_STATE_FILE, 'r') as f:
                    data = json.load(f)
                    saved_queue = data.get('queue', [])
                    self.incomplete_downloads = data.get('incomplete', {})
                    # Eski aktif indirmeleri yarım kalan olarak işaretle
                    for did, info in data.get('active', {}).items():
                        if info.get('status') not in ['completed', 'failed']:
                            info['status'] = 'interrupted'
                            self.incomplete_downloads[did] = info
                    # Kuyruktaki indirmeleri geri yükle
                    if saved_queue:
                        self.queue = deque(saved_queue)
                        for idx, item in enumerate(self.queue):
                            item['status'] = 'queued'
                            item['queue_position'] = idx + 1
                            download_id = item.get('download_id')
                            if download_id:
                                self.progress_data[download_id] = {
                                    'percent': item.get('progress', 0),
                                    'status': 'queued',
                                    'queue_position': idx + 1,
                                    'url': item.get('url', ''),
                                    'title': item.get('url', '')
                                }
                    logger.info(f"Loaded {len(self.incomplete_downloads)} incomplete downloads")
        except Exception as e:
            logger.error(f"Error loading download state: {e}")
    
    def _save_state(self):
        """Durumu dosyaya kaydet"""
        try:
            data = {
                'active': {k: v for k, v in self.progress_data.items() if v.get('status') not in ['completed']},
                'queue': list(self.queue),
                'incomplete': self.incomplete_downloads
            }
            with open(DOWNLOAD_STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving download state: {e}")
    
    def get_status(self) -> Dict:
        """Kuyruk durumunu döndür - sayfa yenilenince de görünsün"""
        # Progress data'dan aktif olanları filtrele
        active_progress = {}
        for did, prog in self.progress_data.items():
            if prog.get('status') not in ['completed', 'failed']:
                active_progress[did] = prog
        
        return {
            "active_count": len(self.active_downloads),
            "queue_count": len(self.queue),
            "max_concurrent": self.max_concurrent,
            "active_downloads": list(self.active_downloads.values()),
            "queued_downloads": list(self.queue),
            "progress": active_progress,  # Aktif indirmeler
            "incomplete": self.incomplete_downloads  # Yarım kalan indirmeler
        }
    
    def get_download_progress(self, download_id: str) -> Optional[Dict]:
        """Tek bir indirmenin ilerlemesini döndür"""
        return self.progress_data.get(download_id)
    
    def update_progress(self, download_id: str, progress: Dict):
        """İlerleme bilgisini güncelle - mevcut verileri koru ve kaydet"""
        if download_id in self.progress_data:
            # Mevcut verileri koru, yenilerini üzerine yaz
            current = self.progress_data[download_id]
            current.update(progress)
        else:
            self.progress_data[download_id] = progress
        # Her güncellenmede durumu kaydet
        self._save_state()
    
    async def can_start_download(self) -> bool:
        """Yeni indirme başlatılabilir mi?"""
        async with self.lock:
            return len(self.active_downloads) < self.max_concurrent
    
    async def add_to_queue(self, download_info: Dict) -> str:
        """Sıraya ekle veya hemen başlat"""
        download_id = str(uuid.uuid4())[:8]
        download_info['download_id'] = download_id
        download_info['status'] = 'queued'
        download_info['created_at'] = datetime.now(timezone.utc).isoformat()
        download_info['progress'] = 0
        
        async with self.lock:
            if len(self.active_downloads) < self.max_concurrent:
                download_info['status'] = 'starting'
                self.active_downloads[download_id] = download_info
                self.progress_data[download_id] = {
                    'percent': 0,
                    'speed': '',
                    'eta': '',
                    'downloaded': '',
                    'total': '',
                    'status': 'starting',
                    'url': download_info.get('url', ''),
                    'title': download_info.get('url', '')  # Başlangıçta URL, sonra title ile güncellenir
                }
            else:
                download_info['status'] = 'queued'
                download_info['queue_position'] = len(self.queue) + 1
                self.queue.append(download_info)
                self.progress_data[download_id] = {
                    'percent': 0,
                    'status': 'queued',
                    'queue_position': len(self.queue),
                    'url': download_info.get('url', ''),
                    'title': download_info.get('url', '')
                }
        self._save_state()
        return download_id
    
    async def start_download(self, download_id: str):
        """İndirmeyi başlat olarak işaretle"""
        async with self.lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id]['status'] = 'downloading'
                if download_id in self.progress_data:
                    self.progress_data[download_id]['status'] = 'downloading'

    async def prime_queue(self) -> List[Dict]:
        """Kuyruktan boş slotları doldur"""
        started = []
        async with self.lock:
            while self.queue and len(self.active_downloads) < self.max_concurrent:
                next_download = self.queue.popleft()
                next_id = next_download['download_id']
                next_download['status'] = 'starting'
                self.active_downloads[next_id] = next_download
                self.progress_data[next_id] = {
                    'percent': 0,
                    'status': 'starting',
                    'url': next_download.get('url', ''),
                    'title': next_download.get('url', '')
                }
                started.append(next_download)

            for i, item in enumerate(self.queue):
                item['queue_position'] = i + 1
                if item.get('download_id') in self.progress_data:
                    self.progress_data[item['download_id']]['queue_position'] = i + 1

        self._save_state()
        return started
    
    async def complete_download(self, download_id: str, success: bool = True, result: Dict = None):
        """İndirmeyi tamamla ve sıradaki başlat"""
        async with self.lock:
            download_info = self.active_downloads.get(download_id, {})
            
            if download_id in self.active_downloads:
                del self.active_downloads[download_id]
            
            # Sonucu kaydet
            if download_id in self.progress_data:
                prog = self.progress_data[download_id]
                prog['status'] = 'completed' if success else 'failed'
                prog['percent'] = 100 if success else prog.get('percent', 0)
                if result:
                    prog['result'] = result
                
                # Başarısız ve ilerleme varsa yarım kalan olarak kaydet
                if not success and prog.get('percent', 0) > 0:
                    self.incomplete_downloads[download_id] = {
                        'url': prog.get('url', download_info.get('url', '')),
                        'title': prog.get('title', ''),
                        'percent': prog.get('percent', 0),
                        'format': download_info.get('format', 'video'),
                        'status': 'interrupted',
                        'created_at': download_info.get('created_at', datetime.now(timezone.utc).isoformat())
                    }
            
            # Durumu kaydet
            self._save_state()
            
            # Sıradaki indirmeyi başlat
            if self.queue and len(self.active_downloads) < self.max_concurrent:
                next_download = self.queue.popleft()
                next_id = next_download['download_id']
                next_download['status'] = 'starting'
                self.active_downloads[next_id] = next_download
                self.progress_data[next_id] = {
                    'percent': 0,
                    'status': 'starting',
                    'url': next_download.get('url', ''),
                    'title': next_download.get('url', '')
                }
                # Sıra pozisyonlarını güncelle
                for i, item in enumerate(self.queue):
                    item['queue_position'] = i + 1
                    self.progress_data[item['download_id']]['queue_position'] = i + 1
                self._save_state()
                return next_download
        return None
    
    def clear_completed(self):
        """Tamamlanan indirmelerin progress datasını temizle"""
        to_remove = []
        for did, prog in self.progress_data.items():
            if prog.get('status') in ['completed', 'failed']:
                to_remove.append(did)
        for did in to_remove:
            del self.progress_data[did]
        self._save_state()
    
    def clear_incomplete(self, download_id: str = None):
        """Yarım kalan indirmeyi temizle"""
        if download_id:
            if download_id in self.incomplete_downloads:
                del self.incomplete_downloads[download_id]
        else:
            self.incomplete_downloads.clear()
        self._save_state()
    
    async def resume_download(self, download_id: str) -> Optional[str]:
        """Yarım kalan indirmeyi devam ettir"""
        if download_id not in self.incomplete_downloads:
            return None
        
        incomplete = self.incomplete_downloads[download_id]
        # Yeni indirme olarak ekle
        download_info = {
            'url': incomplete.get('url'),
            'format': incomplete.get('format', 'video'),
            'type': 'resume'
        }
        new_id = await self.add_to_queue(download_info)
        
        # Eski incomplete'den sil
        del self.incomplete_downloads[download_id]
        self._save_state()
        
        return new_id


# Global download queue manager
download_queue = DownloadQueueManager(max_concurrent=int(os.environ.get("DOWNLOAD_MAX_CONCURRENT", "20")))


# Models
class CrawlStartRequest(BaseModel):
    target_url: str
    max_pages: int = 50


class DownloadRequest(BaseModel):
    urls: List[str]
    download_type: str = "images"


class YouTubeDownloadRequest(BaseModel):
    url: str
    format: str = "video"  # video or audio


class DirectVideoDownloadRequest(BaseModel):
    url: str
    format: str = "video"  # video or audio
    site: str = "auto"  # auto, youtube, vk, tiktok, etc.


# ===== Download Queue Status Endpoint =====
@api_router.get("/download/queue-status")
async def get_download_queue_status():
    """İndirme kuyruğu durumunu getir"""
    return download_queue.get_status()


@api_router.get("/download/progress/{download_id}")
async def get_download_progress(download_id: str):
    """Tek bir indirmenin ilerlemesini getir"""
    progress = download_queue.get_download_progress(download_id)
    if progress:
        return {"success": True, "progress": progress}
    return {"success": False, "message": "İndirme bulunamadı"}


@api_router.post("/download/clear-completed")
async def clear_completed_downloads():
    """Tamamlanan indirmeleri temizle"""
    download_queue.clear_completed()
    return {"success": True}


@api_router.post("/download/resume/{download_id}")
async def resume_incomplete_download(download_id: str, background_tasks: BackgroundTasks):
    """Yarım kalan indirmeyi devam ettir"""
    new_id = await download_queue.resume_download(download_id)
    if new_id:
        # Arka planda indirmeyi başlat
        incomplete = download_queue.incomplete_downloads.get(download_id, {})
        url = incomplete.get('url', '')
        format_type = incomplete.get('format', 'video')
        
        if download_queue.progress_data.get(new_id, {}).get('status') == 'starting':
            background_tasks.add_task(process_youtube_download, new_id, url, format_type)
        
        return {
            "success": True,
            "download_id": new_id,
            "message": "İndirme devam ettiriliyor"
        }
    return {"success": False, "message": "Yarım kalan indirme bulunamadı"}


@api_router.delete("/download/incomplete/{download_id}")
async def delete_incomplete_download(download_id: str):
    """Yarım kalan indirmeyi sil"""
    download_queue.clear_incomplete(download_id)
    return {"success": True}


@api_router.delete("/download/incomplete")
async def clear_all_incomplete_downloads():
    """Tüm yarım kalan indirmeleri temizle"""
    download_queue.clear_incomplete()
    return {"success": True}


@api_router.post("/download/direct-image")
async def download_direct_image(url: str):
    """Tek bir görseli direkt indir"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60), ssl=False) as resp:
                if resp.status == 200:
                    # Dosya adı
                    filename = url.split('/')[-1].split('?')[0]
                    if not filename or '.' not in filename:
                        content_type = resp.headers.get('content-type', '')
                        ext = '.jpg'
                        if 'png' in content_type:
                            ext = '.png'
                        elif 'gif' in content_type:
                            ext = '.gif'
                        elif 'webp' in content_type:
                            ext = '.webp'
                        filename = f"image_{uuid.uuid4().hex[:8]}{ext}"
                    
                    filepath = DOWNLOADS_DIR / filename
                    content = await resp.read()
                    
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(content)
                    
                    return {
                        "success": True,
                        "filename": filename,
                        "size_kb": len(content) / 1024,
                        "download_url": f"/api/download/file-direct/{filename}"
                    }
                else:
                    return {"success": False, "message": f"HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@api_router.get("/download/file-direct/{filename}")
async def get_direct_file(filename: str):
    """İndirilen dosyayı getir"""
    filepath = DOWNLOADS_DIR / filename
    if filepath.exists():
        return FileResponse(str(filepath), filename=filename)
    return {"error": "Dosya bulunamadı"}


# WebSocket
class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, msg: dict):
        for conn in self.connections:
            try:
                await conn.send_json(msg)
            except Exception:
                pass

manager = ConnectionManager()


async def progress_callback(progress: dict):
    global crawl_progress
    crawl_progress.update(progress)
    crawl_progress['status'] = 'running'
    crawl_progress['message'] = f"Taranıyor... {progress['crawled']} sayfa, {progress.get('images', 0)} görsel"
    await manager.broadcast(crawl_progress)


async def run_crawl_task():
    global crawler_instance, current_report, crawl_progress
    
    try:
        crawl_progress['status'] = 'running'
        crawl_progress['message'] = 'Playwright başlatılıyor...'
        await manager.broadcast(crawl_progress)
        
        report = await crawler_instance.run_crawl(progress_callback)
        current_report = report_to_dict(report)
        
        # MongoDB'ye kaydet
        report_doc = current_report.copy()
        report_doc['_id'] = str(uuid.uuid4())
        report_doc['created_at'] = datetime.now(timezone.utc).isoformat()
        await db.reports.insert_one(report_doc)
        
        total_images = len(current_report.get('images', []))
        total_videos = len(current_report.get('videos', [])) + len(current_report.get('youtube_videos', []))
        
        crawl_progress['status'] = 'completed'
        crawl_progress['message'] = f"Tamamlandı! {current_report['total_urls']} sayfa, {total_images} görsel, {total_videos} video"
        await manager.broadcast(crawl_progress)
        
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        crawl_progress['status'] = 'error'
        crawl_progress['message'] = f"Hata: {str(e)}"
        await manager.broadcast(crawl_progress)


# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "Gelişmiş Web Tarama Aracı - Playwright + yt-dlp"}


@api_router.post("/crawl/start")
async def start_crawl(request: CrawlStartRequest, background_tasks: BackgroundTasks):
    global crawler_instance, crawl_progress
    
    if crawler_instance and crawler_instance.is_running:
        return {"success": False, "message": "Tarama devam ediyor"}
    
    url = request.target_url
    if not url.startswith("http"):
        url = "https://" + url
    
    crawler_instance = AdvancedCrawler(
        target_url=url,
        max_pages=request.max_pages,
        download_dir=str(DOWNLOADS_DIR)
    )
    
    crawl_progress = {
        'status': 'starting', 'crawled': 0, 'discovered': 0,
        'images': 0, 'videos': 0, 'issues': 0, 'message': 'Başlatılıyor...'
    }
    
    background_tasks.add_task(run_crawl_task)
    return {"success": True, "message": "Tarama başlatıldı"}


@api_router.post("/crawl/stop")
async def stop_crawl():
    global crawler_instance, crawl_progress
    if crawler_instance:
        crawler_instance.stop_crawl()
        crawl_progress['status'] = 'stopped'
        crawl_progress['message'] = 'Durduruldu'
        return {"success": True}
    return {"success": False, "message": "Aktif tarama yok"}


@api_router.get("/crawl/status")
async def get_status():
    return crawl_progress


@api_router.get("/report/summary")
async def get_summary():
    global current_report
    if not current_report:
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            latest['id'] = str(latest.pop('_id'))
            current_report = latest
        else:
            return {"error": "Rapor yok"}
    
    return {
        'domain': current_report.get('domain', ''),
        'target_url': current_report.get('target_url', ''),
        'total_urls': current_report.get('total_urls', 0),
        'total_images': len(current_report.get('images', [])),
        'total_videos': len(current_report.get('videos', [])),
        'total_youtube': len(current_report.get('youtube_videos', [])),
        'total_texts': len(current_report.get('texts', [])),
        'issues_count': len(current_report.get('issues', []))
    }


@api_router.get("/report/images")
async def get_images(page: int = 1, limit: int = 100):
    global current_report
    if not current_report:
        return {"images": [], "total": 0}
    
    images = current_report.get('images', [])
    start = (page - 1) * limit
    return {"images": images[start:start+limit], "total": len(images)}


@api_router.get("/report/videos")
async def get_videos():
    global current_report
    if not current_report:
        return {"videos": [], "youtube": [], "total": 0}
    
    return {
        "videos": current_report.get('videos', []),
        "youtube": current_report.get('youtube_videos', []),
        "total": len(current_report.get('videos', [])) + len(current_report.get('youtube_videos', []))
    }


@api_router.get("/report/texts")
async def get_texts(limit: int = 100):
    global current_report
    if not current_report:
        return {"texts": [], "total": 0}
    
    texts = current_report.get('texts', [])
    return {"texts": texts[:limit], "total": len(texts)}


@api_router.get("/report/issues")
async def get_issues():
    global current_report
    if not current_report:
        return {"issues": [], "total": 0}
    
    return {"issues": current_report.get('issues', []), "total": len(current_report.get('issues', []))}


@api_router.post("/download/images")
async def download_images(request: DownloadRequest):
    """Görselleri ZIP olarak indir"""
    download_id = str(uuid.uuid4())[:8]
    download_dir = DOWNLOADS_DIR / download_id
    download_dir.mkdir(exist_ok=True)
    
    downloaded = []
    errors = []
    
    async with aiohttp.ClientSession() as session:
        for url in request.urls:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30), ssl=False) as resp:
                    if resp.status == 200:
                        filename = url.split('/')[-1].split('?')[0] or f"image_{len(downloaded)}.jpg"
                        filepath = download_dir / filename
                        
                        # Duplicate önle
                        counter = 1
                        while filepath.exists():
                            name, ext = os.path.splitext(filename)
                            filepath = download_dir / f"{name}_{counter}{ext}"
                            counter += 1
                        
                        content = await resp.read()
                        async with aiofiles.open(filepath, 'wb') as f:
                            await f.write(content)
                        downloaded.append(filepath.name)
            except Exception as e:
                errors.append({"url": url, "error": str(e)})
    
    if downloaded:
        zip_path = DOWNLOADS_DIR / f"{download_id}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in downloaded:
                zf.write(download_dir / file, file)
        shutil.rmtree(download_dir)
        
        return {
            "success": True,
            "download_id": download_id,
            "files_count": len(downloaded),
            "download_url": f"/api/download/file/{download_id}"
        }
    
    return {"success": False, "message": "İndirilemedi", "errors": errors}


@api_router.post("/download/youtube")
async def download_youtube(request: YouTubeDownloadRequest, background_tasks: BackgroundTasks):
    """YouTube video/ses indir - Sıra sistemi ile"""
    # Sıraya ekle
    download_info = {
        'url': request.url,
        'format': request.format,
        'type': 'youtube'
    }
    download_id = await download_queue.add_to_queue(download_info)
    
    # Eğer hemen başlayabiliyorsa background task olarak başlat
    if download_queue.progress_data[download_id]['status'] == 'starting':
        background_tasks.add_task(process_youtube_download, download_id, request.url, request.format)
    else:
        # Sırada bekleyenler için de background task ekle (sırası gelince başlar)
        background_tasks.add_task(wait_and_process_download, download_id, request.url, request.format)
    
    return {
        "success": True,
        "download_id": download_id,
        "status": download_queue.progress_data[download_id]['status'],
        "queue_position": download_queue.progress_data[download_id].get('queue_position', 0),
        "message": "İndirme sıraya eklendi" if download_queue.progress_data[download_id]['status'] == 'queued' else "İndirme başlatıldı"
    }


async def wait_and_process_download(download_id: str, url: str, format_type: str):
    """Sıra bekleyen indirmeler için"""
    # Sıranın gelmesini bekle
    while True:
        progress = download_queue.get_download_progress(download_id)
        if not progress:
            return
        if progress.get('status') in ['starting', 'downloading']:
            break
        if progress.get('status') in ['completed', 'failed']:
            return
        await asyncio.sleep(1)
    
    # İndirmeyi başlat
    await process_youtube_download(download_id, url, format_type)


async def process_youtube_download(download_id: str, url: str, format_type: str):
    """YouTube indirme işlemi - Progress tracking ile"""
    await download_queue.start_download(download_id)
    
    # Başlangıç durumunu ayarla
    download_queue.update_progress(download_id, {
        'percent': 0,
        'status': 'downloading',
        'url': url,
        'title': url,  # Başlangıçta URL, sonra title ile güncellenir
        'speed': '',
        'eta': 'Hazırlanıyor...',
        'downloaded': '',
        'total': ''
    })
    
    # Thread-safe progress update
    def progress_hook(d):
        """yt-dlp progress callback"""
        try:
            if d['status'] == 'downloading':
                percent = 0
                downloaded_bytes = d.get('downloaded_bytes', 0)
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                if total_bytes > 0:
                    percent = (downloaded_bytes / total_bytes) * 100
                elif '_percent_str' in d:
                    try:
                        percent_str = d['_percent_str'].replace('%', '').strip()
                        percent = float(percent_str)
                    except (ValueError, AttributeError):
                        pass
                
                # Speed formatting
                speed = d.get('_speed_str', d.get('speed', ''))
                if isinstance(speed, (int, float)) and speed > 0:
                    if speed > 1024*1024:
                        speed = f"{speed/1024/1024:.1f}MB/s"
                    elif speed > 1024:
                        speed = f"{speed/1024:.1f}KB/s"
                    else:
                        speed = f"{speed:.0f}B/s"
                
                # Downloaded size formatting
                downloaded = d.get('_downloaded_bytes_str', '')
                if not downloaded and downloaded_bytes > 0:
                    if downloaded_bytes > 1024*1024:
                        downloaded = f"{downloaded_bytes/1024/1024:.1f}MB"
                    else:
                        downloaded = f"{downloaded_bytes/1024:.1f}KB"
                
                # Total size formatting
                total = d.get('_total_bytes_str', d.get('_total_bytes_estimate_str', ''))
                if not total and total_bytes > 0:
                    if total_bytes > 1024*1024:
                        total = f"{total_bytes/1024/1024:.1f}MB"
                    else:
                        total = f"{total_bytes/1024:.1f}KB"
                
                download_queue.update_progress(download_id, {
                    'percent': round(percent, 1),
                    'speed': str(speed) if speed else '',
                    'eta': d.get('_eta_str', d.get('eta', '')),
                    'downloaded': downloaded,
                    'total': total,
                    'status': 'downloading',
                    'filename': d.get('filename', '')
                })
                logger.info(f"Download progress {download_id}: {percent:.1f}% - {speed}")
                
            elif d['status'] == 'finished':
                download_queue.update_progress(download_id, {
                    'percent': 99,
                    'status': 'processing',
                    'speed': '',
                    'eta': 'İşleniyor...'
                })
        except Exception as e:
            logger.error(f"Progress hook error: {e}")
    
    downloader = YouTubeDownloaderWithProgress(str(DOWNLOADS_DIR), progress_hook)
    
    try:
        # Video bilgisi al
        info = downloader.get_video_info(url)
        if not info:
            await download_queue.complete_download(download_id, False, {"message": "Video bilgisi alınamadı"})
            return
        
        # Title'ı progress'e ekle
        download_queue.update_progress(download_id, {
            'percent': 0,
            'status': 'starting',
            'title': info.get('title', url)
        })
        
        # Async olarak thread'de çalıştır
        loop = asyncio.get_event_loop()
        if format_type == "audio":
            filepath = await loop.run_in_executor(None, downloader.download_audio, url)
        else:
            filepath = await loop.run_in_executor(None, downloader.download_video, url)
        
        if filepath and os.path.exists(filepath):
            filename = os.path.basename(filepath)
            result = {
                "success": True,
                "filename": filename,
                "title": info.get('title', ''),
                "download_url": f"/api/download/youtube-file/{filename}"
            }
            await download_queue.complete_download(download_id, True, result)
            return
        
        await download_queue.complete_download(download_id, False, {"message": "İndirme başarısız"})
        
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        await download_queue.complete_download(download_id, False, {"message": str(e)})


@api_router.post("/download/video")
async def download_any_video(request: DirectVideoDownloadRequest, background_tasks: BackgroundTasks):
    """Herhangi bir siteden video indir (VK, TikTok, Twitter, vs.) - Sıra sistemi ile"""
    # Sıraya ekle
    download_info = {
        'url': request.url,
        'format': request.format,
        'type': 'video',
        'site': request.site
    }
    download_id = await download_queue.add_to_queue(download_info)
    
    # Background task olarak başlat
    if download_queue.progress_data[download_id]['status'] == 'starting':
        background_tasks.add_task(process_youtube_download, download_id, request.url, request.format)
    else:
        background_tasks.add_task(wait_and_process_download, download_id, request.url, request.format)
    
    return {
        "success": True,
        "download_id": download_id,
        "status": download_queue.progress_data[download_id]['status'],
        "queue_position": download_queue.progress_data[download_id].get('queue_position', 0),
        "message": "İndirme sıraya eklendi" if download_queue.progress_data[download_id]['status'] == 'queued' else "İndirme başlatıldı"
    }


@api_router.get("/video/info")
async def get_any_video_info(url: str):
    """Herhangi bir video URL'sinin bilgisini al"""
    downloader = YouTubeDownloaderWithProgress()
    info = downloader.get_video_info(url)
    if info:
        return {"success": True, "info": info}
    return {"success": False, "message": "Video bilgisi alınamadı"}


@api_router.get("/download/file/{download_id}")
async def get_download_file(download_id: str):
    zip_path = DOWNLOADS_DIR / f"{download_id}.zip"
    if zip_path.exists():
        return FileResponse(str(zip_path), filename=f"images_{download_id}.zip", media_type="application/zip")
    return {"error": "Dosya bulunamadı"}


@api_router.get("/download/youtube-file/{filename}")
async def get_youtube_file(filename: str):
    filepath = DOWNLOADS_DIR / filename
    if filepath.exists():
        return FileResponse(str(filepath), filename=filename)
    return {"error": "Dosya bulunamadı"}


@api_router.get("/youtube/info")
async def get_youtube_info(url: str):
    """YouTube video bilgisi al"""
    downloader = YouTubeDownloaderWithProgress()
    info = downloader.get_video_info(url)
    if info:
        return {"success": True, "info": info}
    return {"success": False, "message": "Bilgi alınamadı"}


# WebSocket
@api_router.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()


@app.on_event("startup")
async def startup():
    await resume_pending_downloads()


async def resume_pending_downloads():
    """Yarım kalan ve kuyrukta bekleyen indirmeleri yeniden başlat."""
    pending_incomplete = list(download_queue.incomplete_downloads.items())
    for old_id, info in pending_incomplete:
        await download_queue.resume_download(old_id)

    await download_queue.prime_queue()

    for download_id, info in list(download_queue.active_downloads.items()):
        url = info.get('url', '')
        format_type = info.get('format', 'video')
        asyncio.create_task(process_youtube_download(download_id, url, format_type))

    for item in list(download_queue.queue):
        download_id = item.get('download_id')
        if not download_id:
            continue
        url = item.get('url', '')
        format_type = item.get('format', 'video')
        asyncio.create_task(wait_and_process_download(download_id, url, format_type))
