"""
Demart.com.tr Web Sitesi Denetim Aracı - Crawler Service
%100 Link, Dil, İçerik Uyumluluk Testi
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Dict, List, Set, Optional, Tuple
import re
from datetime import datetime
import logging
from langdetect import detect, DetectorFactory
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json

# Ensure consistent language detection
DetectorFactory.seed = 0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class IssueType(str, Enum):
    BROKEN_LINK = "broken_link"
    BROKEN_IMAGE = "broken_image"
    LANGUAGE_MISMATCH = "language_mismatch"
    REDIRECT_LOOP = "redirect_loop"
    WRONG_REDIRECT = "wrong_redirect"
    MIXED_CONTENT = "mixed_content"
    MISSING_ALT = "missing_alt"
    MISSING_META = "missing_meta"
    CANONICAL_ERROR = "canonical_error"
    HREFLANG_ERROR = "hreflang_error"
    CONTENT_LANGUAGE_MISMATCH = "content_language_mismatch"
    BROKEN_ANCHOR = "broken_anchor"
    INVALID_EMAIL = "invalid_email"
    INVALID_PHONE = "invalid_phone"
    IMAGE_CONTENT_MISMATCH = "image_content_mismatch"
    LARGE_IMAGE = "large_image"
    HTTP_IN_HTTPS = "http_in_https"
    EXTERNAL_LINK_ERROR = "external_link_error"


@dataclass
class CrawlIssue:
    source_url: str
    source_language: str  # TR / EN
    issue_type: str
    element_text: str
    target_url: str
    http_status: int
    final_url: str
    severity: str
    fix_suggestion: str
    element_location: str = ""  # menu, footer, content, etc.


@dataclass
class PageInfo:
    url: str
    language: str  # TR / EN
    http_status: int
    title: str = ""
    meta_description: str = ""
    canonical_url: str = ""
    hreflang_tags: Dict[str, str] = field(default_factory=dict)
    internal_links: List[str] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    images: List[Dict] = field(default_factory=list)
    anchors: List[str] = field(default_factory=list)
    redirect_chain: List[str] = field(default_factory=list)
    content_text: str = ""
    detected_language: str = ""


@dataclass
class CrawlReport:
    domain: str
    start_time: str
    end_time: str = ""
    total_urls: int = 0
    tr_pages: int = 0
    en_pages: int = 0
    broken_links: int = 0
    broken_images: int = 0
    language_errors: int = 0
    redirect_loops: int = 0
    issues: List[CrawlIssue] = field(default_factory=list)
    all_urls: List[Dict] = field(default_factory=list)
    pages: List[PageInfo] = field(default_factory=list)


class DemartCrawler:
    """Web sitesi denetim crawler'ı"""
    
    BASE_DOMAIN = "demart.com.tr"
    TARGET_URL = "https://www.demart.com.tr"
    MAX_CONCURRENT = 5
    TIMEOUT = 30
    
    # Turkish language indicators in URL
    TR_URL_PATTERNS = [
        r'/tr/',
        r'/tr$',
        r'\?lang=tr',
        r'&lang=tr',
    ]
    
    # English language indicators in URL
    EN_URL_PATTERNS = [
        r'/en/',
        r'/en$',
        r'\?lang=en',
        r'&lang=en',
    ]
    
    # Turkish keywords for content detection
    TR_KEYWORDS = [
        'hizmetler', 'hakkımızda', 'iletişim', 'anasayfa', 'ürünler',
        've', 'ile', 'için', 'olan', 'bir', 'bu', 'gibi', 'daha',
        'çok', 'şirket', 'müşteri', 'proje', 'kalite', 'çözüm'
    ]
    
    # English keywords for content detection  
    EN_KEYWORDS = [
        'services', 'about', 'contact', 'home', 'products',
        'and', 'with', 'for', 'the', 'our', 'your', 'this',
        'company', 'customer', 'project', 'quality', 'solution'
    ]

    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.discovered_urls: Set[str] = set()
        self.issues: List[CrawlIssue] = []
        self.pages: Dict[str, PageInfo] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        self.progress_callback = None
        self.is_running = False
        self.should_stop = False
        
    def normalize_url(self, url: str) -> str:
        """URL'yi normalize et"""
        parsed = urlparse(url)
        # Remove trailing slash and fragment
        path = parsed.path.rstrip('/')
        if not path:
            path = '/'
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized
    
    def is_internal_url(self, url: str) -> bool:
        """URL internal mi kontrol et"""
        parsed = urlparse(url)
        return self.BASE_DOMAIN in parsed.netloc
    
    def detect_url_language(self, url: str) -> str:
        """URL'den dil tespit et"""
        url_lower = url.lower()
        
        for pattern in self.EN_URL_PATTERNS:
            if re.search(pattern, url_lower):
                return "EN"
        
        for pattern in self.TR_URL_PATTERNS:
            if re.search(pattern, url_lower):
                return "TR"
        
        # Default to TR for main domain without language indicator
        return "TR"
    
    def detect_content_language(self, text: str) -> str:
        """İçerikten dil tespit et"""
        if not text or len(text.strip()) < 20:
            return "UNKNOWN"
        
        try:
            detected = detect(text)
            if detected == 'tr':
                return "TR"
            elif detected == 'en':
                return "EN"
            else:
                return detected.upper()
        except:
            # Fallback: keyword based detection
            text_lower = text.lower()
            tr_count = sum(1 for kw in self.TR_KEYWORDS if kw in text_lower)
            en_count = sum(1 for kw in self.EN_KEYWORDS if kw in text_lower)
            
            if tr_count > en_count:
                return "TR"
            elif en_count > tr_count:
                return "EN"
            return "UNKNOWN"
    
    def get_element_location(self, element) -> str:
        """Element'in sayfa içindeki konumunu tespit et"""
        if not element:
            return "unknown"
        
        # Check parent elements
        for parent in element.parents:
            if parent.name:
                parent_class = parent.get('class', [])
                parent_id = parent.get('id', '')
                
                # Menu detection
                if any(x in str(parent_class).lower() + parent_id.lower() 
                       for x in ['nav', 'menu', 'header']):
                    return "menu"
                
                # Footer detection
                if any(x in str(parent_class).lower() + parent_id.lower() 
                       for x in ['footer', 'bottom']):
                    return "footer"
                
                # Sidebar detection
                if any(x in str(parent_class).lower() + parent_id.lower() 
                       for x in ['sidebar', 'aside']):
                    return "sidebar"
                
                # Banner/Slider detection
                if any(x in str(parent_class).lower() + parent_id.lower() 
                       for x in ['banner', 'slider', 'carousel', 'hero']):
                    return "banner"
        
        return "content"

    async def fetch_url(self, url: str, follow_redirects: bool = True) -> Tuple[int, str, str, List[str]]:
        """URL'yi fetch et ve sonucu döndür"""
        redirect_chain = []
        final_url = url
        
        try:
            async with self.semaphore:
                async with self.session.get(
                    url, 
                    allow_redirects=follow_redirects,
                    timeout=aiohttp.ClientTimeout(total=self.TIMEOUT),
                    ssl=False  # SSL verification issues için
                ) as response:
                    # Track redirects
                    if response.history:
                        redirect_chain = [str(r.url) for r in response.history]
                    
                    final_url = str(response.url)
                    content = await response.text()
                    return response.status, content, final_url, redirect_chain
        except asyncio.TimeoutError:
            return 408, "", url, redirect_chain
        except aiohttp.ClientError as e:
            logger.error(f"Client error fetching {url}: {e}")
            return 0, "", url, redirect_chain
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return 0, "", url, redirect_chain

    async def fetch_sitemap(self) -> List[str]:
        """Sitemap.xml'den URL'leri çek"""
        urls = []
        sitemap_urls = [
            f"{self.TARGET_URL}/sitemap.xml",
            f"{self.TARGET_URL}/sitemap_index.xml",
            f"{self.TARGET_URL}/sitemap-index.xml",
        ]
        
        for sitemap_url in sitemap_urls:
            try:
                status, content, _, _ = await self.fetch_url(sitemap_url)
                if status == 200 and content:
                    # Parse XML
                    root = ET.fromstring(content)
                    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
                    
                    # Check for sitemap index
                    sitemaps = root.findall('.//sm:sitemap/sm:loc', ns)
                    if sitemaps:
                        for sitemap in sitemaps:
                            sub_urls = await self._fetch_sub_sitemap(sitemap.text)
                            urls.extend(sub_urls)
                    
                    # Regular sitemap URLs
                    locs = root.findall('.//sm:url/sm:loc', ns)
                    for loc in locs:
                        if loc.text:
                            urls.append(loc.text)
                    
                    # Try without namespace
                    if not urls:
                        locs = root.findall('.//loc')
                        for loc in locs:
                            if loc.text:
                                urls.append(loc.text)
                    
                    if urls:
                        logger.info(f"Found {len(urls)} URLs in sitemap")
                        break
            except Exception as e:
                logger.warning(f"Error parsing sitemap {sitemap_url}: {e}")
        
        return list(set(urls))
    
    async def _fetch_sub_sitemap(self, url: str) -> List[str]:
        """Alt sitemap'i parse et"""
        urls = []
        try:
            status, content, _, _ = await self.fetch_url(url)
            if status == 200 and content:
                root = ET.fromstring(content)
                ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
                locs = root.findall('.//sm:url/sm:loc', ns)
                for loc in locs:
                    if loc.text:
                        urls.append(loc.text)
                if not urls:
                    locs = root.findall('.//loc')
                    for loc in locs:
                        if loc.text:
                            urls.append(loc.text)
        except Exception as e:
            logger.warning(f"Error parsing sub-sitemap {url}: {e}")
        return urls

    async def parse_page(self, url: str, content: str, status: int, 
                         final_url: str, redirect_chain: List[str]) -> PageInfo:
        """Sayfayı parse et ve bilgileri çıkar"""
        soup = BeautifulSoup(content, 'lxml')
        url_language = self.detect_url_language(url)
        
        page_info = PageInfo(
            url=url,
            language=url_language,
            http_status=status,
            redirect_chain=redirect_chain
        )
        
        # Title
        title_tag = soup.find('title')
        page_info.title = title_tag.get_text().strip() if title_tag else ""
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        page_info.meta_description = meta_desc.get('content', '') if meta_desc else ""
        
        # Canonical URL
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        page_info.canonical_url = canonical.get('href', '') if canonical else ""
        
        # Hreflang tags
        hreflangs = soup.find_all('link', attrs={'rel': 'alternate', 'hreflang': True})
        for tag in hreflangs:
            lang = tag.get('hreflang', '')
            href = tag.get('href', '')
            if lang and href:
                page_info.hreflang_tags[lang] = href
        
        # Extract main content text
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            # Remove script and style
            for tag in main_content.find_all(['script', 'style', 'noscript']):
                tag.decompose()
            page_info.content_text = main_content.get_text(' ', strip=True)[:5000]
            page_info.detected_language = self.detect_content_language(page_info.content_text)
        
        # Extract all links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if not href or href.startswith('#') or href.startswith('javascript:'):
                if href.startswith('#') and len(href) > 1:
                    page_info.anchors.append(href)
                continue
            
            full_url = urljoin(url, href)
            
            if self.is_internal_url(full_url):
                page_info.internal_links.append(full_url)
                self.discovered_urls.add(self.normalize_url(full_url))
            else:
                page_info.external_links.append(full_url)
            
            # Check language mismatch
            link_text = link.get_text().strip()
            element_location = self.get_element_location(link)
            await self._check_link_language(url, url_language, full_url, link_text, element_location)
        
        # Extract images
        for img in soup.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if src:
                full_src = urljoin(url, src)
                alt = img.get('alt', '')
                page_info.images.append({
                    'src': full_src,
                    'alt': alt,
                    'has_alt': bool(alt),
                    'context': self._get_image_context(img)
                })
        
        return page_info

    def _get_image_context(self, img_tag) -> str:
        """Görsel çevresindeki bağlamı al"""
        context_parts = []
        
        # Get alt text
        alt = img_tag.get('alt', '')
        if alt:
            context_parts.append(f"alt: {alt}")
        
        # Get title
        title = img_tag.get('title', '')
        if title:
            context_parts.append(f"title: {title}")
        
        # Get surrounding text
        parent = img_tag.parent
        if parent:
            sibling_text = parent.get_text(' ', strip=True)[:200]
            if sibling_text:
                context_parts.append(f"context: {sibling_text}")
        
        return ' | '.join(context_parts)

    async def _check_link_language(self, source_url: str, source_lang: str, 
                                   target_url: str, link_text: str, location: str):
        """Link dil uyumluluğunu kontrol et"""
        if not self.is_internal_url(target_url):
            return
        
        target_lang = self.detect_url_language(target_url)
        
        # Dil değiştirici linkleri hariç tut
        if any(x in link_text.lower() for x in ['english', 'türkçe', 'tr', 'en']):
            if 'lang' in location.lower() or len(link_text) < 10:
                return
        
        # TR sayfadan EN sayfaya link hatası
        if source_lang == "TR" and target_lang == "EN":
            self.issues.append(CrawlIssue(
                source_url=source_url,
                source_language=source_lang,
                issue_type=IssueType.LANGUAGE_MISMATCH.value,
                element_text=link_text[:100],
                target_url=target_url,
                http_status=0,
                final_url=target_url,
                severity=Severity.CRITICAL.value,
                fix_suggestion=f"TR sayfadaki link EN sayfaya yönlendiriyor. '{link_text}' linkini TR versiyonuna yönlendirin.",
                element_location=location
            ))
        
        # EN sayfadan TR sayfaya link hatası
        elif source_lang == "EN" and target_lang == "TR":
            self.issues.append(CrawlIssue(
                source_url=source_url,
                source_language=source_lang,
                issue_type=IssueType.LANGUAGE_MISMATCH.value,
                element_text=link_text[:100],
                target_url=target_url,
                http_status=0,
                final_url=target_url,
                severity=Severity.CRITICAL.value,
                fix_suggestion=f"EN sayfadaki link TR sayfaya yönlendiriyor. '{link_text}' linkini EN versiyonuna yönlendirin.",
                element_location=location
            ))

    async def check_image(self, page_url: str, page_lang: str, image_info: Dict):
        """Görsel kontrolü yap"""
        src = image_info['src']
        alt = image_info.get('alt', '')
        context = image_info.get('context', '')
        
        # HTTP status kontrolü
        try:
            async with self.semaphore:
                async with self.session.head(
                    src,
                    timeout=aiohttp.ClientTimeout(total=15),
                    ssl=False
                ) as response:
                    status = response.status
                    content_length = response.headers.get('content-length', 0)
                    content_type = response.headers.get('content-type', '')
        except Exception as e:
            status = 0
            content_length = 0
            content_type = ''
        
        # Kırık görsel
        if status in [404, 403, 0]:
            self.issues.append(CrawlIssue(
                source_url=page_url,
                source_language=page_lang,
                issue_type=IssueType.BROKEN_IMAGE.value,
                element_text=alt or src.split('/')[-1],
                target_url=src,
                http_status=status,
                final_url=src,
                severity=Severity.HIGH.value,
                fix_suggestion=f"Görsel bulunamadı veya erişilemiyor. Görseli düzeltin: {src}",
                element_location="image"
            ))
        
        # Alt etiketi eksik
        if not alt and status == 200:
            self.issues.append(CrawlIssue(
                source_url=page_url,
                source_language=page_lang,
                issue_type=IssueType.MISSING_ALT.value,
                element_text=src.split('/')[-1],
                target_url=src,
                http_status=status,
                final_url=src,
                severity=Severity.MEDIUM.value,
                fix_suggestion=f"Görsel için alt etiketi eksik. SEO ve erişilebilirlik için alt ekleyin.",
                element_location="image"
            ))
        
        # HTTPS sayfada HTTP görsel
        if page_url.startswith('https://') and src.startswith('http://'):
            self.issues.append(CrawlIssue(
                source_url=page_url,
                source_language=page_lang,
                issue_type=IssueType.HTTP_IN_HTTPS.value,
                element_text=alt or src.split('/')[-1],
                target_url=src,
                http_status=status,
                final_url=src,
                severity=Severity.HIGH.value,
                fix_suggestion=f"HTTPS sayfada HTTP görsel kullanılıyor. Görseli HTTPS'e çevirin.",
                element_location="image"
            ))
        
        # Büyük dosya kontrolü (> 2MB)
        try:
            if int(content_length) > 2 * 1024 * 1024:
                self.issues.append(CrawlIssue(
                    source_url=page_url,
                    source_language=page_lang,
                    issue_type=IssueType.LARGE_IMAGE.value,
                    element_text=alt or src.split('/')[-1],
                    target_url=src,
                    http_status=status,
                    final_url=src,
                    severity=Severity.MEDIUM.value,
                    fix_suggestion=f"Görsel boyutu çok büyük ({int(content_length)/1024/1024:.1f}MB). Optimize edin.",
                    element_location="image"
                ))
        except:
            pass
        
        # Görsel-içerik uyumu kontrolü (dil bazlı)
        if alt and status == 200:
            alt_lang = self.detect_content_language(alt)
            if alt_lang != "UNKNOWN" and alt_lang != page_lang:
                self.issues.append(CrawlIssue(
                    source_url=page_url,
                    source_language=page_lang,
                    issue_type=IssueType.IMAGE_CONTENT_MISMATCH.value,
                    element_text=alt,
                    target_url=src,
                    http_status=status,
                    final_url=src,
                    severity=Severity.HIGH.value,
                    fix_suggestion=f"{page_lang} sayfada {alt_lang} dilinde görsel alt etiketi var. Alt etiketini {page_lang} diline çevirin.",
                    element_location="image"
                ))

    async def check_external_link(self, source_url: str, source_lang: str, 
                                  target_url: str, link_text: str):
        """Harici link kontrolü"""
        try:
            async with self.semaphore:
                async with self.session.head(
                    target_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False,
                    allow_redirects=True
                ) as response:
                    if response.status >= 400:
                        self.issues.append(CrawlIssue(
                            source_url=source_url,
                            source_language=source_lang,
                            issue_type=IssueType.EXTERNAL_LINK_ERROR.value,
                            element_text=link_text[:100],
                            target_url=target_url,
                            http_status=response.status,
                            final_url=str(response.url),
                            severity=Severity.MEDIUM.value,
                            fix_suggestion=f"Harici link çalışmıyor (HTTP {response.status}). Linki güncelleyin veya kaldırın.",
                            element_location="external"
                        ))
        except Exception as e:
            self.issues.append(CrawlIssue(
                source_url=source_url,
                source_language=source_lang,
                issue_type=IssueType.EXTERNAL_LINK_ERROR.value,
                element_text=link_text[:100],
                target_url=target_url,
                http_status=0,
                final_url=target_url,
                severity=Severity.LOW.value,
                fix_suggestion=f"Harici linke erişilemiyor: {str(e)[:50]}",
                element_location="external"
            ))

    async def check_content_language(self, page_info: PageInfo):
        """Sayfa içerik dil tutarlılığı kontrolü"""
        if page_info.detected_language == "UNKNOWN":
            return
        
        if page_info.language != page_info.detected_language:
            self.issues.append(CrawlIssue(
                source_url=page_info.url,
                source_language=page_info.language,
                issue_type=IssueType.CONTENT_LANGUAGE_MISMATCH.value,
                element_text=page_info.content_text[:200],
                target_url=page_info.url,
                http_status=page_info.http_status,
                final_url=page_info.url,
                severity=Severity.HIGH.value,
                fix_suggestion=f"Sayfa URL'si {page_info.language} dil gösteriyor ama içerik {page_info.detected_language} dilinde. İçeriği düzeltin.",
                element_location="content"
            ))

    async def check_technical_seo(self, page_info: PageInfo):
        """Teknik SEO kontrolü"""
        # Missing title
        if not page_info.title:
            self.issues.append(CrawlIssue(
                source_url=page_info.url,
                source_language=page_info.language,
                issue_type=IssueType.MISSING_META.value,
                element_text="Title tag eksik",
                target_url=page_info.url,
                http_status=page_info.http_status,
                final_url=page_info.url,
                severity=Severity.HIGH.value,
                fix_suggestion="Sayfa başlığı (title) eksik. SEO için başlık ekleyin.",
                element_location="head"
            ))
        
        # Missing meta description
        if not page_info.meta_description:
            self.issues.append(CrawlIssue(
                source_url=page_info.url,
                source_language=page_info.language,
                issue_type=IssueType.MISSING_META.value,
                element_text="Meta description eksik",
                target_url=page_info.url,
                http_status=page_info.http_status,
                final_url=page_info.url,
                severity=Severity.MEDIUM.value,
                fix_suggestion="Meta açıklama eksik. SEO için meta description ekleyin.",
                element_location="head"
            ))
        
        # Canonical URL check
        if page_info.canonical_url:
            canonical_lang = self.detect_url_language(page_info.canonical_url)
            if canonical_lang != page_info.language:
                self.issues.append(CrawlIssue(
                    source_url=page_info.url,
                    source_language=page_info.language,
                    issue_type=IssueType.CANONICAL_ERROR.value,
                    element_text=page_info.canonical_url,
                    target_url=page_info.canonical_url,
                    http_status=page_info.http_status,
                    final_url=page_info.url,
                    severity=Severity.HIGH.value,
                    fix_suggestion=f"Canonical URL ({canonical_lang}) sayfa diliyle ({page_info.language}) uyuşmuyor.",
                    element_location="head"
                ))
        
        # Hreflang bidirectional check
        if page_info.hreflang_tags:
            for lang, href in page_info.hreflang_tags.items():
                if lang in ['tr', 'tr-TR'] and page_info.language == 'EN':
                    # EN page should have TR alternate
                    pass
                elif lang in ['en', 'en-US', 'en-GB'] and page_info.language == 'TR':
                    # TR page should have EN alternate
                    pass

    async def crawl_page(self, url: str) -> Optional[PageInfo]:
        """Tek bir sayfayı crawl et"""
        if self.should_stop:
            return None
        
        normalized_url = self.normalize_url(url)
        if normalized_url in self.visited_urls:
            return None
        
        self.visited_urls.add(normalized_url)
        
        logger.info(f"Crawling: {url}")
        
        status, content, final_url, redirect_chain = await self.fetch_url(url)
        
        if status == 0:
            self.issues.append(CrawlIssue(
                source_url=url,
                source_language=self.detect_url_language(url),
                issue_type=IssueType.BROKEN_LINK.value,
                element_text="",
                target_url=url,
                http_status=status,
                final_url=final_url,
                severity=Severity.CRITICAL.value,
                fix_suggestion="Sayfaya erişilemiyor. URL'yi kontrol edin.",
                element_location="page"
            ))
            return None
        
        if status >= 400:
            self.issues.append(CrawlIssue(
                source_url=url,
                source_language=self.detect_url_language(url),
                issue_type=IssueType.BROKEN_LINK.value,
                element_text="",
                target_url=url,
                http_status=status,
                final_url=final_url,
                severity=Severity.CRITICAL.value,
                fix_suggestion=f"Sayfa HTTP {status} hatası veriyor. Düzeltin veya yönlendirme ekleyin.",
                element_location="page"
            ))
            return None
        
        # Check redirect loop
        if len(redirect_chain) > 5:
            self.issues.append(CrawlIssue(
                source_url=url,
                source_language=self.detect_url_language(url),
                issue_type=IssueType.REDIRECT_LOOP.value,
                element_text=" -> ".join(redirect_chain[:5]),
                target_url=url,
                http_status=status,
                final_url=final_url,
                severity=Severity.CRITICAL.value,
                fix_suggestion="Çok fazla yönlendirme var. Redirect zincirini düzeltin.",
                element_location="redirect"
            ))
        
        # Check wrong language redirect
        if redirect_chain:
            source_lang = self.detect_url_language(url)
            final_lang = self.detect_url_language(final_url)
            if source_lang != final_lang:
                self.issues.append(CrawlIssue(
                    source_url=url,
                    source_language=source_lang,
                    issue_type=IssueType.WRONG_REDIRECT.value,
                    element_text=f"{source_lang} -> {final_lang}",
                    target_url=final_url,
                    http_status=status,
                    final_url=final_url,
                    severity=Severity.CRITICAL.value,
                    fix_suggestion=f"{source_lang} URL'si {final_lang} sayfasına yönlendiriliyor. Yönlendirmeyi düzeltin.",
                    element_location="redirect"
                ))
        
        # Parse page
        page_info = await self.parse_page(url, content, status, final_url, redirect_chain)
        self.pages[url] = page_info
        
        # Content language check
        await self.check_content_language(page_info)
        
        # Technical SEO check
        await self.check_technical_seo(page_info)
        
        # Image checks
        for img in page_info.images:
            await self.check_image(url, page_info.language, img)
        
        # External link checks (sample - not all)
        for ext_link in page_info.external_links[:5]:
            await self.check_external_link(url, page_info.language, ext_link, "")
        
        return page_info

    async def run_crawl(self, progress_callback=None) -> CrawlReport:
        """Ana crawl işlemini başlat"""
        self.is_running = True
        self.should_stop = False
        self.progress_callback = progress_callback
        
        start_time = datetime.now().isoformat()
        
        # Create session
        connector = aiohttp.TCPConnector(limit=self.MAX_CONCURRENT, ssl=False)
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; DemartBot/1.0; +https://demart.com.tr)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'tr,en;q=0.9',
            }
        )
        
        try:
            # Phase 1: Fetch sitemap URLs
            logger.info("Fetching sitemap...")
            sitemap_urls = await self.fetch_sitemap()
            
            # Phase 2: Add homepage
            self.discovered_urls.add(self.TARGET_URL)
            self.discovered_urls.add(f"{self.TARGET_URL}/")
            self.discovered_urls.add(f"{self.TARGET_URL}/en")
            self.discovered_urls.add(f"{self.TARGET_URL}/en/")
            
            # Add sitemap URLs
            for url in sitemap_urls:
                self.discovered_urls.add(self.normalize_url(url))
            
            logger.info(f"Total discovered URLs: {len(self.discovered_urls)}")
            
            # Phase 3: Crawl all pages
            iteration = 0
            max_iterations = 10  # Prevent infinite loop
            
            while iteration < max_iterations and not self.should_stop:
                urls_to_crawl = list(self.discovered_urls - self.visited_urls)
                
                if not urls_to_crawl:
                    break
                
                logger.info(f"Iteration {iteration + 1}: Crawling {len(urls_to_crawl)} URLs")
                
                # Crawl in batches
                batch_size = 10
                for i in range(0, len(urls_to_crawl), batch_size):
                    if self.should_stop:
                        break
                    
                    batch = urls_to_crawl[i:i+batch_size]
                    tasks = [self.crawl_page(url) for url in batch]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Progress update
                    if progress_callback:
                        progress = {
                            'crawled': len(self.visited_urls),
                            'discovered': len(self.discovered_urls),
                            'issues': len(self.issues),
                            'current_batch': i // batch_size + 1
                        }
                        await progress_callback(progress)
                
                iteration += 1
            
            # Generate report
            report = self._generate_report(start_time)
            
            return report
            
        finally:
            await self.session.close()
            self.is_running = False

    def _generate_report(self, start_time: str) -> CrawlReport:
        """Rapor oluştur"""
        tr_pages = sum(1 for p in self.pages.values() if p.language == "TR")
        en_pages = sum(1 for p in self.pages.values() if p.language == "EN")
        
        broken_links = sum(1 for i in self.issues if i.issue_type == IssueType.BROKEN_LINK.value)
        broken_images = sum(1 for i in self.issues if i.issue_type == IssueType.BROKEN_IMAGE.value)
        language_errors = sum(1 for i in self.issues if i.issue_type in [
            IssueType.LANGUAGE_MISMATCH.value,
            IssueType.CONTENT_LANGUAGE_MISMATCH.value
        ])
        redirect_loops = sum(1 for i in self.issues if i.issue_type == IssueType.REDIRECT_LOOP.value)
        
        all_urls = []
        for url, page in self.pages.items():
            all_urls.append({
                'url': url,
                'language': page.language,
                'http_status': page.http_status,
                'redirect_chain': page.redirect_chain,
                'title': page.title
            })
        
        return CrawlReport(
            domain=self.BASE_DOMAIN,
            start_time=start_time,
            end_time=datetime.now().isoformat(),
            total_urls=len(self.visited_urls),
            tr_pages=tr_pages,
            en_pages=en_pages,
            broken_links=broken_links,
            broken_images=broken_images,
            language_errors=language_errors,
            redirect_loops=redirect_loops,
            issues=self.issues,
            all_urls=all_urls
        )

    def stop_crawl(self):
        """Crawl işlemini durdur"""
        self.should_stop = True

    def reset(self):
        """Crawler'ı sıfırla"""
        self.visited_urls.clear()
        self.discovered_urls.clear()
        self.issues.clear()
        self.pages.clear()
        self.is_running = False
        self.should_stop = False


def issue_to_dict(issue: CrawlIssue) -> dict:
    """CrawlIssue'yu dict'e çevir"""
    return asdict(issue)


def report_to_dict(report: CrawlReport) -> dict:
    """CrawlReport'u dict'e çevir"""
    return {
        'domain': report.domain,
        'start_time': report.start_time,
        'end_time': report.end_time,
        'total_urls': report.total_urls,
        'tr_pages': report.tr_pages,
        'en_pages': report.en_pages,
        'broken_links': report.broken_links,
        'broken_images': report.broken_images,
        'language_errors': report.language_errors,
        'redirect_loops': report.redirect_loops,
        'issues': [issue_to_dict(i) for i in report.issues],
        'all_urls': report.all_urls
    }
