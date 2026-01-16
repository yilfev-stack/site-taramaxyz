from fastapi import FastAPI, APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
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

from crawler_service import WebsiteCrawler, report_to_dict

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'website_audit')]

# Downloads directory
DOWNLOADS_DIR = ROOT_DIR / 'downloads'
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Create the main app
app = FastAPI(title="Web Sitesi Tarama ve İndirme Aracı")

# Create router with /api prefix
api_router = APIRouter(prefix="/api")

# Global crawler instance
crawler_instance: Optional[WebsiteCrawler] = None
current_report: Optional[dict] = None
crawl_progress: Dict[str, Any] = {
    'status': 'idle',
    'crawled': 0,
    'discovered': 0,
    'issues': 0,
    'message': ''
}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Models
class CrawlStartRequest(BaseModel):
    target_url: str
    max_concurrent: int = 5
    enable_ai_image_analysis: bool = False
    max_pages: int = 100


class DownloadRequest(BaseModel):
    urls: List[str]
    download_type: str = "images"  # images, videos, texts, all


class ContentItem(BaseModel):
    url: str
    type: str  # image, video, text
    title: str = ""
    size: int = 0
    preview: str = ""


# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


# Progress callback
async def progress_callback(progress: dict):
    global crawl_progress
    crawl_progress.update(progress)
    crawl_progress['status'] = 'running'
    crawl_progress['message'] = f"Taranıyor... {progress['crawled']}/{progress['discovered']} sayfa"
    await manager.broadcast(crawl_progress)


# Background crawl task
async def run_crawl_task():
    global crawler_instance, current_report, crawl_progress
    
    try:
        crawl_progress['status'] = 'running'
        crawl_progress['message'] = 'Tarama başlatılıyor...'
        await manager.broadcast(crawl_progress)
        
        report = await crawler_instance.run_crawl(progress_callback)
        current_report = report_to_dict(report)
        
        # Save to MongoDB
        report_doc = current_report.copy()
        report_doc['_id'] = str(uuid.uuid4())
        report_doc['created_at'] = datetime.now(timezone.utc).isoformat()
        await db.reports.insert_one(report_doc)
        
        crawl_progress['status'] = 'completed'
        crawl_progress['message'] = f"Tarama tamamlandı! {current_report['total_urls']} sayfa, {len(current_report.get('images', []))} görsel, {len(current_report.get('videos', []))} video bulundu."
        await manager.broadcast(crawl_progress)
        
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        crawl_progress['status'] = 'error'
        crawl_progress['message'] = f"Hata: {str(e)}"
        await manager.broadcast(crawl_progress)


# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "Web Sitesi Tarama ve İndirme Aracı API"}


@api_router.post("/crawl/start")
async def start_crawl(request: CrawlStartRequest, background_tasks: BackgroundTasks):
    global crawler_instance, crawl_progress
    
    if crawler_instance and crawler_instance.is_running:
        return {"success": False, "message": "Tarama zaten devam ediyor"}
    
    # Reset and create new crawler
    crawler_instance = WebsiteCrawler(
        target_url=request.target_url,
        max_concurrent=request.max_concurrent,
        enable_ai_analysis=request.enable_ai_image_analysis,
        max_pages=request.max_pages
    )
    
    crawl_progress = {
        'status': 'starting',
        'crawled': 0,
        'discovered': 0,
        'issues': 0,
        'message': 'Tarama hazırlanıyor...'
    }
    
    # Start crawl in background
    background_tasks.add_task(run_crawl_task)
    
    return {"success": True, "message": "Tarama başlatıldı"}


@api_router.post("/crawl/stop")
async def stop_crawl():
    global crawler_instance, crawl_progress
    
    if crawler_instance:
        crawler_instance.stop_crawl()
        crawl_progress['status'] = 'stopped'
        crawl_progress['message'] = 'Tarama durduruldu'
        return {"success": True, "message": "Tarama durduruldu"}
    
    return {"success": False, "message": "Aktif tarama yok"}


@api_router.get("/crawl/status")
async def get_crawl_status():
    return crawl_progress


@api_router.get("/report/summary")
async def get_report_summary():
    global current_report
    
    if not current_report:
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            latest['id'] = str(latest.pop('_id'))
            current_report = latest
        else:
            return {"error": "Henüz rapor yok. Önce tarama başlatın."}
    
    return {
        'domain': current_report.get('domain', ''),
        'target_url': current_report.get('target_url', ''),
        'start_time': current_report.get('start_time', ''),
        'end_time': current_report.get('end_time', ''),
        'total_urls': current_report.get('total_urls', 0),
        'total_images': len(current_report.get('images', [])),
        'total_videos': len(current_report.get('videos', [])),
        'total_texts': len(current_report.get('texts', [])),
        'issues_count': len(current_report.get('issues', []))
    }


