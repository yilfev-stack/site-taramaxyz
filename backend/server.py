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

# Gelişmiş crawler
from advanced_crawler import AdvancedCrawler, YouTubeDownloader, report_to_dict

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
            except:
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
async def download_youtube(request: YouTubeDownloadRequest):
    """YouTube video/ses indir"""
    downloader = YouTubeDownloader(str(DOWNLOADS_DIR))
    
    try:
        # Video bilgisi al
        info = downloader.get_video_info(request.url)
        if not info:
            return {"success": False, "message": "Video bilgisi alınamadı"}
        
        # İndir
        if request.format == "audio":
            filepath = downloader.download_audio(request.url)
        else:
            filepath = downloader.download_video(request.url)
        
        if filepath and os.path.exists(filepath):
            filename = os.path.basename(filepath)
            return {
                "success": True,
                "filename": filename,
                "title": info.get('title', ''),
                "download_url": f"/api/download/youtube-file/{filename}"
            }
        
        return {"success": False, "message": "İndirme başarısız"}
        
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return {"success": False, "message": str(e)}


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
    downloader = YouTubeDownloader()
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
