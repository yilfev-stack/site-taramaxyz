from fastapi import FastAPI, APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import asyncio
import json
import csv
import io

from crawler_service import DemartCrawler, report_to_dict, CrawlReport

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'demart_audit')]

# Create the main app
app = FastAPI(title="Demart.com.tr Web Sitesi Denetim Aracı")

# Create router with /api prefix
api_router = APIRouter(prefix="/api")

# Global crawler instance
crawler_instance: Optional[DemartCrawler] = None
current_report: Optional[dict] = None
crawl_progress: Dict[str, Any] = {
    'status': 'idle',
    'crawled': 0,
    'discovered': 0,
    'issues': 0,
    'message': ''
}

# WebSocket connections
active_connections: List[WebSocket] = []

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Models
class CrawlStartRequest(BaseModel):
    target_url: str = "https://www.demart.com.tr"
    max_concurrent: int = 5
    enable_ai_image_analysis: bool = True  # AI görsel analizi etkinleştir


class CrawlStatusResponse(BaseModel):
    status: str
    crawled: int
    discovered: int
    issues: int
    message: str


class IssueResponse(BaseModel):
    source_url: str
    source_language: str
    issue_type: str
    element_text: str
    target_url: str
    http_status: int
    final_url: str
    severity: str
    fix_suggestion: str
    element_location: str = ""


class ReportSummary(BaseModel):
    domain: str
    start_time: str
    end_time: str
    total_urls: int
    tr_pages: int
    en_pages: int
    broken_links: int
    broken_images: int
    language_errors: int
    redirect_loops: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int


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
        crawl_progress['message'] = f"Tarama tamamlandı! {current_report['total_urls']} sayfa tarandı, {len(current_report['issues'])} sorun bulundu."
        await manager.broadcast(crawl_progress)
        
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        crawl_progress['status'] = 'error'
        crawl_progress['message'] = f"Hata: {str(e)}"
        await manager.broadcast(crawl_progress)


# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "Demart.com.tr Web Sitesi Denetim Aracı API"}


@api_router.post("/crawl/start")
async def start_crawl(request: CrawlStartRequest, background_tasks: BackgroundTasks):
    global crawler_instance, crawl_progress
    
    if crawler_instance and crawler_instance.is_running:
        return {"success": False, "message": "Tarama zaten devam ediyor"}
    
    # Reset and create new crawler
    crawler_instance = DemartCrawler()
    crawler_instance.MAX_CONCURRENT = request.max_concurrent
    
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


@api_router.get("/crawl/status", response_model=CrawlStatusResponse)
async def get_crawl_status():
    return CrawlStatusResponse(**crawl_progress)


@api_router.get("/report/summary")
async def get_report_summary():
    global current_report
    
    if not current_report:
        # Try to get latest from DB
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            del latest['_id']
            current_report = latest
        else:
            return {"error": "Henüz rapor yok. Önce tarama başlatın."}
    
    # Calculate severity counts
    issues = current_report.get('issues', [])
    critical = sum(1 for i in issues if i.get('severity') == 'Critical')
    high = sum(1 for i in issues if i.get('severity') == 'High')
    medium = sum(1 for i in issues if i.get('severity') == 'Medium')
    low = sum(1 for i in issues if i.get('severity') == 'Low')
    
    return {
        'domain': current_report.get('domain', ''),
        'start_time': current_report.get('start_time', ''),
        'end_time': current_report.get('end_time', ''),
        'total_urls': current_report.get('total_urls', 0),
        'tr_pages': current_report.get('tr_pages', 0),
        'en_pages': current_report.get('en_pages', 0),
        'broken_links': current_report.get('broken_links', 0),
        'broken_images': current_report.get('broken_images', 0),
        'language_errors': current_report.get('language_errors', 0),
        'redirect_loops': current_report.get('redirect_loops', 0),
        'critical_issues': critical,
        'high_issues': high,
        'medium_issues': medium,
        'low_issues': low,
        'total_issues': len(issues)
    }