@api_router.get("/report/images")
async def get_images(page: int = 1, limit: int = 50):
    global current_report
    
    if not current_report:
        return {"images": [], "total": 0}
    
    images = current_report.get('images', [])
    total = len(images)
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "images": images[start:end],
        "total": total,
        "page": page,
        "limit": limit
    }


@api_router.get("/report/videos")
async def get_videos(page: int = 1, limit: int = 50):
    global current_report
    
    if not current_report:
        return {"videos": [], "total": 0}
    
    videos = current_report.get('videos', [])
    total = len(videos)
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "videos": videos[start:end],
        "total": total,
        "page": page,
        "limit": limit
    }


@api_router.get("/report/texts")
async def get_texts(page: int = 1, limit: int = 50):
    global current_report
    
    if not current_report:
        return {"texts": [], "total": 0}
    
    texts = current_report.get('texts', [])
    total = len(texts)
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "texts": texts[start:end],
        "total": total,
        "page": page,
        "limit": limit
    }


@api_router.get("/report/issues")
async def get_issues(page: int = 1, limit: int = 50):
    global current_report
    
    if not current_report:
        return {"issues": [], "total": 0}
    
    issues = current_report.get('issues', [])
    total = len(issues)
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "issues": issues[start:end],
        "total": total,
        "page": page,
        "limit": limit
    }


@api_router.post("/download/start")
async def start_download(request: DownloadRequest):
    """İçerikleri indir ve ZIP olarak hazırla"""
    
    download_id = str(uuid.uuid4())[:8]
    download_dir = DOWNLOADS_DIR / download_id
    download_dir.mkdir(exist_ok=True)
    
    downloaded_files = []
    errors = []
    
    async with aiohttp.ClientSession() as session:
        for url in request.urls:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30), ssl=False) as response:
                    if response.status == 200:
                        # Get filename from URL
                        filename = url.split('/')[-1].split('?')[0]
                        if not filename:
                            filename = f"file_{len(downloaded_files)}"
                        
                        # Add extension if missing
                        content_type = response.headers.get('content-type', '')
                        if '.' not in filename:
                            if 'image' in content_type:
                                filename += '.jpg'
                            elif 'video' in content_type:
                                filename += '.mp4'
                            else:
                                filename += '.txt'
                        
                        filepath = download_dir / filename
                        
                        # Avoid duplicate filenames
                        counter = 1
                        while filepath.exists():
                            name, ext = os.path.splitext(filename)
                            filepath = download_dir / f"{name}_{counter}{ext}"
                            counter += 1
                        
                        content = await response.read()
                        async with aiofiles.open(filepath, 'wb') as f:
                            await f.write(content)
                        
                        downloaded_files.append(str(filepath.name))
            except Exception as e:
                errors.append({"url": url, "error": str(e)})
    
    # Create ZIP file
    if downloaded_files:
        zip_path = DOWNLOADS_DIR / f"{download_id}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in downloaded_files:
                file_path = download_dir / file
                zipf.write(file_path, file)
        
        # Cleanup individual files
        shutil.rmtree(download_dir)
        
        return {
            "success": True,
            "download_id": download_id,
            "files_count": len(downloaded_files),
            "errors": errors,
            "download_url": f"/api/download/file/{download_id}"
        }
    
    return {
        "success": False,
        "message": "Hiçbir dosya indirilemedi",
        "errors": errors
    }


@api_router.get("/download/file/{download_id}")
async def download_file(download_id: str):
    """ZIP dosyasını indir"""
    zip_path = DOWNLOADS_DIR / f"{download_id}.zip"
    
    if zip_path.exists():
        return FileResponse(
            path=str(zip_path),
            filename=f"download_{download_id}.zip",
            media_type="application/zip"
        )
    
    return {"error": "Dosya bulunamadı"}


@api_router.get("/report/export/csv")
async def export_csv():
    global current_report
    
    if not current_report:
        return {"error": "Rapor yok"}
    
    issues = current_report.get('issues', [])
    
    output = io.StringIO()
    fieldnames = ['source_url', 'issue_type', 'element_text', 'target_url', 'severity', 'fix_suggestion']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for issue in issues:
        row = {k: issue.get(k, '') for k in fieldnames}
        writer.writerow(row)
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_report.csv"}
    )


# WebSocket endpoint
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
