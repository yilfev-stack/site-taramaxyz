"""
Download Manager - Kuyruk sistemi ve ilerleme takibi
Maksimum 5 eşzamanlı indirme destekler
"""

import os
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadItem:
    id: str
    url: str
    format: str  # video, audio
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    filename: str = ""
    title: str = ""
    thumbnail: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    file_size: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0


class DownloadManager:
    """Video indirme yöneticisi - kuyruk ve ilerleme takibi"""
    
    MAX_CONCURRENT = 5  # Maksimum eşzamanlı indirme
    
    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = download_dir
        self.queue: Dict[str, DownloadItem] = {}
        self.active_downloads: Dict[str, DownloadItem] = {}
        self.completed_downloads: Dict[str, DownloadItem] = {}
        self.lock = asyncio.Lock()
        self._progress_callbacks: List[Callable] = []
        
        os.makedirs(download_dir, exist_ok=True)
    
    def add_progress_callback(self, callback: Callable):
        """İlerleme callback'i ekle"""
        self._progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable):
        """İlerleme callback'i kaldır"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
    
    async def _notify_progress(self):
        """Tüm callback'lere ilerleme bildir"""
        status = self.get_all_status()
        for callback in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(status)
                else:
                    callback(status)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    def get_all_status(self) -> Dict:
        """Tüm indirmelerin durumunu al"""
        all_items = {}
        all_items.update({k: asdict(v) for k, v in self.queue.items()})
        all_items.update({k: asdict(v) for k, v in self.active_downloads.items()})
        all_items.update({k: asdict(v) for k, v in self.completed_downloads.items()})
        
        return {
            "queue_count": len(self.queue),
            "active_count": len(self.active_downloads),
            "completed_count": len(self.completed_downloads),
            "max_concurrent": self.MAX_CONCURRENT,
            "downloads": all_items
        }
    
    def get_download_status(self, download_id: str) -> Optional[Dict]:
        """Tek bir indirmenin durumunu al"""
        if download_id in self.queue:
            return asdict(self.queue[download_id])
        if download_id in self.active_downloads:
            return asdict(self.active_downloads[download_id])
        if download_id in self.completed_downloads:
            return asdict(self.completed_downloads[download_id])
        return None
    
    async def add_download(self, url: str, format: str = "video") -> Dict:
        """İndirme kuyruğuna ekle"""
        async with self.lock:
            # Aynı URL zaten kuyrukta veya indiriliyor mu kontrol et
            for item in list(self.queue.values()) + list(self.active_downloads.values()):
                if item.url == url and item.format == format:
                    return {
                        "success": False, 
                        "message": "Bu video zaten indirme listesinde",
                        "download_id": item.id
                    }
            
            download_id = str(uuid.uuid4())[:8]
            item = DownloadItem(
                id=download_id,
                url=url,
                format=format
            )
            
            # Önce video bilgisini al
            try:
                info = self._get_video_info(url)
                if info:
                    item.title = info.get('title', '')[:100]
                    item.thumbnail = info.get('thumbnail', '')
            except Exception as e:
                logger.warning(f"Could not get video info: {e}")
            
            self.queue[download_id] = item
            
            # İşlemeyi başlat
            asyncio.create_task(self._process_queue())
            
            return {
                "success": True,
                "download_id": download_id,
                "position": len(self.queue),
                "message": "Kuyruğa eklendi"
            }
    
    async def cancel_download(self, download_id: str) -> Dict:
        """İndirmeyi iptal et"""
        async with self.lock:
            if download_id in self.queue:
                item = self.queue.pop(download_id)
                item.status = DownloadStatus.CANCELLED
                self.completed_downloads[download_id] = item
                await self._notify_progress()
                return {"success": True, "message": "Kuyruktan kaldırıldı"}
            
            if download_id in self.active_downloads:
                # Aktif indirme iptal edilemez (yt-dlp limitation)
                return {"success": False, "message": "Aktif indirme iptal edilemez"}
            
            return {"success": False, "message": "İndirme bulunamadı"}
    
    def _get_video_info(self, url: str) -> Optional[Dict]:
        """Video bilgilerini al"""
        try:
            ydl_opts = {
                'quiet': True, 
                'no_warnings': True,
                'extract_flat': False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Video'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'uploader': info.get('uploader', ''),
                    'view_count': info.get('view_count', 0),
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    async def _process_queue(self):
        """Kuyruğu işle"""
        async with self.lock:
            # Aktif indirme sayısı kontrolü
            while len(self.active_downloads) < self.MAX_CONCURRENT and self.queue:
                # Kuyruktan al
                download_id = next(iter(self.queue))
                item = self.queue.pop(download_id)
                item.status = DownloadStatus.DOWNLOADING
                self.active_downloads[download_id] = item
                
                # İndirmeyi başlat
                asyncio.create_task(self._download_item(item))
    
    async def _download_item(self, item: DownloadItem):
        """Videoyu indir"""
        def progress_hook(d):
            if d['status'] == 'downloading':
                item.progress = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100 if d.get('total_bytes') else 0
                item.speed = d.get('_speed_str', '')
                item.eta = d.get('_eta_str', '')
                item.downloaded_bytes = d.get('downloaded_bytes', 0)
                item.total_bytes = d.get('total_bytes', 0)
                item.file_size = d.get('_total_bytes_str', '')
                # Sync callback notification
                asyncio.create_task(self._notify_progress())
            elif d['status'] == 'finished':
                item.progress = 100
                item.filename = d.get('filename', '')
        
        try:
            if item.format == "audio":
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'progress_hooks': [progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                }
            else:
                ydl_opts = {
                    'format': 'best[height<=720]/best',
                    'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
                    'progress_hooks': [progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                }
            
            # İndirmeyi ayrı thread'de çalıştır
            loop = asyncio.get_event_loop()
            
            def do_download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(item.url, download=True)
                    return ydl.prepare_filename(info)
            
            filepath = await loop.run_in_executor(None, do_download)
            
            # Audio için .mp3 uzantısı
            if item.format == "audio":
                base = os.path.splitext(filepath)[0]
                filepath = base + ".mp3"
            
            if filepath and os.path.exists(filepath):
                item.status = DownloadStatus.COMPLETED
                item.progress = 100
                item.filename = os.path.basename(filepath)
                item.completed_at = datetime.now(timezone.utc).isoformat()
            else:
                item.status = DownloadStatus.FAILED
                item.error = "Dosya oluşturulamadı"
                
        except Exception as e:
            logger.error(f"Download error for {item.url}: {e}")
            item.status = DownloadStatus.FAILED
            item.error = str(e)[:200]
        
        finally:
            # Active'den completed'a taşı
            async with self.lock:
                if item.id in self.active_downloads:
                    del self.active_downloads[item.id]
                self.completed_downloads[item.id] = item
                await self._notify_progress()
                
                # Kuyruğu işlemeye devam et
                await self._process_queue()
    
    def clear_completed(self):
        """Tamamlanan indirmeleri temizle"""
        self.completed_downloads.clear()


# Global download manager instance
download_manager: Optional[DownloadManager] = None


def get_download_manager(download_dir: str = "./downloads") -> DownloadManager:
    """Singleton download manager al"""
    global download_manager
    if download_manager is None:
        download_manager = DownloadManager(download_dir)
    return download_manager
