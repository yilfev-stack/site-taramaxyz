"""
Web Sitesi Tarama ve İçerik Toplama Servisi
Herhangi bir web sitesini tarar, görselleri, videoları ve metinleri toplar
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Set, Optional, Tuple
import re
from datetime import datetime
import logging
from dataclasses import dataclass, field, asdict
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ImageInfo:
    url: str
    alt: str = ""
    width: int = 0
    height: int = 0
    size_kb: float = 0
    page_url: str = ""


@dataclass
class VideoInfo:
    url: str
    title: str = ""
    thumbnail: str = ""
    type: str = ""  # youtube, vimeo, mp4, etc.
    page_url: str = ""


@dataclass
class TextInfo:
    content: str
    title: str = ""
    type: str = ""  # heading, paragraph, article
    page_url: str = ""
    word_count: int = 0


@dataclass
class CrawlIssue:
    source_url: str
    issue_type: str
    element_text: str
    target_url: str
    severity: str
    fix_suggestion: str


@dataclass
class CrawlReport:
    domain: str
    target_url: str
    start_time: str
    end_time: str = ""
    total_urls: int = 0
    images: List[Dict] = field(default_factory=list)
    videos: List[Dict] = field(default_factory=list)
    texts: List[Dict] = field(default_factory=list)
    issues: List[Dict] = field(default_factory=list)


class WebsiteCrawler:
    """Herhangi bir web sitesini tarar"""
    
    def __init__(self, target_url: str, max_concurrent: int = 5, 
                 enable_ai_analysis: bool = False, max_pages: int = 100):
        self.target_url = target_url.rstrip('/')
        parsed = urlparse(target_url)
        self.base_domain = parsed.netloc
        self.base_scheme = parsed.scheme or 'https'
        
        self.max_concurrent = max_concurrent
        self.max_pages = max_pages
        self.enable_ai_analysis = enable_ai_analysis
        
        self.visited_urls: Set[str] = set()
        self.discovered_urls: Set[str] = set()
        self.images: List[ImageInfo] = []
        self.videos: List[VideoInfo] = []
        self.texts: List[TextInfo] = []
        self.issues: List[CrawlIssue] = []
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.progress_callback = None
        self.is_running = False
        self.should_stop = False

    def normalize_url(self, url: str) -> str:
        """URL'yi normalize et"""
        parsed = urlparse(url)
        path = parsed.path.rstrip('/') or '/'
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized

    def is_internal_url(self, url: str) -> bool:
        """URL internal mi kontrol et"""
        parsed = urlparse(url)
        return self.base_domain in parsed.netloc

    def is_valid_image_url(self, url: str) -> bool:
        """Geçerli görsel URL mi"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']
        lower_url = url.lower()
        return any(ext in lower_url for ext in image_extensions)

    def is_valid_video_url(self, url: str) -> bool:
        """Geçerli video URL mi"""
        video_patterns = [
            r'youtube\.com/watch',
            r'youtu\.be/',
            r'vimeo\.com/',
            r'\.mp4',
            r'\.webm',
            r'\.mov',
            r'\.avi'
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in video_patterns)

    async def fetch_url(self, url: str) -> Tuple[int, str, str]:
        """URL'yi fetch et"""
        try:
            async with self.semaphore:
                async with self.session.get(
                    url,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=False
                ) as response:
                    final_url = str(response.url)
                    if response.status == 200:
                        content = await response.text()
                        return response.status, content, final_url
                    return response.status, "", final_url
        except Exception as e:
            logger.warning(f"Error fetching {url}: {e}")
            return 0, "", url

    async def get_image_size(self, url: str) -> float:
        """Görsel boyutunu KB olarak al"""
        try:
            async with self.semaphore:
                async with self.session.head(url, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as response:
                    size = response.headers.get('content-length', 0)
                    return int(size) / 1024  # KB
        except:
            return 0

    async def parse_page(self, url: str, content: str) -> None:
        """Sayfayı parse et ve içerikleri topla"""
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove script and style tags
        for tag in soup.find_all(['script', 'style', 'noscript']):
            tag.decompose()
        
        # Extract images
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy')
            if src:
                full_url = urljoin(url, src)
                if self.is_valid_image_url(full_url) or 'image' in full_url.lower():
                    # Skip tiny icons
                    width = img.get('width', '')
                    height = img.get('height', '')
                    try:
                        w = int(width) if width else 100
                        h = int(height) if height else 100
                    except:
                        w, h = 100, 100
                    
                    if w >= 50 and h >= 50:  # Skip very small images
                        size_kb = await self.get_image_size(full_url)
                        self.images.append(ImageInfo(
                            url=full_url,
                            alt=img.get('alt', ''),
                            width=w,
                            height=h,
                            size_kb=size_kb,
                            page_url=url
                        ))
        
        # Extract background images from style attributes
        for tag in soup.find_all(style=True):
            style = tag.get('style', '')
            bg_match = re.search(r'background(?:-image)?:\s*url\(["\']?([^"\')]+)["\']?\)', style)
            if bg_match:
                img_url = urljoin(url, bg_match.group(1))
                if self.is_valid_image_url(img_url):
                    self.images.append(ImageInfo(
                        url=img_url,
                        alt='Background Image',
                        page_url=url
                    ))
        
        # Extract videos
        # YouTube iframes
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if 'youtube' in src or 'vimeo' in src:
                self.videos.append(VideoInfo(
                    url=src,
                    title=iframe.get('title', 'Video'),
                    type='youtube' if 'youtube' in src else 'vimeo',
                    page_url=url
                ))
        
        # Video tags
        for video in soup.find_all('video'):
            src = video.get('src')
            if not src:
                source = video.find('source')
                if source:
                    src = source.get('src')
            if src:
                self.videos.append(VideoInfo(
                    url=urljoin(url, src),
                    title='Video',
                    type='mp4',
                    page_url=url
                ))
        
        # Extract meaningful texts
        # Headings
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            text = heading.get_text(strip=True)
            if len(text) > 10:  # Skip very short headings
                self.texts.append(TextInfo(
                    content=text,
                    title=heading.name.upper(),
                    type='heading',
                    page_url=url,
                    word_count=len(text.split())
                ))
        
        # Paragraphs with substantial content
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 100:  # Only meaningful paragraphs
                self.texts.append(TextInfo(
                    content=text[:500] + ('...' if len(text) > 500 else ''),
                    title='Paragraph',
                    type='paragraph',
                    page_url=url,
                    word_count=len(text.split())
                ))
        
        # Extract links for crawling
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                full_url = urljoin(url, href)
                if self.is_internal_url(full_url):
                    self.discovered_urls.add(self.normalize_url(full_url))
        
        # Check for broken images
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src:
                full_url = urljoin(url, src)
                try:
                    async with self.semaphore:
                        async with self.session.head(full_url, timeout=aiohttp.ClientTimeout(total=5), ssl=False) as response:
                            if response.status >= 400:
                                self.issues.append(CrawlIssue(
                                    source_url=url,
                                    issue_type='broken_image',
                                    element_text=img.get('alt', src),
                                    target_url=full_url,
                                    severity='High',
                                    fix_suggestion=f'Görsel bulunamadı (HTTP {response.status}). Görseli düzeltin veya kaldırın.'
                                ))
                except:
                    pass

    async def crawl_page(self, url: str) -> None:
        """Tek bir sayfayı crawl et"""
        if self.should_stop:
            return
        
        if len(self.visited_urls) >= self.max_pages:
            return
        
        normalized_url = self.normalize_url(url)
        if normalized_url in self.visited_urls:
            return
        
        self.visited_urls.add(normalized_url)
        logger.info(f"Crawling: {url}")
        
        status, content, final_url = await self.fetch_url(url)
        
        if status == 200 and content:
            await self.parse_page(url, content)
        elif status >= 400:
            self.issues.append(CrawlIssue(
                source_url=url,
                issue_type='broken_link',
                element_text='',
                target_url=url,
                severity='Critical',
                fix_suggestion=f'Sayfa HTTP {status} hatası veriyor.'
            ))

    async def run_crawl(self, progress_callback=None) -> CrawlReport:
        """Ana crawl işlemini başlat"""
        self.is_running = True
        self.should_stop = False
        self.progress_callback = progress_callback
        
        start_time = datetime.now().isoformat()
        
        # Create session
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'tr,en;q=0.9',
            }
        )
        
        try:
            # Add start URL
            self.discovered_urls.add(self.normalize_url(self.target_url))
            
            logger.info(f"Starting crawl of {self.target_url}")
            
            # Crawl pages
            iteration = 0
            max_iterations = 20
            
            while iteration < max_iterations and not self.should_stop:
                urls_to_crawl = list(self.discovered_urls - self.visited_urls)
                
                if not urls_to_crawl or len(self.visited_urls) >= self.max_pages:
                    break
                
                urls_to_crawl = urls_to_crawl[:self.max_pages - len(self.visited_urls)]
                
                logger.info(f"Iteration {iteration + 1}: Crawling {len(urls_to_crawl)} URLs")
                
                # Crawl in batches
                batch_size = 5
                for i in range(0, len(urls_to_crawl), batch_size):
                    if self.should_stop:
                        break
                    
                    batch = urls_to_crawl[i:i+batch_size]
                    tasks = [self.crawl_page(url) for url in batch]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    if progress_callback:
                        progress = {
                            'crawled': len(self.visited_urls),
                            'discovered': len(self.discovered_urls),
                            'issues': len(self.issues),
                            'images': len(self.images),
                            'videos': len(self.videos)
                        }
                        await progress_callback(progress)
                
                iteration += 1
            
            # Remove duplicates
            seen_images = set()
            unique_images = []
            for img in self.images:
                if img.url not in seen_images:
                    seen_images.add(img.url)
                    unique_images.append(img)
            self.images = unique_images
            
            seen_videos = set()
            unique_videos = []
            for vid in self.videos:
                if vid.url not in seen_videos:
                    seen_videos.add(vid.url)
                    unique_videos.append(vid)
            self.videos = unique_videos
            
            # Generate report
            report = CrawlReport(
                domain=self.base_domain,
                target_url=self.target_url,
                start_time=start_time,
                end_time=datetime.now().isoformat(),
                total_urls=len(self.visited_urls),
                images=[asdict(img) for img in self.images],
                videos=[asdict(vid) for vid in self.videos],
                texts=[asdict(txt) for txt in self.texts[:100]],  # Limit texts
                issues=[asdict(issue) for issue in self.issues]
            )
            
            return report
            
        finally:
            await self.session.close()
            self.is_running = False

    def stop_crawl(self):
        """Crawl işlemini durdur"""
        self.should_stop = True


def report_to_dict(report: CrawlReport) -> dict:
    """CrawlReport'u dict'e çevir"""
    return asdict(report)
