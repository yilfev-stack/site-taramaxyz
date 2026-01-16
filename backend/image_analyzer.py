"""
AI Görsel-İçerik Uyumluluk Analizi Servisi
Gemini Vision API kullanarak görsellerin sayfa içeriğiyle uyumunu kontrol eder
"""

import asyncio
import aiohttp
import base64
import os
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Emergent LLM entegrasyonu
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    HAS_EMERGENT = True
except ImportError:
    HAS_EMERGENT = False
    logger.warning("emergentintegrations not found, image analysis will be limited")


@dataclass
class ImageAnalysisResult:
    image_url: str
    is_relevant: bool
    confidence: float  # 0-100
    image_description: str
    page_context: str
    mismatch_reason: str
    severity: str  # Critical, High, Medium, Low
    suggestion: str


class ImageContentAnalyzer:
    """AI ile görsel-içerik uyumu analizi"""
    
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY', '')
        self.session_counter = 0
        
    async def download_image_as_base64(self, image_url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Görseli indir ve base64'e çevir"""
        try:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    # Sadece desteklenen formatlar
                    if any(fmt in content_type.lower() for fmt in ['jpeg', 'jpg', 'png', 'webp']):
                        image_data = await response.read()
                        # Çok küçük görselleri atla (ikonlar vb.)
                        if len(image_data) < 5000:  # 5KB'den küçük
                            return None
                        # Çok büyük görselleri atla
                        if len(image_data) > 5 * 1024 * 1024:  # 5MB'den büyük
                            return None
                        return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.warning(f"Image download failed for {image_url}: {e}")
        return None

    async def analyze_image_relevance(
        self, 
        image_url: str,
        image_base64: str,
        page_title: str,
        page_content: str,
        page_url: str
    ) -> Optional[ImageAnalysisResult]:
        """Görselin sayfa içeriğiyle uyumunu AI ile analiz et"""
        
        if not HAS_EMERGENT or not self.api_key:
            logger.warning("Emergent API not available for image analysis")
            return None
        
        try:
            self.session_counter += 1
            
            # Sayfa içeriğini kısalt
            content_summary = page_content[:1500] if page_content else ""
            
            # AI prompt
            analysis_prompt = f"""Bu görseli analiz et ve sayfa içeriğiyle uyumunu değerlendir.

SAYFA BİLGİLERİ:
- URL: {page_url}
- Başlık: {page_title}
- İçerik Özeti: {content_summary[:800]}

GÖREV:
1. Görselde ne görüyorsun? (kişi, ürün, nesne, manzara vb.)
2. Bu görsel sayfa içeriğiyle alakalı mı?
3. Eğer alakasız bir stok fotoğraf ise (örn: endüstriyel ürün sayfasında alakasız insan fotoğrafı) bunu tespit et.

YANITINI ŞÖYLE VER (JSON formatında):
{{
    "image_description": "Görselde görülen şeyin kısa açıklaması",
    "is_relevant": true/false,
    "confidence": 0-100 arası güven skoru,
    "mismatch_reason": "Eğer alakasız ise neden (yoksa boş bırak)",
    "severity": "Critical/High/Medium/Low (alakasız ise High, kısmen alakalı ise Medium)",
    "suggestion": "Düzeltme önerisi"
}}

ÖNEMLİ: Eğer görsel bir stok fotoğraf ve sayfa içeriğiyle alakasız görünüyorsa (örn: vana kilitleri sayfasında siyahi adam fotoğrafı) bunu mutlaka tespit et ve is_relevant: false yap."""

            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"image-analysis-{self.session_counter}",
                system_message="Sen bir web sitesi denetim uzmanısın. Görsellerin sayfa içeriğiyle uyumunu analiz ediyorsun. Alakasız stok fotoğrafları tespit etmekte uzmanlaşmışsın."
            ).with_model("gemini", "gemini-2.5-flash")
            
            # Görsel içeriği oluştur
            image_content = ImageContent(image_base64=image_base64)
            
            user_message = UserMessage(
                text=analysis_prompt,
                file_contents=[image_content]
            )
            
            response = await chat.send_message(user_message)
            
            # JSON yanıtı parse et
            result = self._parse_analysis_response(response, image_url, page_content[:200])
            return result
            
        except Exception as e:
            logger.error(f"Image analysis failed for {image_url}: {e}")
            return None
    
    def _parse_analysis_response(self, response: str, image_url: str, page_context: str) -> Optional[ImageAnalysisResult]:
        """AI yanıtını parse et"""
        import json
        import re
        
        try:
            # JSON bloğunu bul
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                return ImageAnalysisResult(
                    image_url=image_url,
                    is_relevant=data.get('is_relevant', True),
                    confidence=float(data.get('confidence', 50)),
                    image_description=data.get('image_description', ''),
                    page_context=page_context,
                    mismatch_reason=data.get('mismatch_reason', ''),
                    severity=data.get('severity', 'Medium'),
                    suggestion=data.get('suggestion', '')
                )
        except Exception as e:
            logger.warning(f"Failed to parse AI response: {e}")
        
        return None

    async def analyze_page_images(
        self,
        page_url: str,
        page_title: str,
        page_content: str,
        images: List[Dict],
        session: aiohttp.ClientSession,
        max_images: int = 10
    ) -> List[ImageAnalysisResult]:
        """Sayfadaki tüm görselleri analiz et"""
        
        results = []
        analyzed_count = 0
        
        for img in images:
            if analyzed_count >= max_images:
                break
                
            image_url = img.get('src', '')
            if not image_url:
                continue
            
            # SVG ve çok küçük görselleri atla
            if '.svg' in image_url.lower() or 'icon' in image_url.lower():
                continue
            
            # Görseli indir
            image_base64 = await self.download_image_as_base64(image_url, session)
            if not image_base64:
                continue
            
            # AI analizi yap
            result = await self.analyze_image_relevance(
                image_url=image_url,
                image_base64=image_base64,
                page_title=page_title,
                page_content=page_content,
                page_url=page_url
            )
            
            if result and not result.is_relevant:
                results.append(result)
                logger.info(f"Found irrelevant image: {image_url} - {result.mismatch_reason}")
            
            analyzed_count += 1
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        return results


# Test fonksiyonu
async def test_analyzer():
    analyzer = ImageContentAnalyzer()
    
    async with aiohttp.ClientSession() as session:
        # Test için örnek bir sayfa
        test_url = "https://demart.com.tr/hizmetler/operasyon-bakim"
        
        async with session.get(test_url, ssl=False) as response:
            if response.status == 200:
                from bs4 import BeautifulSoup
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
                
                title = soup.find('title')
                title_text = title.get_text() if title else ""
                
                main = soup.find('main') or soup.find('body')
                content_text = main.get_text(' ', strip=True)[:2000] if main else ""
                
                images = []
                for img in soup.find_all('img'):
                    src = img.get('src', '') or img.get('data-src', '')
                    if src:
                        from urllib.parse import urljoin
                        full_src = urljoin(test_url, src)
                        images.append({'src': full_src, 'alt': img.get('alt', '')})
                
                print(f"Found {len(images)} images")
                
                results = await analyzer.analyze_page_images(
                    page_url=test_url,
                    page_title=title_text,
                    page_content=content_text,
                    images=images,
                    session=session,
                    max_images=5
                )
                
                for r in results:
                    print(f"\n--- IRRELEVANT IMAGE ---")
                    print(f"URL: {r.image_url}")
                    print(f"Description: {r.image_description}")
                    print(f"Reason: {r.mismatch_reason}")
                    print(f"Severity: {r.severity}")


if __name__ == "__main__":
    asyncio.run(test_analyzer())