@api_router.get("/report/issues")
async def get_report_issues(
    issue_type: Optional[str] = None,
    severity: Optional[str] = None,
    language: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    global current_report
    
    if not current_report:
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            del latest['_id']
            current_report = latest
        else:
            return {"issues": [], "total": 0}
    
    issues = current_report.get('issues', [])
    
    # Filter
    if issue_type:
        issues = [i for i in issues if i.get('issue_type') == issue_type]
    if severity:
        issues = [i for i in issues if i.get('severity') == severity]
    if language:
        issues = [i for i in issues if i.get('source_language') == language]
    
    # Paginate
    total = len(issues)
    start = (page - 1) * limit
    end = start + limit
    paginated = issues[start:end]
    
    return {
        "issues": paginated,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@api_router.get("/report/urls")
async def get_all_urls(
    language: Optional[str] = None,
    page: int = 1,
    limit: int = 100
):
    global current_report
    
    if not current_report:
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            del latest['_id']
            current_report = latest
        else:
            return {"urls": [], "total": 0}
    
    urls = current_report.get('all_urls', [])
    
    if language:
        urls = [u for u in urls if u.get('language') == language]
    
    total = len(urls)
    start = (page - 1) * limit
    end = start + limit
    paginated = urls[start:end]
    
    return {
        "urls": paginated,
        "total": total,
        "page": page,
        "limit": limit
    }


@api_router.get("/report/export/csv")
async def export_csv():
    global current_report
    
    if not current_report:
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            del latest['_id']
            current_report = latest
        else:
            return {"error": "Rapor yok"}
    
    issues = current_report.get('issues', [])
    
    # Create CSV
    output = io.StringIO()
    fieldnames = [
        'source_url', 'source_language', 'issue_type', 'element_text',
        'target_url', 'http_status', 'final_url', 'severity',
        'fix_suggestion', 'element_location'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for issue in issues:
        row = {k: issue.get(k, '') for k in fieldnames}
        writer.writerow(row)
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=demart_audit_report.csv"}
    )


@api_router.get("/report/export/json")
async def export_json():
    global current_report
    
    if not current_report:
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            del latest['_id']
            current_report = latest
        else:
            return {"error": "Rapor yok"}
    
    return current_report


@api_router.get("/report/top-issues")
async def get_top_issues(limit: int = 10):
    global current_report
    
    if not current_report:
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            del latest['_id']
            current_report = latest
        else:
            return {"issues": []}
    
    issues = current_report.get('issues', [])
    
    # Sort by severity
    severity_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
    sorted_issues = sorted(issues, key=lambda x: severity_order.get(x.get('severity', 'Low'), 4))
    
    return {"issues": sorted_issues[:limit]}


@api_router.get("/report/stats")
async def get_issue_stats():
    global current_report
    
    if not current_report:
        latest = await db.reports.find_one(sort=[('created_at', -1)])
        if latest:
            del latest['_id']
            current_report = latest
        else:
            return {"stats": {}}
    
    issues = current_report.get('issues', [])
    
    # Group by issue type
    by_type = {}
    for issue in issues:
        itype = issue.get('issue_type', 'unknown')
        by_type[itype] = by_type.get(itype, 0) + 1
    
    # Group by severity
    by_severity = {}
    for issue in issues:
        sev = issue.get('severity', 'Low')
        by_severity[sev] = by_severity.get(sev, 0) + 1
    
    # Group by location
    by_location = {}
    for issue in issues:
        loc = issue.get('element_location', 'unknown')
        by_location[loc] = by_location.get(loc, 0) + 1
    
    return {
        "by_type": by_type,
        "by_severity": by_severity,
        "by_location": by_location
    }


@api_router.get("/history")
async def get_crawl_history(limit: int = 10):
    reports = await db.reports.find(
        {},
        {'issues': 0, 'all_urls': 0}  # Exclude large fields
    ).sort('created_at', -1).limit(limit).to_list(limit)
    
    for r in reports:
        r['id'] = str(r.pop('_id'))
    
    return {"reports": reports}


# WebSocket endpoint for real-time progress
@api_router.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
