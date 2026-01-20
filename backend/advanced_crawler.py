"""
Gelişmiş Web Tarayıcı - Playwright + yt-dlp
JavaScript render'lı siteleri ve YouTube videolarını destekler
"""

import asyncio
import os
import re
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from urllib.parse import urljoin, urlparse
import aiohttp
import aiofiles
import json

# Set Playwright browsers path
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/pw-browsers'

# Playwright
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

# yt-dlp
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MediaItem:
    url: str
    type: str  # image, video, youtube, text
    title: str = ""
    thumbnail: str = ""
    size_kb: float = 0
    page_url: str = ""
    downloadable: bool = True


@dataclass
class CrawlReport:
    domain: str
    target_url: str
    start_time: str
    end_time: str = ""
    total_urls: int = 0
    images: List[Dict] = field(default_factory=list)
    videos: List[Dict] = field(default_factory=list)
    youtube_videos: List[Dict] = field(default_factory=list)
    texts: List[Dict] = field(default_factory=list)
    issues: List[Dict] = field(default_factory=list)


class AdvancedCrawler:
    """Playwright tabanlı gelişmiş tarayıcı"""
    
    def __init__(self, target_url: str, max_pages: int = 50, download_dir: str = "./downloads"):
        self.target_url = target_url.rstrip('/')
        parsed = urlparse(target_url)
        self.base_domain = parsed.netloc
        self.base_path = parsed.path.rstrip('/')
        self.restrict_to_start_page = 'vk.com' in self.base_domain or 'vkvideo.ru' in self.base_domain
        self.max_pages = max_pages
        self.download_dir = download_dir
        
        self.visited_urls: Set[str] = set()
        self.discovered_urls: Set[str] = set()
        self.images: List[MediaItem] = []
        self.videos: List[MediaItem] = []
        self.youtube_videos: List[MediaItem] = []
        self.texts: List[Dict] = []
        self.issues: List[Dict] = []
        
        self.browser: Optional[Browser] = None
        self.is_running = False
        self.should_stop = False
        self.progress_callback = None
        
        os.makedirs(download_dir, exist_ok=True)

    def is_internal_url(self, url: str) -> bool:
        if self.restrict_to_start_page:
            return url.rstrip('/') == self.target_url
        parsed = urlparse(url)
        if self.base_domain not in parsed.netloc:
            return False
        if not self.base_path:
            return True
        candidate_path = parsed.path.rstrip('/')
        return candidate_path == self.base_path or candidate_path.startswith(f"{self.base_path}/")

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """YouTube video ID'sini çıkar"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def normalize_vk_url(self, vk_url: str) -> Optional[str]:
        """VK video/clip URL'lerini normalize et ve doğrula."""
        if not vk_url:
            return None

        if 'video_ext.php' in vk_url or 'embed' in vk_url:
            match = re.search(r'oid=(-?\d+).*id=(\d+)', vk_url)
            if match:
                vk_url = f"https://vk.com/video{match.group(1)}_{match.group(2)}"

        if 'vkvideo.ru' in vk_url:
            match = re.search(r'(video|clip)(-?\d+_\d+)', vk_url)
            if match:
                vk_url = f"https://vk.com/{match.group(1)}{match.group(2)}"

        if not re.search(r'(video|clip)-?\d+_\d+', vk_url):
            return None

        return vk_url

    async def safe_goto(self, page: Page, url: str) -> Optional[str]:
        """Ağ hatalarına karşı sayfa geçişini birkaç kez dene."""
        last_error = None
        for attempt in range(3):
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=45000)
                return None
            except PlaywrightTimeoutError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc)
            logger.warning(f"Navigation failed ({attempt + 1}/3) for {url}: {last_error}")
            await page.wait_for_timeout(1000)
        return last_error

    async def crawl_page(self, page: Page, url: str) -> None:
        """Tek bir sayfayı Playwright ile tara"""
        if self.should_stop or url in self.visited_urls:
            return

        if len(self.visited_urls) >= self.max_pages:
            return

        self.visited_urls.add(url)
        logger.info(f"Crawling: {url}")

        try:
            # Sayfaya git
            goto_error = await self.safe_goto(page, url)
            if goto_error:
                self.issues.append({
                    'source_url': url,
                    'issue_type': 'network_error',
                    'severity': 'High',
                    'fix_suggestion': goto_error
                })
                return
            await page.wait_for_timeout(500)  # JS'in yüklenmesini bekle
            if "vk.com" in url or "vkvideo.ru" in url:
                await page.wait_for_timeout(1000)
                try:
                    await page.wait_for_selector('a[href*="video"], .VideoCard', timeout=1500)
                except Exception:
                    pass

            # Görselleri topla
            images = await page.evaluate(r'''() => {
                const imgs = [];
                document.querySelectorAll('img').forEach(img => {
                    const src = img.src || img.dataset.src || img.dataset.lazy;
                    if (src && !src.startsWith('data:')) {
                        imgs.push({
                            url: src,
                            alt: img.alt || '',
                            width: img.naturalWidth || img.width || 0,
                            height: img.naturalHeight || img.height || 0
                        });
                    }
                });
                // Background images
                document.querySelectorAll('*').forEach(el => {
                    const bg = getComputedStyle(el).backgroundImage;
                    if (bg && bg !== 'none') {
                        const match = bg.match(/url\\(["']?([^"')]+)["']?\\)/);
                        if (match && !match[1].startsWith('data:')) {
                            imgs.push({ url: match[1], alt: 'Background', width: 0, height: 0 });
                        }
                    }
                });
                return imgs;
            }''')

            
            for img in images:
                if img['width'] >= 50 or img['height'] >= 50 or img['width'] == 0:
                    self.images.append(MediaItem(
                        url=img['url'],
                        type='image',
                        title=img['alt'],
                        page_url=url
                    ))
            
            # Videoları topla - Önce sayfa URL'lerini bul (VK, YouTube, vb.)
            async def collect_videos():
                return await page.evaluate(r'''() => {
                const vids = [];
                const seen = new Set();
                const currentUrl = window.location.href;
                const isVkSite = currentUrl.includes('vk.com') || currentUrl.includes('vkvideo.ru');
                const getBackgroundImage = (el) => {
                    if (!el) return '';
                    const style = getComputedStyle(el).backgroundImage;
                    if (!style || style === 'none') {
                        return '';
                    }
                    const match = style.match(/url\\(["']?([^"')]+)["']?\\)/);
                    return match ? match[1] : '';
                };
                const isVisible = (el) => {
                    if (!el) return false;
                    if (el.hidden) return false;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                        return false;
                    }
                    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                };
                const isInViewport = (el) => {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.bottom > 0 && rect.right > 0 &&
                        rect.top < (window.innerHeight || document.documentElement.clientHeight) &&
                        rect.left < (window.innerWidth || document.documentElement.clientWidth);
                };
                const shouldIncludeElement = (el) => isVisible(el) && isInViewport(el);
                
                // VK video sayfalarında - video kartlarından URL'leri çıkar
                if (isVkSite) {
                    // VK video kartları - farklı seçiciler dene
                    const vkSelectors = [
                        'a[href*="/video-"]',
                        'a[href*="/video@"]',
                        'a[href*="video"][href*="_"]',
                        '[data-video-id]',
                        '.VideoCard a',
                        '.video_item a',
                        '.VideoThumb a'
                    ];
                    
                    vkSelectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => {
                            if (!shouldIncludeElement(el)) {
                                return;
                            }
                            let href = el.href || el.getAttribute('href');
                            const videoId = el.dataset?.videoId;
                            const rawId = el.dataset?.videoRawId;
                            const thumbData = el.dataset?.thumb || el.dataset?.preview || el.dataset?.poster;
                            
                            // data-video-id varsa URL oluştur
                            if (videoId && !href) {
                                href = 'https://vk.com/video' + videoId;
                            }
                            if (rawId && !href) {
                                href = 'https://vk.com/video' + rawId;
                            }
                            
                            if (href && !seen.has(href)) {
                                // VK video URL formatını kontrol et
                                const vkMatch = href.match(/video(-?\d+_\d+)/);
                                if (vkMatch) {
                                    const cleanUrl = 'https://vk.com/video' + vkMatch[1];
                                    if (!seen.has(cleanUrl)) {
                                        seen.add(cleanUrl);
                                        // Thumbnail bulmaya çalış
                                        let thumb = '';
                                        const img = el.querySelector('img') || el.closest('.VideoCard')?.querySelector('img');
                                        if (img) {
                                            thumb = img.src || img.dataset.src || img.dataset.lazy || img.dataset.lazySrc || '';
                                        }
                                        if (!thumb && thumbData) {
                                            thumb = thumbData;
                                        }
                                        if (!thumb) {
                                            thumb = getBackgroundImage(el) || getBackgroundImage(el.closest('.VideoCard') || el);
                                        }
                                        vids.push({ url: cleanUrl, type: 'vk', thumbnail: thumb });
                                    }
                                }
                            }
                        });
                    });
                }
                
                // CDN video URL'lerini ATLA - bunlar süreli ve çalışmaz
                // Sadece direkt indirilebilir video dosyalarını al (.mp4 dosyaları)
                document.querySelectorAll('video').forEach(v => {
                    if (!shouldIncludeElement(v)) {
                        return;
                    }
                    let src = v.src || v.currentSrc;
                    // CDN URL'lerini atla
                    if (src && !src.startsWith('blob:') && !src.includes('okcdn') && !src.includes('vkuservideo')) {
                        // Sadece temiz .mp4/.webm URL'lerini al
                        if (src.match(/\.(mp4|webm|mov)(\?|$)/i) && !seen.has(src)) {
                            seen.add(src);
                            vids.push({ url: src, type: 'video' });
                        }
                    }
                });
                
                // YouTube iframes
                document.querySelectorAll('iframe').forEach(iframe => {
                    if (!shouldIncludeElement(iframe)) {
                        return;
                    }
                    const src = iframe.src || iframe.dataset.src;
                    if (src && !seen.has(src)) {
                        if (src.includes('youtube') || src.includes('youtu.be')) {
                            seen.add(src);
                            vids.push({ url: src, type: 'youtube' });
                        } else if (src.includes('vimeo')) {
                            seen.add(src);
                            vids.push({ url: src, type: 'vimeo' });
                        } else if (src.includes('vk.com') || src.includes('vkvideo')) {
                            seen.add(src);
                            vids.push({ url: src, type: 'vk' });
                        } else if (src.includes('dailymotion')) {
                            seen.add(src);
                            vids.push({ url: src, type: 'dailymotion' });
                        }
                    }
                });
                
                // YouTube links
                document.querySelectorAll('a[href*="youtube"], a[href*="youtu.be"]').forEach(a => {
                    if (!shouldIncludeElement(a)) {
                        return;
                    }
                    if (!seen.has(a.href)) {
                        seen.add(a.href);
                        vids.push({ url: a.href, type: 'youtube' });
                    }
                });
                
                // VK video links
                document.querySelectorAll('a[href*="vk.com/video"], a[href*="vkvideo"], a[href*="vkvideo.ru/video"], a[href*="vkvideo.ru/clip"]').forEach(a => {
                    if (!shouldIncludeElement(a)) {
                        return;
                    }
                    if (!seen.has(a.href)) {
                        seen.add(a.href);
                        vids.push({ url: a.href, type: 'vk' });
                    }
                });
                
                // Genel video linkleri (.mp4, .webm, .avi, .mov)
                document.querySelectorAll('a[href$=".mp4"], a[href$=".webm"], a[href$=".avi"], a[href$=".mov"], a[href$=".m3u8"]').forEach(a => {
                    if (!shouldIncludeElement(a)) {
                        return;
                    }
                    if (!seen.has(a.href)) {
                        seen.add(a.href);
                        vids.push({ url: a.href, type: 'video' });
                    }
                });
                
                // data-video attributes
                document.querySelectorAll('[data-video], [data-video-url], [data-video-src]').forEach(el => {
                    if (!shouldIncludeElement(el)) {
                        return;
                    }
                    const src = el.dataset.video || el.dataset.videoUrl || el.dataset.videoSrc;
                    if (src && !src.startsWith('blob:') && !seen.has(src)) {
                        seen.add(src);
                        vids.push({ url: src, type: 'video' });
                    }
                });
                
              videos = []
            seen_video_urls = set()
            is_vk_page = "vk.com" in url or "vkvideo.ru" in url
            scroll_steps = 30 if is_vk_page else 1
            stable_rounds = 0
            for _ in range(scroll_steps):
                before_count = len(seen_video_urls)
                batch = await collect_videos()
                for item in batch:
                    item_url = item.get('url')
                    if item_url and item_url not in seen_video_urls:
                        seen_video_urls.add(item_url)
                        videos.append(item)
                if not is_vk_page:
                    break
                if len(seen_video_urls) == before_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                if stable_rounds >= 2:
                    break
                await page.evaluate("window.scrollBy(0, Math.floor(window.innerHeight * 0.9));")
                await page.wait_for_timeout(800)
            await page.evaluate("window.scrollTo(0, 0);")
            
            for vid in videos:
                # Blob URL'leri atla
                if vid['url'].startswith('blob:'):
                    continue

                    
                if vid['type'] == 'youtube':
                    yt_id = self.extract_youtube_id(vid['url'])
                    if yt_id:
                        self.youtube_videos.append(MediaItem(
                            url=f"https://www.youtube.com/watch?v={yt_id}",
                            type='youtube',
                            title=f"YouTube Video: {yt_id}",
                            thumbnail=f"https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg",
                            page_url=url,
                            downloadable=True
                        ))
                elif vid['type'] == 'vk':
                    vk_url = self.normalize_vk_url(vid['url'])
                    if not vk_url:
                        continue

                    # Thumbnail varsa ekle
                    thumbnail = vid.get('thumbnail', '')
                    self.videos.append(MediaItem(
                        url=vk_url,
                        type='vk',
                        thumbnail=thumbnail,
                        page_url=url,
                        downloadable=True
                    ))
                else:
                    self.videos.append(MediaItem(
                        url=vid['url'],
                        type=vid.get('type', 'video'),
                        page_url=url,
                        downloadable=True
                    ))
           
            # Metinleri topla
            texts = await page.evaluate(r'''() => {
                const txts = [];
                document.querySelectorAll('h1, h2, h3, p').forEach(el => {
                    const text = el.innerText.trim();
                    if (text.length > 50) {
                        txts.push({
                            content: text.substring(0, 500),
                            type: el.tagName.toLowerCase(),
                            wordCount: text.split(/\\s+/).length
                        });
                    }
                });
                return txts;
            }''')
            
            for txt in texts:
                self.texts.append({
                    'content': txt['content'],
                    'type': txt['type'],
                    'word_count': txt['wordCount'],
                    'page_url': url
                })
            
            # Internal linkleri topla
            links = await page.evaluate(r'''() => {
                const hrefs = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    if (a.href && !a.href.startsWith('javascript:') && !a.href.startsWith('#')) {
                        hrefs.push(a.href);
                    }
                });
                return hrefs;
            }''')
            
            for link in links:
                if self.is_internal_url(link):
                    self.discovered_urls.add(link.split('#')[0].rstrip('/'))
            
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            self.issues.append({
                'source_url': url,
                'issue_type': 'crawl_error',
                'severity': 'High',
                'fix_suggestion': str(e)
            })

    async def run_crawl(self, progress_callback=None) -> CrawlReport:
        """Ana tarama işlemi"""
        self.is_running = True
        self.should_stop = False
        self.progress_callback = progress_callback
        start_time = datetime.now().isoformat()
        
        async with async_playwright() as p:
            self.browser = await p.chromium.launch(headless=True)
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                ignore_https_errors=True
            )
            page = await context.new_page()
            
            # İlk URL'yi ekle
            self.discovered_urls.add(self.target_url)
            
            try:
                iteration = 0
                while iteration < 20 and not self.should_stop:
                    urls_to_crawl = list(self.discovered_urls - self.visited_urls)
                    
                    if not urls_to_crawl or len(self.visited_urls) >= self.max_pages:
                        break
                    
                    for url in urls_to_crawl[:10]:  # Batch of 10
                        if self.should_stop:
                            break
                        await self.crawl_page(page, url)
                        
                        if progress_callback:
                            await progress_callback({
                                'crawled': len(self.visited_urls),
                                'discovered': len(self.discovered_urls),
                                'images': len(self.images),
                                'videos': len(self.videos) + len(self.youtube_videos),
                                'issues': len(self.issues)
                            })
                    
                    iteration += 1
                    
            finally:
                await self.browser.close()
        
        # Duplicate'leri kaldır
        seen_urls = set()
        unique_images = []
        for img in self.images:
            if img.url not in seen_urls:
                seen_urls.add(img.url)
                unique_images.append(img)
        self.images = unique_images
        
        seen_yt = set()
        unique_yt = []
        for yt in self.youtube_videos:
            if yt.url not in seen_yt:
                seen_yt.add(yt.url)
                unique_yt.append(yt)
        self.youtube_videos = unique_yt

        seen_videos = set()
        unique_videos = []
        for vid in self.videos:
            if vid.url not in seen_videos:
                seen_videos.add(vid.url)
                unique_videos.append(vid)
        self.videos = unique_videos
        
        self.is_running = False
        
        return CrawlReport(
            domain=self.base_domain,
            target_url=self.target_url,
            start_time=start_time,
            end_time=datetime.now().isoformat(),
            total_urls=len(self.visited_urls),
            images=[asdict(img) for img in self.images],
            videos=[asdict(vid) for vid in self.videos],
            youtube_videos=[asdict(yt) for yt in self.youtube_videos],
            texts=self.texts[:100],
            issues=self.issues
        )

    def stop_crawl(self):
        self.should_stop = True


class YouTubeDownloader:
    """yt-dlp ile YouTube video indirici"""
    
    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
    
    def get_video_info(self, url: str) -> Optional[Dict]:
        """Video bilgilerini al"""
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'description': info.get('description', '')[:200] if info.get('description') else '',
                    'view_count': info.get('view_count', 0),
                    'uploader': info.get('uploader', '')
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def download_video(self, url: str, quality: str = 'best') -> Optional[str]:
        """Video indir"""
        try:
            ydl_opts = {
                'format': 'best[height<=720]' if quality == 'medium' else 'best',
                'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                logger.info(f"Downloaded: {filename}")
                return filename
                
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None
    
    def download_audio(self, url: str) -> Optional[str]:
        """Sadece ses indir (MP3)"""
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return os.path.join(self.download_dir, f"{info['title']}.mp3")
                
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            return None


class YouTubeDownloaderWithProgress:
    """yt-dlp ile YouTube video indirici - Progress tracking ile"""
    
    def __init__(self, download_dir: str = "./downloads", progress_hook=None):
        self.download_dir = download_dir
        self.progress_hook = progress_hook
        os.makedirs(download_dir, exist_ok=True)
    
    def get_video_info(self, url: str) -> Optional[Dict]:
        """Video bilgilerini al"""
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'description': info.get('description', '')[:200] if info.get('description') else '',
                    'view_count': info.get('view_count', 0),
                    'uploader': info.get('uploader', '')
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def download_video(self, url: str, quality: str = 'best') -> Optional[str]:
        """Video indir - Progress tracking ile"""
        try:
            ydl_opts = {
                'format': 'best[height<=720]' if quality == 'medium' else 'best',
                'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'continuedl': True,  # Yarım kalan indirmeleri devam ettir
                'nopart': False,  # .part dosyaları kullan
            }
            
            # Progress hook ekle
            if self.progress_hook:
                ydl_opts['progress_hooks'] = [self.progress_hook]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                logger.info(f"Downloaded: {filename}")
                return filename
                
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None
    
    def download_audio(self, url: str) -> Optional[str]:
        """Sadece ses indir (MP3) - Progress tracking ve hız optimizasyonu ile"""
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': True,
                'noprogress': False,
                # Hız optimizasyonları
                'concurrent_fragment_downloads': 4,
                'buffersize': 1024 * 16,
                'retries': 10,
                'continuedl': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            # Progress hook ekle
            if self.progress_hook:
                ydl_opts['progress_hooks'] = [self.progress_hook]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return os.path.join(self.download_dir, f"{info['title']}.mp3")
                
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            return None


def report_to_dict(report: CrawlReport) -> dict:
    return asdict(report)


# Test
if __name__ == "__main__":
    async def test():
        crawler = AdvancedCrawler("https://www.example.com", max_pages=5)
        report = await crawler.run_crawl()
        print(f"Found {len(report.images)} images, {len(report.youtube_videos)} YouTube videos")
    
    asyncio.run(test())
